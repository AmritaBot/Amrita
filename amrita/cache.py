"""LRU缓存实现模块

该模块实现了基于OrderedDict的LRU（Least Recently Used）缓存，
支持字典-like的操作接口，并在缓存满时自动淘汰最久未使用的条目。
同时实现了TTL（Time To Live）和LFU（Least Frequently Used）缓存策略。

目前这个模块看起来并没有使用，但是在Amrita的未来的重构计划中将作为重要的一环。
"""

from __future__ import annotations

import time
import weakref
from collections import OrderedDict
from collections.abc import Generator, Hashable, Iterator
from typing import Any, Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")
T = TypeVar("T")


class LRUCache(Generic[K, V]):
    """LRU缓存实现，基于OrderedDict实现

    该缓存具有固定容量，当添加新条目导致缓存满时，
    会自动删除最久未使用的条目（Least Recently Used）。
    """

    __marker = object()

    def __init__(self, capacity: int):
        """初始化LRU缓存

        Args:
            capacity: 缓存的最大容量
        """
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self._capacity = capacity
        self._cache: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        """获取缓存中的值，如果存在则将其标记为最近使用

        Args:
            key: 要获取的键

        Returns:
            键对应的值，如果键不存在则返回None
        """
        if key not in self._cache:
            return None

        # 将访问的键移到末尾（标记为最近使用）
        value = self._cache.pop(key)
        self._cache[key] = value
        return value

    def put(self, key: K, value: V) -> None:
        """向缓存中添加或更新键值对

        如果键已存在，则更新其值并标记为最近使用。
        如果键不存在且缓存已满，则删除最久未使用的条目后再添加。

        Args:
            key: 要添加的键
            value: 要添加的值
        """
        if key in self._cache:
            # 如果键已存在，先删除它以便移到末尾
            self._cache.pop(key)
        elif len(self._cache) >= self._capacity:
            # 如果缓存已满，删除最久未使用的项（第一个）
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key)

        # 添加新的键值对到末尾（标记为最近使用）
        self._cache[key] = value

    def __getitem__(self, key: K) -> V:
        """支持字典风格的取值操作

        Args:
            key: 要获取的键

        Returns:
            键对应的值

        Raises:
            KeyError: 当键不存在时抛出
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        """支持字典风格的赋值操作

        Args:
            key: 要设置的键
            value: 要设置的值
        """
        self.put(key, value)

    def __delitem__(self, key: K) -> None:
        """支持删除操作

        Args:
            key: 要删除的键

        Raises:
            KeyError: 当键不存在时抛出
        """
        if key not in self._cache:
            raise KeyError(key)
        del self._cache[key]

    def __contains__(self, key: K) -> bool:
        """支持in操作符

        Args:
            key: 要检查的键

        Returns:
            如果键存在于缓存中则返回True，否则返回False
        """
        return key in self._cache

    def __len__(self) -> int:
        """返回缓存中的条目数量

        Returns:
            缓存中键值对的数量
        """
        return len(self._cache)

    def __iter__(self) -> Iterator[K]:
        """支持迭代操作，返回键的迭代器

        Returns:
            键的迭代器，按使用顺序排列（最近使用的在后）
        """
        return iter(self._cache)

    def keys(self):
        """返回键的迭代器

        Returns:
            键的迭代器
        """
        return self._cache.keys()

    def values(self):
        """返回值的迭代器

        Returns:
            值的迭代器，按使用顺序排列（最近使用的在后）
        """
        return self._cache.values()

    def items(self):
        """返回键值对的迭代器

        Returns:
            键值对的迭代器，按使用顺序排列（最近使用的在后）
        """
        return self._cache.items()

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def capacity(self) -> int:
        """获取缓存容量

        Returns:
            缓存的最大容量
        """
        return self._capacity

    def size(self) -> int:
        """获取当前缓存大小

        Returns:
            当前缓存中的条目数量
        """
        return len(self._cache)

    def is_full(self) -> bool:
        """检查缓存是否已满

        Returns:
            如果缓存已满则返回True，否则返回False
        """
        return len(self._cache) >= self._capacity

    def pop(self, key: K, default: T = __marker) -> V | T:
        """从缓存中删除指定键的条目并返回其值
        如果指定键不存在，则抛出异常

        """
        if default is self.__marker:
            return self._cache.pop(key)
        else:
            return self._cache.pop(key, default)

    def resize(self, new_size: int):
        """调整缓存大小"""
        self._capacity = new_size

    def __repr__(self) -> str:
        """返回缓存的字符串表示

        Returns:
            缓存内容的字符串表示
        """
        items = [f"{k!r}: {v!r}" for k, v in self._cache.items()]
        return f"{self.__class__.__name__}(capacity={self._capacity}, items={{{', '.join(items)}}})"


class WeakValueLRUCache(Generic[K, V]):
    """弱引用值的LRU缓存实现，基于weakref和OrderedDict实现

    该缓存使用弱引用来存储值，当值被垃圾回收后，对应的缓存条目会自动失效。
    通常来说用于动态锁池的设计。
    """

    __marker = object()
    _capacity: int
    _cache: OrderedDict[K, weakref.ReferenceType[V]]
    _loose_mode: bool

    def __init__(self, capacity: int, loose_mode: bool = False):
        """初始化弱引用LRU缓存

        Args:
            capacity: 缓存的最大容量
            loose_mode: 即使超出容量，也允许缓存新的值（不释放所有有效项）
        """
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self._capacity = capacity
        self._loose_mode = loose_mode
        self._cache: OrderedDict[K, weakref.ref[V]] = OrderedDict()

    def _cleanup_key_if_expired(self, key: K) -> bool:
        """清理指定键（如果已过期）

        Args:
            key: 要检查的键

        Returns:
            如果键存在且有效则返回True，否则返回False
        """
        if key not in self._cache:
            return False

        weak_ref = self._cache[key]
        if weak_ref() is None:
            # 值已被GC，清理并返回False
            self._cache.pop(key, None)
            return False
        return True

    def resize(self, new_size: int):
        """调整缓存大小"""
        self._capacity = new_size

    def get(self, key: K) -> V | None:
        """获取缓存中的值，如果存在且未被GC则将其标记为最近使用

        Args:
            key: 要获取的键

        Returns:
            键对应的值，如果键不存在或值已被GC则返回None
        """
        # 只检查当前访问的键，不遍历整个缓存
        if key not in self._cache:
            return None

        weak_ref = self._cache[key]
        value = weak_ref()

        if value is None:
            # 值已被GC，清理并返回None
            self._cache.pop(key, None)
            return None

        # 将访问的键移到末尾（标记为最近使用）
        self._cache.pop(key)
        self._cache[key] = weak_ref
        return value

    def put(self, key: K, value: V) -> None:
        """向缓存中添加或更新键值对（使用弱引用）

        如果键已存在，则更新其弱引用并标记为最近使用。
        如果键不存在且缓存已满，则删除最久未使用的条目后再添加。
        注意：传入的value不能是None，因为weakref不支持None

        Args:
            key: 要添加的键
            value: 要添加的值（不能为None）
        """
        if value is None:
            raise ValueError("Cannot store None value in WeakValueLRUCache")

        weak_ref = weakref.ref(value)

        if key in self._cache:
            self._cache.pop(key)
        else:
            should_expire_count = max(0, (len(self._cache) + 1) - self._capacity)
            collected = 0
            for _ in range(len(self._cache)):
                if collected >= should_expire_count:
                    break
                oldest_key: K = next(iter(self._cache))
                oldest_ref = self._cache[oldest_key]
                if (
                    oldest_ref() is None or not self._loose_mode
                ):  # 缓存对象被回收或`非添加宽松`模式下
                    collected += 1
                    self._cache.pop(oldest_key)
                elif self._loose_mode:
                    self._cache.move_to_end(oldest_key)

        self._cache[key] = weak_ref

    def expire(self, length: int | None = None) -> None:
        """手动触发过期检查，清理已被GC的条目

        只清理队列前面的一部分项（利用LRU特性，访问少的项更可能已过期）
        """
        if length is None:
            length = int(len(self._cache) * (1 / 5))
        keys_to_check = list(self._cache.keys())[: min(length, len(self._cache))]
        expired_keys = [key for key in keys_to_check if self._cache[key]() is None]

        for key in expired_keys:
            self._cache.pop(key, None)

    def __getitem__(self, key: K) -> V:
        """支持字典风格的取值操作

        Args:
            key: 要获取的键

        Returns:
            键对应的值

        Raises:
            KeyError: 当键不存在或值已被GC时抛出
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        """支持字典风格的赋值操作

        Args:
            key: 要设置的键
            value: 要设置的值
        """
        self.put(key, value)

    def __delitem__(self, key: K) -> None:
        """支持删除操作

        Args:
            key: 要删除的键

        Raises:
            KeyError: 当键不存在时抛出
        """
        if key not in self._cache:
            raise KeyError(key)
        del self._cache[key]

    def __contains__(self, key: K) -> bool:
        """支持in操作符

        Args:
            key: 要检查的键

        Returns:
            如果键存在于缓存中且值未被GC则返回True，否则返回False
        """
        if key not in self._cache:
            return False
        return self._cache[key]() is not None

    def __len__(self) -> int:
        """返回缓存中所有个键值对的数量

        Returns:
            缓存中键值对的数量
        """
        return len(self._cache)

    def __iter__(self) -> Iterator[K]:
        """支持迭代操作，返回有效键的迭代器

        Returns:
            有效键的迭代器，按使用顺序排列（最近使用的在后）
        """
        for key in list(self._cache.keys()):
            if self._cleanup_key_if_expired(key):
                yield key

    def keys(self):
        """返回有效键的迭代器

        Returns:
            有效键的迭代器
        """
        return self.__iter__()

    def values(self):
        """返回有效值的迭代器

        Returns:
            有效值的迭代器，按使用顺序排列（最近使用的在后）
        """
        for _, value in self.items():  # noqa: PERF102
            yield value

    def items(self) -> Generator[tuple[K, V], Any, None]:
        """返回有效键值对的迭代器

        Returns:
            有效键值对的迭代器，按使用顺序排列（最近使用的在后）
        """
        for key, weak_ref in list(self._cache.items()):
            if self._cleanup_key_if_expired(key):
                value = weak_ref()
                assert value is not None
                yield key, value

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def capacity(self) -> int:
        """获取缓存容量

        Returns:
            缓存的最大容量
        """
        return self._capacity

    def size(self) -> int:
        """获取当前有效缓存大小

        Returns:
            当前缓存中有效条目的数量
        """
        t = 0
        for i in self._cache.values():
            if i() is not None:
                t += 1
        return t

    def is_full(self) -> bool:
        """检查缓存是否已满（基于实际条目数，不考虑是否过期）

        Returns:
            如果条目数量达到容量则返回True，否则返回False
        """
        return len(self._cache) >= self._capacity

    def pop(self, key: K, default: T = __marker) -> V | T:
        """从缓存中删除指定键的条目并返回其值

        Args:
            key: 要删除的键
            default: 默认值（可选）

        Returns:
            键对应的值，如果键不存在或值已被GC则返回default或抛出异常
        """
        if key not in self._cache:
            if default is self.__marker:
                raise KeyError(key)
            return default

        weak_ref = self._cache.pop(key)
        value = weak_ref()
        if value is None:
            if default is self.__marker:
                raise KeyError(key)
            return default
        return value

    def __repr__(self) -> str:
        """返回缓存的字符串表示（只显示有效条目）

        Returns:
            缓存内容的字符串表示
        """
        items = []
        for k, weak_ref in self._cache.items():
            v = weak_ref()
            if v is not None:
                items.append(f"{k!r}: {v!r}")
        return f"{self.__class__.__name__}(capacity={self._capacity}, items={{{', '.join(items)}}})"


class TTLCache(Generic[K, V]):
    """TTL缓存实现（Time To Live）

    该缓存为每个条目设置生存时间，超过时间后自动失效。
    """

    def __init__(self, capacity: int, ttl: float):
        """初始化TTL缓存

        Args:
            capacity: 缓存的最大容量
            ttl: 条目的生存时间（秒）
        """
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        if ttl <= 0:
            raise ValueError("TTL must be a positive number")

        self._capacity = capacity
        self._ttl = ttl
        self._cache: dict[K, tuple[V, float]] = {}  # (value, expire_time)

    def _is_expired(self, expire_time: float) -> bool:
        """检查条目是否已过期

        Args:
            expire_time: 条目的过期时间

        Returns:
            如果已过期返回True，否则返回False
        """
        return time.time() > expire_time

    def _remove_expired(self) -> None:
        """移除所有已过期的条目"""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, expire_time) in self._cache.items()
            if current_time > expire_time
        ]
        for key in expired_keys:
            del self._cache[key]

    def resize(self, new_size: int):
        """调整缓存大小"""
        self._capacity = new_size

    def get(self, key: K) -> V | None:
        """获取缓存中的值，如果存在且未过期则返回，否则返回None

        Args:
            key: 要获取的键

        Returns:
            键对应的值，如果键不存在或已过期则返回None
        """
        self._remove_expired()

        if key not in self._cache:
            return None

        value, expire_time = self._cache[key]

        if self._is_expired(expire_time):
            del self._cache[key]
            return None

        return value

    def put(self, key: K, value: V) -> None:
        """向缓存中添加或更新键值对

        如果缓存已满，会删除一个过期条目或最老的条目。

        Args:
            key: 要添加的键
            value: 要添加的值
        """
        self._remove_expired()

        # 如果缓存已满，删除一个条目
        if len(self._cache) >= self._capacity:
            # 删除最老的条目
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        # 添加新的键值对，设置过期时间
        expire_time = time.time() + self._ttl
        self._cache[key] = (value, expire_time)

    def __getitem__(self, key: K) -> V:
        """支持字典风格的取值操作

        Args:
            key: 要获取的键

        Returns:
            键对应的值

        Raises:
            KeyError: 当键不存在或已过期时抛出
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        """支持字典风格的赋值操作

        Args:
            key: 要设置的键
            value: 要设置的值
        """
        self.put(key, value)

    def __delitem__(self, key: K) -> None:
        """支持删除操作

        Args:
            key: 要删除的键

        Raises:
            KeyError: 当键不存在时抛出
        """
        if key not in self._cache:
            raise KeyError(key)
        del self._cache[key]

    def __contains__(self, key: K) -> bool:
        """支持in操作符

        Args:
            key: 要检查的键

        Returns:
            如果键存在于缓存中且未过期则返回True，否则返回False
        """
        self._remove_expired()
        return key in self._cache

    def __len__(self) -> int:
        """返回缓存中的条目数量

        Returns:
            缓存中未过期键值对的数量
        """
        self._remove_expired()
        return len(self._cache)

    def __iter__(self) -> Iterator[K]:
        """支持迭代操作，返回键的迭代器

        Returns:
            键的迭代器
        """
        self._remove_expired()
        return iter(self._cache)

    def keys(self):
        """返回键的迭代器

        Returns:
            键的迭代器
        """
        self._remove_expired()
        return self._cache.keys()

    def values(self):
        """返回值的迭代器

        Returns:
            值的迭代器
        """
        self._remove_expired()
        return [value for value, _ in self._cache.values()]

    def items(self):
        """返回键值对的迭代器

        Returns:
            键值对的迭代器
        """
        self._remove_expired()
        return ((key, value) for key, (value, _) in self._cache.items())

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def capacity(self) -> int:
        """获取缓存容量

        Returns:
            缓存的最大容量
        """
        return self._capacity

    def size(self) -> int:
        """获取当前缓存大小

        Returns:
            当前缓存中的条目数量
        """
        self._remove_expired()
        return len(self._cache)

    def ttl(self) -> float:
        """获取TTL值

        Returns:
            条目的生存时间（秒）
        """
        return self._ttl

    def is_full(self) -> bool:
        """检查缓存是否已满

        Returns:
            如果缓存已满则返回True，否则返回False
        """
        self._remove_expired()
        return len(self._cache) >= self._capacity

    def __repr__(self) -> str:
        """返回缓存的字符串表示

        Returns:
            缓存内容的字符串表示
        """
        self._remove_expired()
        items = [f"{k!r}: {v!r}" for k, (v, _) in self._cache.items()]
        return f"{self.__class__.__name__}(capacity={self._capacity}, ttl={self._ttl}, items={{{', '.join(items)}}})"


class LFUCache(Generic[K, V]):
    """LFU缓存实现（Least Frequently Used）

    该缓存根据访问频率淘汰条目，保留访问频率最高的条目。
    """

    def __init__(self, capacity: int):
        """初始化LFU缓存

        Args:
            capacity: 缓存的最大容量
        """
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")

        self._capacity = capacity
        self._cache: dict[K, tuple[V, int]] = {}  # (value, frequency)

    def get(self, key: K) -> V | None:
        """获取缓存中的值，如果存在则增加其访问频率

        Args:
            key: 要获取的键

        Returns:
            键对应的值，如果键不存在则返回None
        """
        if key not in self._cache:
            return None

        value, freq = self._cache[key]
        # 增加访问频率
        self._cache[key] = (value, freq + 1)
        return value

    def resize(self, new_size: int):
        """调整缓存大小"""
        self._capacity = new_size

    def put(self, key: K, value: V) -> None:
        """向缓存中添加或更新键值对

        如果缓存已满，会删除访问频率最低的条目。

        Args:
            key: 要添加的键
            value: 要添加的值
        """
        if key in self._cache:
            # 如果键已存在，更新值并增加频率
            _, old_freq = self._cache[key]
            self._cache[key] = (value, old_freq + 1)
        else:
            # 如果缓存已满，删除访问频率最低的条目
            if len(self._cache) >= self._capacity:
                least_freq_key = min(
                    self._cache.keys(), key=lambda k: self._cache[k][1]
                )
                del self._cache[least_freq_key]

            # 添加新的键值对，初始频率为1
            self._cache[key] = (value, 1)

    def __getitem__(self, key: K) -> V:
        """支持字典风格的取值操作

        Args:
            key: 要获取的键

        Returns:
            键对应的值

        Raises:
            KeyError: 当键不存在时抛出
        """
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: K, value: V) -> None:
        """支持字典风格的赋值操作

        Args:
            key: 要设置的键
            value: 要设置的值
        """
        self.put(key, value)

    def __delitem__(self, key: K) -> None:
        """支持删除操作

        Args:
            key: 要删除的键

        Raises:
            KeyError: 当键不存在时抛出
        """
        if key not in self._cache:
            raise KeyError(key)
        del self._cache[key]

    def __contains__(self, key: K) -> bool:
        """支持in操作符

        Args:
            key: 要检查的键

        Returns:
            如果键存在于缓存中则返回True，否则返回False
        """
        return key in self._cache

    def __len__(self) -> int:
        """返回缓存中的条目数量

        Returns:
            缓存中键值对的数量
        """
        return len(self._cache)

    def __iter__(self) -> Iterator[K]:
        """支持迭代操作，返回键的迭代器

        Returns:
            键的迭代器
        """
        return iter(self._cache)

    def keys(self):
        """返回键的迭代器

        Returns:
            键的迭代器
        """
        return self._cache.keys()

    def values(self):
        """返回值的迭代器

        Returns:
            值的迭代器
        """
        return [value for value, _ in self._cache.values()]

    def items(self):
        """返回键值对的迭代器

        Returns:
            键值对的迭代器
        """
        return ((key, value) for key, (value, _) in self._cache.items())

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def capacity(self) -> int:
        """获取缓存容量

        Returns:
            缓存的最大容量
        """
        return self._capacity

    def size(self) -> int:
        """获取当前缓存大小

        Returns:
            当前缓存中的条目数量
        """
        return len(self._cache)

    def frequency(self, key: K) -> int | None:
        """获取指定键的访问频率

        Args:
            key: 要查询的键

        Returns:
            键的访问频率，如果键不存在则返回None
        """
        if key not in self._cache:
            return None
        _, freq = self._cache[key]
        return freq

    def is_full(self) -> bool:
        """检查缓存是否已满

        Returns:
            如果缓存已满则返回True，否则返回False
        """
        return len(self._cache) >= self._capacity

    def __repr__(self) -> str:
        """返回缓存的字符串表示

        Returns:
            缓存内容的字符串表示
        """
        items = [f"{k!r}: {v!r}" for k, (v, _) in self._cache.items()]
        return f"{self.__class__.__name__}(capacity={self._capacity}, items={{{', '.join(items)}}})"
