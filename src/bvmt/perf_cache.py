"""Thread-safe, content-fingerprinted in-memory caches for local BVMT research and API reads.

Design invariants:
- Never return stale account, snapshot, or market data after any file changes on disk.
- Every cache key captures resolved paths plus cryptographic fingerprints (`sha256` for
  small mutable files such as ledgers, snapshots, configs, and alerts; `(size, mtime_ns,
  sha256)` for large canonical market CSVs) and an explicit generation counter incremented by
  `invalidate_all_caches()` after any mutation or refresh.
- Callers receiving sequences (`list[...]`) always receive shallow copies from cached immutable
  tuples so downstream sorting or filtering never mutates cached entries.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path

_SMALL_FILE_HASH_THRESHOLD_BYTES = 524_288
_CACHE_LOCK = threading.RLock()
_CACHE_GENERATION = 0
_LARGE_FILE_SHA_CACHE: OrderedDict[tuple[str, int, int], str] = OrderedDict()


def sha256_bytes_hex(path: Path) -> str:
    """Compute SHA-256 hex digest of a file using buffered reads."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_fingerprint(path: Path | None) -> tuple[str, int, int, str] | None:
    """Return `(resolved_path, size, mtime_ns, sha256)` or `None` if missing."""
    if path is None:
        return None
    try:
        st = path.stat()
    except OSError:
        return None
    resolved = str(path.resolve())
    # Metadata is not content identity: same-size rewrites with restored mtime
    # must invalidate validated CSVs and every downstream research cache.
    sha = sha256_bytes_hex(path)
    return (resolved, st.st_size, st.st_mtime_ns, sha)


def dir_files_fingerprint(directory: Path, pattern: str = "sync_*.json") -> tuple[object, ...]:
    """Fingerprint every file matching `pattern` inside `directory`."""
    if not directory.is_dir():
        return (str(directory), False)
    items: list[object] = []
    for path in sorted(directory.glob(pattern), reverse=True):
        fp = file_fingerprint(path)
        items.append((path.name, fp))
    return tuple(items)


def processed_datasets_fingerprint(processed_root: Path) -> tuple[object, ...]:
    """Fingerprint sibling processed dataset CSVs under `processed_root`."""
    if not processed_root.is_dir():
        return (str(processed_root), False)
    entries: list[object] = []
    for sub in sorted(processed_root.iterdir()):
        if not sub.is_dir():
            continue
        csv_path = sub / "daily_bars.canonical.csv"
        if csv_path.is_file():
            try:
                entries.append(file_fingerprint(csv_path))
            except OSError:
                continue
    return tuple(entries)


class BoundedLruCache[K, V]:
    """Thread-safe bounded LRU cache with hit/miss counters."""

    def __init__(self, max_entries: int = 16) -> None:
        self._max_entries = max(1, max_entries)
        self._entries: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key: K) -> V | None:
        with self._lock:
            val = self._entries.get(key)
            if val is None:
                self.misses += 1
                return None
            self._entries.move_to_end(key)
            self.hits += 1
            return val

    def set(self, key: K, value: V) -> V:
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            return value

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_REGISTERED_CACHES: list[BoundedLruCache[object, object]] = []


def register_cache(cache: BoundedLruCache[object, object]) -> None:
    """Register a module cache for global invalidation."""
    with _CACHE_LOCK:
        _REGISTERED_CACHES.append(cache)


def get_cache_generation() -> int:
    with _CACHE_LOCK:
        return _CACHE_GENERATION


def invalidate_all_caches() -> int:
    """Clear all registered caches and bump generation atomically."""
    global _CACHE_GENERATION
    with _CACHE_LOCK:
        _CACHE_GENERATION += 1
        _LARGE_FILE_SHA_CACHE.clear()
        for cache in _REGISTERED_CACHES:
            cache.clear()
        return _CACHE_GENERATION


def clear_caches(caches: Iterable[BoundedLruCache[object, object]]) -> None:
    for cache in caches:
        cache.clear()
