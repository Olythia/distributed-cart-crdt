import time
import threading


class CartCache:
    def __init__(self, ttl=2):
        self.ttl = ttl
        self.data = {}
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self.lock:
            entry = self.data.get(key)

            if entry is None:
                self.misses += 1
                return None

            value, expire_time = entry

            if time.monotonic() >= expire_time:
                del self.data[key]
                self.misses += 1
                return None

            self.hits += 1
            return value

    def set(self, key, value):
        with self.lock:
            self.data[key] = (
                value,
                time.monotonic() + self.ttl
            )

    def clear(self):
        with self.lock:
            self.data.clear()

    def stats(self):
        with self.lock:
            total = self.hits + self.misses

            return {
                "cache_entries": len(self.data),
                "cache_hits": self.hits,
                "cache_misses": self.misses,
                "hit_rate": round(
                    self.hits / total * 100, 2
                ) if total else 0,
                "ttl_seconds": self.ttl
            }

    def reset_stats(self):
        with self.lock:
            self.hits = 0
            self.misses = 0