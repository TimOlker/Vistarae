"""Unit tests for persistent in-memory cache and signal/crash persistence."""

import tempfile
from pathlib import Path

from photo_scraper.core.cache import PersistentCache, flush_all_caches


def test_persistent_cache_read_write():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "test_cache.json"
        cache = PersistentCache(str(cache_file))

        assert cache.get("geo:beijing") is None

        sample_data = {"lat": 39.9042, "lon": 116.4074, "name": "Beijing"}
        cache.set("geo:beijing", sample_data)

        # Should retrieve immediately from memory
        retrieved = cache.get("geo:beijing")
        assert retrieved == sample_data
        assert cache.is_dirty

        # Persist memory to disk
        cache.save()
        assert not cache.is_dirty

        # Reload new cache instance from same file
        cache2 = PersistentCache(str(cache_file))
        assert cache2.get("geo:beijing") == sample_data
        assert len(cache2) == 1


def test_in_memory_updates_and_flush_all_caches():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file1 = Path(tmpdir) / "gemini_cache.json"
        cache_file2 = Path(tmpdir) / "geo_cache.json"

        c1 = PersistentCache(str(cache_file1))
        c2 = PersistentCache(str(cache_file2))

        c1.set("path:china", {"country": "China", "city": "Beijing"})
        c2.set("osm:beijing", {"lat": 39.9, "lon": 116.4})

        # Memory updated, but files not yet written
        assert c1.is_dirty
        assert c2.is_dirty
        assert not cache_file1.exists()
        assert not cache_file2.exists()

        # Flush all active caches to disk (simulates stop/crash/signal trigger)
        flush_all_caches()

        assert not c1.is_dirty
        assert not c2.is_dirty
        assert cache_file1.exists()
        assert cache_file2.exists()

        # Verify disk contents on fresh load
        fresh1 = PersistentCache(str(cache_file1))
        assert fresh1.get("path:china") == {"country": "China", "city": "Beijing"}


def test_auto_save_interval():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "auto_save_cache.json"
        cache = PersistentCache(str(cache_file), auto_save_interval=3)

        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert not cache_file.exists()

        # 3rd entry reaches auto_save_interval threshold -> auto persists
        cache.set("k3", "v3")
        assert cache_file.exists()

        loaded = PersistentCache(str(cache_file))
        assert len(loaded) == 3
