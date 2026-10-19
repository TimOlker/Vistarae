"""Thread-safe persistent cache with in-memory storage, periodic flush, and signal/crash persistence."""

import atexit
import json
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("vistarae.photo_scraper.cache")

_registry_lock = threading.Lock()
_active_caches: set["PersistentCache"] = set()
_global_handlers_installed = False
_original_signal_handlers: dict[int, Any] = {}
_original_excepthook = None


def register_cache(cache: "PersistentCache") -> None:
    """Registers a cache instance for global shutdown and signal flushing."""
    with _registry_lock:
        _active_caches.add(cache)
        _ensure_global_handlers()


def unregister_cache(cache: "PersistentCache") -> None:
    """Unregisters a cache instance."""
    with _registry_lock:
        _active_caches.discard(cache)


def flush_all_caches(force: bool = False) -> None:
    """Flushes all registered in-memory caches to disk if dirty."""
    with _registry_lock:
        for cache in list(_active_caches):
            try:
                cache.save(force=force)
            except Exception as e:
                logger.error(f"Error persisting cache '{cache.file_path}' to disk: {e}")


def _signal_handler(signum: int, frame: Any) -> None:
    """Handles OS termination signals (SIGINT, SIGTERM, SIGBREAK) by persisting in-memory caches."""
    try:
        sig_name = signal.Signals(signum).name
    except Exception:
        sig_name = str(signum)

    logger.warning(f"Received stop signal ({sig_name}). Saving updated in-memory caches to disk...")
    flush_all_caches()

    prev = _original_signal_handlers.get(signum)
    if callable(prev) and prev not in (signal.SIG_IGN, signal.SIG_DFL, _signal_handler):
        prev(signum, frame)
    else:
        sys.exit(128 + signum)


def _crash_excepthook(exc_type: type, exc_value: BaseException, exc_traceback: Any) -> None:
    """Handles uncaught application crashes by persisting in-memory caches before exiting."""
    logger.critical(
        f"Application crashed with unhandled exception ({exc_type.__name__}: {exc_value}). "
        "Saving updated in-memory caches to disk..."
    )
    flush_all_caches()
    if callable(_original_excepthook):
        _original_excepthook(exc_type, exc_value, exc_traceback)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def _ensure_global_handlers() -> None:
    """Installs process-level exit, crash, and signal handlers once."""
    global _global_handlers_installed, _original_excepthook
    if _global_handlers_installed:
        return
    _global_handlers_installed = True

    # 1. Register atexit handler (runs on normal termination or sys.exit)
    atexit.register(flush_all_caches)

    # 2. Register unhandled exception crash hook
    _original_excepthook = sys.excepthook
    sys.excepthook = _crash_excepthook

    # 3. Register OS signals in main thread
    if threading.current_thread() is threading.main_thread():
        signals_to_catch = [signal.SIGINT, signal.SIGTERM]
        if hasattr(signal, "SIGBREAK"):
            signals_to_catch.append(signal.SIGBREAK)
        if hasattr(signal, "SIGHUP"):
            signals_to_catch.append(signal.SIGHUP)

        for sig in signals_to_catch:
            try:
                _original_signal_handlers[sig] = signal.getsignal(sig)
                signal.signal(sig, _signal_handler)
            except Exception as err:
                logger.debug(f"Could not attach signal handler for {sig}: {err}")


class PersistentCache:
    """Manages thread-safe in-memory cache with atomic disk persistence.

    - Loads from disk at application startup.
    - Updates in memory as processing continues.
    - Persists to disk on application stop, crash, signal (SIGINT/SIGTERM/SIGBREAK),
      or periodic dirty threshold.
    """

    def __init__(
        self,
        cache_file_path: str | None = None,
        save_on_set: bool = False,
        auto_save_interval: int = 50,
    ):
        self.file_path = (
            Path(cache_file_path)
            if cache_file_path
            else Path(__file__).resolve().parent.parent / "output" / "photo_scraper_cache.json"
        )
        self.save_on_set = save_on_set
        self.auto_save_interval = auto_save_interval
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {}
        self._dirty = False
        self._dirty_count = 0
        self._load()
        register_cache(self)

    def _load(self) -> None:
        """Loads cache from disk into memory if the file exists."""
        if self.file_path.exists():
            try:
                with open(self.file_path, encoding="utf-8") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded {len(self._data)} entries from disk cache: {self.file_path}")
            except Exception as e:
                logger.warning(f"Could not load cache file ({e}). Starting with empty in-memory cache.")
                self._data = {}
        else:
            self._data = {}
        self._dirty = False
        self._dirty_count = 0

    def _save_to_disk(self) -> None:
        """Writes in-memory cache data to disk atomically."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.file_path)
            logger.info(
                f"Saved {len(self._data)} cache entries ({self._dirty_count} updated) "
                f"in memory to disk: {self.file_path}"
            )
        except Exception as e:
            logger.error(f"Failed to persist cache to disk '{self.file_path}': {e}")

    def save(self, force: bool = False) -> None:
        """Flushes in-memory cache to disk if modified or if forced."""
        with self._lock:
            if not self._dirty and not force:
                return
            self._save_to_disk()
            self._dirty = False
            self._dirty_count = 0

    def flush(self, force: bool = False) -> None:
        """Alias for save()."""
        self.save(force=force)

    def get(self, key: str) -> Any | None:
        """Retrieves an entry by key from in-memory cache."""
        with self._lock:
            val = self._data.get(key)
            if val is not None:
                logger.debug(f"MSG <-|  [CACHE HIT] Key='{key}'")
                return val
            logger.debug(f"MSG   |-> [CACHE MISS] Key='{key}'")
            return None

    def set(self, key: str, value: Any) -> None:
        """Updates cache in memory as processing continues and tracks dirty state."""
        with self._lock:
            self._data[key] = value
            self._dirty = True
            self._dirty_count += 1

            if self.save_on_set or (self.auto_save_interval and self._dirty_count >= self.auto_save_interval):
                self._save_to_disk()
                self._dirty = False
                self._dirty_count = 0

    @property
    def is_dirty(self) -> bool:
        """Returns True if there are unpersisted in-memory changes."""
        with self._lock:
            return self._dirty

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
