import asyncio
from abc import ABC
from asyncio import Lock, Task
from collections import defaultdict
from collections.abc import Awaitable, Callable
from io import StringIO
from pathlib import Path
from typing import Generic, TypeVar

import aiofiles
import tomli
import tomli_w
import watchfiles
from nonebot import logger
from nonebot_plugin_localstore import _try_get_caller_plugin, get_config_dir
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

CALLBACK_TYPE = Callable[[str, Path], Awaitable]
FILTER_TYPE = Callable[[watchfiles.main.FileChange], bool]


class BaseDataStorage(ABC, Generic[T]):
    """
    基础数据存储抽象类

    为插件提供基础的数据存储功能抽象基类，确保子类实现必要的方法。
    使用单例模式确保每个子类只有一个实例。

    泛型参数:
        T: BaseModel的子类，表示具体的配置模型类型
    """

    _instance = None
    config: T
    config_class: type[T]

    def __new__(cls, *args, **kwargs):
        """
        实现单例模式，确保每个子类只有一个实例

        Returns:
            BaseDataStorage: 类实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls.__init_subclass__()
        return cls._instance

    @classmethod
    def __init_classvars__(cls) -> None:
        """初始化类变量"""
        ...

    def _config_on_reload(self) -> CALLBACK_TYPE:
        """
        返回一个回调函数，用于处理配置文件重载事件

        Returns:
            CALLBACK_TYPE: 配置重载回调函数
        """

        async def callback(owner_name: str, path: Path):
            """
            配置重载回调函数

            Args:
                owner_name (str): 拥有者名称
                path (Path): 配置文件路径
            """
            self.config = await UniConfigManager().get_config_by_class(
                self.config_class
            )
            logger.debug(f"{owner_name} config reloaded")

        return callback


class UniConfigManager(Generic[T]):
    """
    为Amrita/NoneBot插件设计的统一配置管理器

    提供配置文件管理、热重载、文件监控等功能，支持插件的配置管理需求。
    使用单例模式确保全局唯一实例。
    """

    _instance = None
    _lock: defaultdict[str, Lock]
    _callback_lock: defaultdict[str, Lock]
    _file_callback_map: dict[Path, CALLBACK_TYPE]
    _config_classes: dict[str, type[T]]
    _config_classes_id_to_config: dict[
        int, tuple[str, type[T]]
    ]  # id(class) -> (owner_name, class)
    _config_other_files: dict[str, set[Path]]
    _config_directories: dict[str, set[Path]]
    _config_file_cache: dict[str, StringIO]  # Path -> StringIO
    _config_instances: dict[str, T]
    _tasks: list[Task]

    def __new__(cls, *args, **kwargs):
        """
        实现单例模式，确保UniConfigManager全局唯一

        Returns:
            UniConfigManager: 类实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config_classes = {}
            cls._config_other_files = defaultdict(set)
            cls._config_instances = {}
            cls._config_directories = defaultdict(set)
            cls._lock = defaultdict(Lock)
            cls._callback_lock = defaultdict(Lock)
            cls._config_file_cache = {}
            cls._config_classes_id_to_config = {}
            cls._tasks = []
        return cls._instance

    def __del__(self):
        """
        析构函数，清理任务资源
        """
        self._clean_tasks()

    async def add_config(
        self,
        config_class: type[T],
        init_now: bool = True,
        watch: bool = True,
        owner_name: str | None = None,
        on_reload: CALLBACK_TYPE | None = None,
    ):
        """
        添加配置类

        Args:
            config_class (type[T]): 配置类
            init_now (bool, optional): 是否立即初始化. 默认为True
            watch (bool, optional): 是否监控配置文件变更. 默认为True
            owner_name (str | None, optional): 拥有者名称. 默认为None
            on_reload (CALLBACK_TYPE | None, optional): 重载回调函数. 默认为None
        """
        owner_name = owner_name or _try_get_caller_plugin().name
        logger.debug(f"`{owner_name}` add config `{config_class.__name__}`")
        config_dir = get_config_dir(owner_name)
        async with self._lock[owner_name]:
            if owner_name in self._config_classes:
                raise ValueError(
                    f"`{owner_name}` has already registered a config class"
                )
            self._config_classes[owner_name] = config_class
            self._config_classes_id_to_config[id(config_class)] = (
                owner_name,
                config_class,
            )
        if init_now:
            await self._init_config_or_nothing(owner_name, config_dir)
        if watch:
            callbacks = (
                self._config_reload_callback,
                *((on_reload,) if on_reload else ()),
            )
            await self._add_watch_path(
                owner_name,
                config_dir / "config.toml",
                lambda change: Path(change[1]).name == "config.toml",
                *callbacks,
            )

    async def add_file(
        self, name: str, data: str, watch=True, owner_name: str | None = None
    ):
        """
        添加文件

        Args:
            name (str): 文件名
            data (str): 文件内容
            watch (bool, optional): 是否监控文件变更. 默认为True
            owner_name (str | None, optional): 拥有者名称. 默认为None
        """
        owner_name = owner_name or _try_get_caller_plugin().name
        config_dir = get_config_dir(owner_name)
        file_path = (config_dir / name).resolve()
        logger.info(f"`{owner_name}` added a file named `{name}`")
        if not file_path.exists():
            async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
                await f.write(data)
            async with self._lock[owner_name]:
                self._config_other_files[owner_name].add(file_path)
                str_io = StringIO()
                str_io.write(data)
                self._config_file_cache[owner_name] = str_io
        if watch:
            await self._add_watch_path(
                owner_name,
                config_dir,
                lambda change: Path(change[1]).name == name,
                self._file_reload_callback,
            )

    async def add_directory(
        self,
        name: str,
        callback: CALLBACK_TYPE,
        filter: FILTER_TYPE | None = None,
        watch=True,
        owner_name: str | None = None,
    ):
        """
        添加目录监视

        Args:
            name (str): 目录名
            callback (CALLBACK_TYPE): 回调函数
            filter (FILTER_TYPE | None, optional): 过滤函数. 默认为None
            watch (bool, optional): 是否监控目录变更. 默认为True
            owner_name (str | None, optional): 拥有者名称. 默认为None
        """
        owner_name = owner_name or _try_get_caller_plugin().name
        config_dir = get_config_dir(owner_name)
        target_path = config_dir / name
        logger.debug(f"`{owner_name}` added a directory: `{name}`")
        if not target_path.exists():
            target_path.mkdir(parents=True, exist_ok=True)
        async with self._lock[owner_name]:
            self._config_directories[owner_name].add(target_path)
        if watch:

            def default_filter(change: watchfiles.main.FileChange):
                """
                默认过滤函数

                Args:
                    change (watchfiles.main.FileChange): 文件变更信息

                Returns:
                    bool: 是否通过过滤
                """
                if not change[1].startswith(str(target_path)):
                    return False

                return int(change[0]) in (
                    watchfiles.Change.modified.value,
                    watchfiles.Change.added.value,
                    watchfiles.Change.deleted.value,
                )

            final_filter = filter or default_filter

            await self._add_watch_path(
                owner_name,
                target_path,
                final_filter,
                callback,
            )

    async def get_config_by_class(self, config_class: type[T]) -> T:
        """
        根据配置类获取配置实例

        Args:
            config_class (type[T]): 配置类泛型

        Returns:
            T: 配置实例
        """
        class_id = id(config_class)
        async with self._lock[str(class_id)]:
            owner_name, _ = self._config_classes_id_to_config[class_id]
            async with self._lock[owner_name]:
                config_dir = get_config_dir(owner_name)
                await self._init_config_or_nothing(owner_name, config_dir)
                return self._config_instances[owner_name]

    async def get_config(self, plugin_name: str | None = None) -> T:
        """
        获取配置实例

        Args:
            plugin_name (str | None, optional): 插件名称. 默认为None

        Returns:
            T: 配置实例
        """
        plugin_name = plugin_name or _try_get_caller_plugin().name
        return self._config_instances.get(
            plugin_name
        ) or await self._get_config_by_file(plugin_name)

    async def get_config_class(self, plugin_name: str | None = None) -> type[T]:
        """
        获取配置类

        Args:
            plugin_name (str | None, optional): 插件名称. 默认为None

        Returns:
            type[T]: 配置类
        """
        return self._config_classes[plugin_name or (_try_get_caller_plugin().name)]

    async def reload_config(self, owner_name: str | None = None):
        """
        重新加载配置

        Args:
            owner_name (str | None, optional): 拥有者名称. 默认为None
        """
        owner_name = owner_name or _try_get_caller_plugin().name
        await self._get_config_by_file(owner_name)

    async def loads_config(self, instance: T, owner_name: str | None = None):
        """
        加载配置实例

        Args:
            instance (T): 配置实例
            owner_name (str | None, optional): 拥有者名称. 默认为None
        """
        owner_name = owner_name or _try_get_caller_plugin().name
        async with self._lock[owner_name]:
            self._config_instances[owner_name] = instance

    async def save_config(self, owner_name: str | None = None):
        """
        保存配置

        Args:
            owner_name (str | None, optional): 拥有者名称. 默认为None
        """
        owner_name = owner_name or _try_get_caller_plugin().name
        config_dir = get_config_dir(owner_name)
        async with self._lock[owner_name]:
            async with aiofiles.open(
                config_dir / "config.toml", mode="w", encoding="utf-8"
            ) as f:
                await f.write(
                    tomli_w.dumps(self._config_instances[owner_name].model_dump())
                )

    def get_config_classes(self) -> dict[str, type[T]]:
        """
        获取所有已注册的配置类

        Returns:
            dict[str, type[T]]: 插件名到配置类的映射
        """
        return self._config_classes

    def get_config_instances(self) -> dict[str, T]:
        """
        获取所有配置实例

        Returns:
            dict[str, T]: 插件名到配置实例的映射
        """
        return self._config_instances

    def has_config_class(self, plugin_name: str) -> bool:
        """
        检查是否存在指定插件的配置类

        Args:
            plugin_name (str): 插件名称

        Returns:
            bool: 如果存在配置类则返回True，否则返回False
        """
        return plugin_name in self._config_classes

    def has_config_instance(self, plugin_name: str) -> bool:
        """
        检查是否存在指定插件的配置实例

        Args:
            plugin_name (str): 插件名称

        Returns:
            bool: 如果存在配置实例则返回True，否则返回False
        """
        return plugin_name in self._config_instances

    def get_config_instance(self, plugin_name: str) -> T | None:
        """
        获取指定插件的配置实例

        Args:
            plugin_name (str): 插件名称

        Returns:
            T | None: 配置实例，如果不存在则返回None
        """
        return self._config_instances.get(plugin_name)

    def get_config_instance_not_none(self, plugin_name: str) -> T:
        """
        获取指定插件的配置实例（非空）

        Args:
            plugin_name (str): 插件名称

        Returns:
            T: 配置实例

        Raises:
            KeyError: 如果插件名称不存在
        """
        if plugin_name not in self._config_instances:
            raise KeyError(f"Configuration instance for '{plugin_name}' not found")
        return self._config_instances[plugin_name]

    def get_config_class_by_name(self, plugin_name: str) -> type[T] | None:
        """
        根据插件名称获取配置类

        Args:
            plugin_name (str): 插件名称

        Returns:
            type[T] | None: 配置类，如果不存在则返回None
        """
        return self._config_classes.get(plugin_name)

    async def _get_config_by_file(self, plugin_name: str) -> T:
        """
        从文件获取配置

        Args:
            plugin_name (str): 插件名称

        Returns:
            T: 配置实例
        """
        config_dir = get_config_dir(plugin_name)
        await self._init_config_or_nothing(plugin_name, config_dir)
        async with aiofiles.open(config_dir / "config.toml", encoding="utf-8") as f:
            async with self._lock[plugin_name]:
                config = tomli.loads(await f.read())
                config_class = self._config_classes[plugin_name].model_validate(config)
                self._config_instances[plugin_name] = config_class
        return config_class

    async def _init_config_or_nothing(self, plugin_name: str, config_dir: Path):
        """
        初始化配置或什么都不做

        Args:
            plugin_name (str): 插件名称
            config_dir (Path): 配置目录路径
        """
        config_file = config_dir / "config.toml"
        if not config_file.exists():
            if (config_instance := self._config_instances.get(plugin_name)) is None:
                config_instance = self._config_classes[plugin_name]()
                self._config_instances[plugin_name] = config_instance
            async with aiofiles.open(config_file, mode="w", encoding="utf-8") as f:
                await f.write(tomli_w.dumps(config_instance.model_dump()))

    async def _add_watch_path(
        self,
        plugin_name: str,
        path: Path,
        filter: FILTER_TYPE,
        *callbacks: CALLBACK_TYPE,
    ):
        """添加文件监听

        Args:
            plugin_name (str): 插件名称
            path (Path): 路径（相对路径）
            filter (FILTER_TYPE): 过滤函数
            *callbacks (CALLBACK_TYPE): 回调函数列表
        """

        async def excutor():
            """
            执行文件监控任务
            """
            try:
                async for changes in watchfiles.awatch(path):
                    if any(filter(change) for change in changes):
                        try:
                            async with self._callback_lock[plugin_name]:
                                for callback in callbacks:
                                    await callback(plugin_name, path)
                        except Exception as e:
                            logger.opt(exception=e, colors=True).error(
                                "Error while calling callback function"
                            )
            except Exception as e:
                logger.opt(exception=e, colors=True).error(
                    f"Error in watcher for {path}"
                )

        self._tasks.append(asyncio.create_task(excutor()))

    async def _config_reload_callback(self, plugin_name: str, _):
        """
        配置重载回调函数

        Args:
            plugin_name (str): 插件名称
            _ : 未使用的参数
        """
        logger.info(f"{plugin_name} 配置文件已修改，正在重载中......")
        await self._get_config_by_file(plugin_name)
        logger.success(f"{plugin_name} 配置文件已重载")

    async def _file_reload_callback(self, plugin_name: str, path: Path):
        """
        文件重载回调函数

        Args:
            plugin_name (str): 插件名称
            path (Path): 文件路径
        """
        logger.info(f"{plugin_name} ({path.name})文件已修改，正在重载中......")
        async with self._lock[plugin_name]:
            self._config_file_cache[plugin_name] = StringIO()
            async with aiofiles.open(path, encoding="utf-8") as f:
                self._config_file_cache[plugin_name].write(await f.read())
        logger.success(f"{plugin_name} ({path.name})文件已重载")

    def _clean_tasks(self):
        """
        清理所有任务
        """
        for task in self._tasks:
            task.cancel()
