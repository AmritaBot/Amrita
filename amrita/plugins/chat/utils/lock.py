from collections.abc import Hashable

import aiologic

from amrita.cache import WeakValueLRUCache

_group_lock: WeakValueLRUCache[Hashable, aiologic.Lock] = WeakValueLRUCache(
    capacity=1024, loose_mode=True
)
_private_lock: WeakValueLRUCache[Hashable, aiologic.Lock] = WeakValueLRUCache(
    capacity=1024, loose_mode=True
)
_database_lock: WeakValueLRUCache[Hashable, aiologic.Lock] = WeakValueLRUCache(
    capacity=2048, loose_mode=True
)


def get_group_lock(id: int) -> aiologic.Lock:
    if (lock := _group_lock.get(id)) is None:
        lock = aiologic.Lock()
        _group_lock.put(id, lock)
    return lock


def get_private_lock(id: int) -> aiologic.Lock:
    if (lock := _private_lock.get(id)) is None:
        lock = aiologic.Lock()
        _private_lock.put(id, lock)
    return lock


def database_lock(*args: Hashable) -> aiologic.Lock:
    if (lock := _database_lock.get(args)) is None:
        lock = aiologic.Lock()
        _database_lock.put(args, lock)
    return lock
