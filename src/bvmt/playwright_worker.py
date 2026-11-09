"""Asynchronous job runner for the Playwright browser collector (Milestone 10, Phase 4).

Eliminates synchronous HTTP reverse-proxy timeouts by:
1. Spawning the browser collector in a managed background worker.
2. Returning a job_id immediately (HTTP 202 Accepted).
3. Allowing the client to poll job status via GET /api/sync/jobs/{job_id}.
4. Detecting and cleaning stale profile lockfiles to prevent collisions.
5. Providing structured job cancellation.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

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
    """In-memory thread-safe manager for Playwright background collection jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, SyncJob] = {}
        self._lock = threading.Lock()

    def clean_stale_profile_lock(self, user_data_dir: Path) -> bool:
        """Remove leftover lockfiles if no Chrome/Chromium process is running."""
        lock_file = user_data_dir / "lockfile"
        singleton_lock = user_data_dir / "SingletonLock"
        cleaned = False
        for f in (lock_file, singleton_lock):
            if f.exists():
                try:
                    f.unlink(missing_ok=True)
                    cleaned = True
                except Exception:
                    pass
        return cleaned

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
                if j.status == "RUNNING" and j.proc:
                    try:
                        j.proc.terminate()
                        j.status = "CANCELLED"
                    except Exception:
                        pass

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
                try:
                    job.proc.terminate()
                except Exception:
                    pass
            job.status = "CANCELLED"
            job.completed_at = datetime.now(UTC).isoformat()
            job.error_message = "Sync job was cancelled by user."
            return True

    def _run_job_worker(
        self,
        job: SyncJob,
        user_data_dir: Path,
        snapshots_dir: Path,
        timeout_seconds: int,
    ) -> None:
        job.status = "RUNNING"
        job.started_at = datetime.now(UTC).isoformat()

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
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            job.proc = proc
            stdout, stderr = proc.communicate(timeout=timeout_seconds + 30)

            with self._lock:
                if str(job.status) == "CANCELLED":
                    return

            if proc.returncode != 0:
                err_msg = (stderr or stdout or "Browser sync subprocess failed.").strip()
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
                return

            # Success: parse JSON output from last line
            lines = stdout.strip().splitlines()
            payload = json.loads(lines[-1])
            snap_path = Path(str(payload["saved_path"]))
            snap_data = json.loads(snap_path.read_text(encoding="utf-8"))

            job.status = "COMPLETED"
            job.completed_at = datetime.now(UTC).isoformat()
            job.snapshot_path = snap_path.as_posix()
            job.snapshot_data = snap_data

        except subprocess.TimeoutExpired:
            if job.proc:
                job.proc.kill()
            job.status = "FAILED"
            job.completed_at = datetime.now(UTC).isoformat()
            job.error_message = (
                f"Browser synchronization timed out after {timeout_seconds} seconds."
            )
        except Exception as exc:
            job.status = "FAILED"
            job.completed_at = datetime.now(UTC).isoformat()
            job.error_message = str(exc)


# Global singleton job manager
global_job_manager = PlaywrightJobManager()
