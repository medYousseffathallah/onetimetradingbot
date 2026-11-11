"""Asynchronous job runner for the Playwright browser collector (Milestone 10, Phase 4).

Eliminates synchronous HTTP reverse-proxy timeouts by:
1. Spawning the browser collector in a managed background worker.
2. Returning a job_id immediately (HTTP 202 Accepted).
3. Allowing the client to poll job status via GET /api/sync/jobs/{job_id}.
4. Detecting and cleaning stale profile lockfiles to prevent collisions.
5. Providing structured job cancellation.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from bvmt.snapshots import atomic_write_text

JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]


@dataclass
class SyncJob:
    """State record for an asynchronous browser synchronization job."""

    job_id: str
    status: JobStatus
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    timeout_seconds: int = 180
    error_message: str | None = None
    snapshot_path: str | None = None
    snapshot_data: dict[str, object] | None = None
    proc: subprocess.Popen[str] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "timeout_seconds": self.timeout_seconds,
            "error_message": self.error_message,
            "snapshot_path": self.snapshot_path,
            "snapshot_data": self.snapshot_data,
        }


class PlaywrightJobManager:
    """Thread-safe manager for Playwright background collection jobs with disk persistence."""

    def __init__(self, *, jobs_path: Path | None = None) -> None:
        self._jobs: dict[str, SyncJob] = {}
        self._lock = threading.Lock()
        self._jobs_path = jobs_path
        if self._jobs_path is not None:
            self._load_jobs()

    def configure_persistence(self, jobs_path: Path) -> None:
        """Bind a persistence file path lazily (used when FastAPI app sets snapshots_dir)."""
        with self._lock:
            if self._jobs_path != jobs_path:
                self._jobs.clear()
            self._jobs_path = jobs_path
            self._load_jobs_locked()

    def _load_jobs(self) -> None:
        with self._lock:
            self._load_jobs_locked()

    def _load_jobs_locked(self) -> None:
        if self._jobs_path is None or not self._jobs_path.is_file():
            return
        try:
            raw = json.loads(self._jobs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        for jid, entry in raw.items():
            if not isinstance(entry, dict) or jid in self._jobs:
                continue
            status = str(entry.get("status", "FAILED"))
            err = entry.get("error_message")
            completed_at = entry.get("completed_at")
            if status in {"QUEUED", "RUNNING"}:
                status = "FAILED"
                err = str(err or "Background browser sync interrupted by application restart.")
                completed_at = datetime.now(UTC).isoformat()
            self._jobs[str(jid)] = SyncJob(
                job_id=str(entry.get("job_id", jid)),
                status=status,  # type: ignore[arg-type]
                created_at=str(entry.get("created_at", "")),
                started_at=str(entry["started_at"]) if entry.get("started_at") else None,
                completed_at=str(completed_at) if completed_at else None,
                timeout_seconds=int(entry.get("timeout_seconds", 180)),
                error_message=str(err) if err is not None else None,
                snapshot_path=str(entry["snapshot_path"]) if entry.get("snapshot_path") else None,
                snapshot_data=(
                    dict(entry["snapshot_data"])
                    if isinstance(entry.get("snapshot_data"), dict)
                    else None
                ),
            )

    def _persist_jobs_locked(self) -> None:
        if self._jobs_path is None:
            return
        try:
            self._jobs_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {jid: job.to_dict() for jid, job in self._jobs.items()}
            atomic_write_text(
                self._jobs_path,
                json.dumps(payload, indent=2),
                allow_identical=True,
                allow_overwrite=True,
            )
        except OSError:
            pass

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if sys.platform == "win32":
            windll = getattr(ctypes, "windll", None)
            if windll is None:
                return False
            handle = windll.kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            windll.kernel32.CloseHandle(handle)
            return True
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    @classmethod
    def _is_profile_in_use(cls, user_data_dir: Path) -> bool:
        """Check whether an active browser process currently owns the profile lock."""
        singleton_lock = user_data_dir / "SingletonLock"
        try:
            if singleton_lock.is_symlink():
                target = str(os.readlink(singleton_lock))
                m = re.search(r"-(\d+)$", target)
                if m and cls._is_pid_alive(int(m.group(1))):
                    return True
            elif singleton_lock.is_file():
                text = singleton_lock.read_text(encoding="utf-8", errors="ignore").strip()
                m = re.search(r"(\d+)$", text)
                if m and cls._is_pid_alive(int(m.group(1))):
                    return True
        except OSError:
            pass

        lock_file = user_data_dir / "lockfile"
        if lock_file.exists():
            try:
                text = lock_file.read_text(encoding="utf-8", errors="ignore").strip()
                if text.isdigit() and cls._is_pid_alive(int(text)):
                    return True
            except OSError:
                return True
            if sys.platform == "win32":
                # Windows holds an exclusive lock on active Chromium lockfile handles
                windll = getattr(ctypes, "windll", None)
                if windll is not None:
                    handle = windll.kernel32.CreateFileW(
                        str(lock_file), 0x80000000, 0, None, 3, 0x80, None
                    )
                    invalid = ctypes.c_void_p(-1).value
                    if handle == invalid:
                        return True
                    windll.kernel32.CloseHandle(handle)
        return False

    @classmethod
    def clean_stale_profile_lock(cls, user_data_dir: Path) -> bool:
        """Remove leftover Chromium lock artifacts ONLY when no live browser owns them."""
        if cls._is_profile_in_use(user_data_dir):
            return False
        cleaned = False
        for name in ("lockfile", "SingletonLock", "SingletonSocket", "SingletonCookie"):
            f = user_data_dir / name
            if f.exists() or f.is_symlink():
                try:
                    f.unlink(missing_ok=True)
                    cleaned = True
                except OSError:
                    pass
        return cleaned

    @staticmethod
    def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
        """Terminate worker subprocess and any spawned browser children safely."""
        try:
            if sys.platform == "win32" and proc.pid:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
            else:
                proc.terminate()
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    def start_job(
        self,
        *,
        user_data_dir: Path,
        snapshots_dir: Path,
        timeout_seconds: int = 180,
    ) -> SyncJob:
        """Start a new asynchronous sync job and return immediately."""
        with self._lock:
            # Cancel any already-running jobs to prevent profile lock collisions
            for j in self._jobs.values():
                if j.status in {"QUEUED", "RUNNING"}:
                    if j.proc:
                        self._terminate_process_tree(j.proc)
                    j.status = "CANCELLED"
                    j.completed_at = datetime.now(UTC).isoformat()

            self.clean_stale_profile_lock(user_data_dir)

            job_id = f"job_{uuid.uuid4().hex[:12]}"
            now_iso = datetime.now(UTC).isoformat()
            job = SyncJob(
                job_id=job_id,
                status="QUEUED",
                created_at=now_iso,
                timeout_seconds=timeout_seconds,
            )
            self._jobs[job_id] = job
            self._persist_jobs_locked()

            # Spawn worker thread
            worker_thread = threading.Thread(
                target=self._run_job_worker,
                args=(job, user_data_dir, snapshots_dir, timeout_seconds),
                daemon=True,
            )
            worker_thread.start()
            return job

    def get_job(self, job_id: str) -> SyncJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status not in {"QUEUED", "RUNNING"}:
                return False
            if job.proc:
                self._terminate_process_tree(job.proc)
            job.status = "CANCELLED"
            job.completed_at = datetime.now(UTC).isoformat()
            job.error_message = "Sync job was cancelled by user."
            self._persist_jobs_locked()
            return True

    def _run_job_worker(
        self,
        job: SyncJob,
        user_data_dir: Path,
        snapshots_dir: Path,
        timeout_seconds: int,
    ) -> None:
        with self._lock:
            job.status = "RUNNING"
            job.started_at = datetime.now(UTC).isoformat()
            self._persist_jobs_locked()

        cmd = [
            sys.executable,
            "-m",
            "bvmt.browser",
            "--user-data-dir",
            str(user_data_dir),
            "--snapshots-dir",
            str(snapshots_dir),
            "--timeout",
            str(timeout_seconds),
        ]

        try:
            creationflags = (
                getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if sys.platform == "win32" else 0
            )
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            with self._lock:
                job.proc = proc
            stdout, stderr = proc.communicate(timeout=timeout_seconds + 30)

            with self._lock:
                if str(job.status) == "CANCELLED":
                    self._persist_jobs_locked()
                    return

            if proc.returncode != 0:
                err_msg = (stderr or stdout or "Browser sync subprocess failed.").strip()
                with self._lock:
                    if "AuthenticationExpiredError:" in err_msg:
                        job.error_message = "Session expired or timed out. Please log in manually in the opened browser window."
                    elif "BalanceMismatchError:" in err_msg:
                        job.error_message = f"Portfolio balance mismatch: {err_msg.split('BalanceMismatchError:', 1)[-1].strip()}"
                    elif "LayoutChangedError:" in err_msg:
                        job.error_message = (
                            "Competition page layout changed. Table structure could not be parsed."
                        )
                    else:
                        job.error_message = err_msg
                    job.status = "FAILED"
                    job.completed_at = datetime.now(UTC).isoformat()
                    self._persist_jobs_locked()
                return

            # Success: parse JSON output from last line
            lines = stdout.strip().splitlines()
            payload = json.loads(lines[-1])
            snap_path = Path(str(payload["saved_path"]))
            snap_data = json.loads(snap_path.read_text(encoding="utf-8"))

            with self._lock:
                job.status = "COMPLETED"
                job.completed_at = datetime.now(UTC).isoformat()
                job.snapshot_path = snap_path.as_posix()
                job.snapshot_data = snap_data
                self._persist_jobs_locked()

        except subprocess.TimeoutExpired:
            with self._lock:
                if job.proc:
                    self._terminate_process_tree(job.proc)
                job.status = "FAILED"
                job.completed_at = datetime.now(UTC).isoformat()
                job.error_message = (
                    f"Browser synchronization timed out after {timeout_seconds} seconds."
                )
                self._persist_jobs_locked()
        except Exception as exc:
            with self._lock:
                job.status = "FAILED"
                job.completed_at = datetime.now(UTC).isoformat()
                job.error_message = str(exc)
                self._persist_jobs_locked()


# Global singleton job manager
global_job_manager = PlaywrightJobManager()
