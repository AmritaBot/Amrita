from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Any

from typing_extensions import Self


class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self) -> bool:
        """尝试消耗一个令牌，返回是否成功"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class BucketRepoitory:
    _instance = None
    _bucket: dict[str, defaultdict[Any, TokenBucket]]
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._bucket = {}
        return cls._instance

    def __init__(self, namespace: str, rate: int):
        self.namespace = namespace
        if namespace not in BucketRepoitory._bucket:
            with self._lock:
                BucketRepoitory._bucket[namespace] = defaultdict(
                    lambda: TokenBucket(rate=1 / rate, capacity=1)
                )

    def get_bucket(self, key: Any):
        with self._lock:
            return BucketRepoitory._bucket[self.namespace][key]


def get_bukkit(namespace: str, rate: int, key: Any) -> TokenBucket:
    return BucketRepoitory(namespace, rate).get_bucket(key)


if __name__ == "__main__":
    BucketRepoitory("test", 1).get_bucket("test")
