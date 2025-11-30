import asyncio
from asyncio import Lock, Task
from collections import defaultdict
from collections.abc import Awaitable, Callable
from io import StringIO
from pathlib import Path

import aiofiles
import tomli
import tomli_w
import watchfiles
from nonebot import logger
from nonebot_plugin_localstore import _try_get_caller_plugin, get_config_dir
from pydantic import BaseModel

CALLBACK_TYPE = Callable[[str, Path], Awaitable]
FILTER_TYPE = Callable[[watchfiles.main.FileChange], bool]


class UniConfigManager:
    """
    为Amrita/NoneBot插件设计的统一配置管理器
    """

    _instance = None
    _lock: defaultdict[str, Lock]
    _callback_lock: defaultdict[str, Lock]
    _file_callback_map: dict[Path, CALLBACK_TYPE]
    _config_classes: dict[str, type[BaseModel]]
    _config_other_files: dict[str, set[Path]]
    _config_directories: dict[str, set[Path]]
    _config_file_cache: dict[str, StringIO]  # Path -> StringIO
    _config_instances: dict[str, BaseModel]
    _tasks: list[Task]

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._config_classes = {}
            cls._config_other_files = defaultdict(set)
            cls._config_instances = {}
            cls._config_directories = defaultdict(set)
            cls._lock = defaultdict(Lock)
            cls._callback_lock = defaultdict(Lock)
            cls._config_file_cache = {}
            cls._tasks = []
        return cls._instance

    def __del__(self):
        self._clean_tasks()

    async def add_config(
        self,
        config_class: type[BaseModel],
        init_now: bool = True,
        watch: bool = True,
        owner_name: str | None = None,
        on_reload: CALLBACK_TYPE | None = None,
    ):
        owner_name = owner_name or _try_get_caller_plugin().name
        logger.debug(f"`{owner_name}` add config `{config_class.__name__}`")
        config_dir = get_config_dir(owner_name)
        async with self._lock[owner_name]:
            if owner_name in self._config_classes:
                raise ValueError(
                    f"`{owner_name}` has already registered a config class"
                )
            self._config_classes[owner_name] = config_class
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

    async def get_config(self, plugin_name: str | None = None) -> BaseModel:
        plugin_name = plugin_name or _try_get_caller_plugin().name
        return self._config_instances.get(
            plugin_name
        ) or await self._get_config_by_file(plugin_name)

    async def get_config_class(self, plugin_name: str | None = None) -> type[BaseModel]:
        return self._config_classes[plugin_name or (_try_get_caller_plugin().name)]

    async def reload_config(self, owner_name: str | None = None):
        owner_name = owner_name or _try_get_caller_plugin().name
        await self._get_config_by_file(owner_name)

    async def loads_config(self, instance: BaseModel, owner_name: str | None = None):
        owner_name = owner_name or _try_get_caller_plugin().name
        async with self._lock[owner_name]:
            self._config_instances[owner_name] = instance

    async def save_config(self, owner_name: str | None = None):
        owner_name = owner_name or _try_get_caller_plugin().name
        config_dir = get_config_dir(owner_name)
        async with self._lock[owner_name]:
            async with aiofiles.open(
                config_dir / "config.toml", mode="w", encoding="utf-8"
            ) as f:
                await f.write(
                    tomli_w.dumps(self._config_instances[owner_name].model_dump())
                )

    async def _get_config_by_file(self, plugin_name: str) -> BaseModel:
        config_dir = get_config_dir(plugin_name)
        await self._init_config_or_nothing(plugin_name, config_dir)
        async with aiofiles.open(config_dir / "config.toml", encoding="utf-8") as f:
            async with self._lock[plugin_name]:
                config = tomli.loads(await f.read())
                config_class = self._config_classes[plugin_name].model_validate(config)
                self._config_instances[plugin_name] = config_class
        return config_class

    async def _init_config_or_nothing(self, plugin_name: str, config_dir: Path):
        config_file = config_dir / "config.toml"
        if not config_file.exists():
            async with aiofiles.open(config_file, mode="w", encoding="utf-8") as f:
                await f.write(
                    tomli_w.dumps(self._config_classes[plugin_name]().model_dump())
                )

    async def _add_watch_path(
        self,
        plugin_name: str,
        path: Path,
        filter: FILTER_TYPE,
        *callbacks: CALLBACK_TYPE,
    ):
        """添加文件监听

        Args:
            path (Path): 路径（相对路径）
            callback (Callable[[Path],Awaitable[None]]): 回调函数(Path:绝对路径).
        """

        async def excutor():
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
        logger.info(f"{plugin_name} 配置文件已修改，正在重载中......")
        await self._get_config_by_file(plugin_name)
        logger.success(f"{plugin_name} 配置文件已重载")

    async def _file_reload_callback(self, plugin_name: str, path: Path):
        logger.info(f"{plugin_name} ({path.name})文件已修改，正在重载中......")
        async with self._lock[plugin_name]:
            self._config_file_cache[plugin_name] = StringIO()
            async with aiofiles.open(path, encoding="utf-8") as f:
                self._config_file_cache[plugin_name].write(await f.read())
        logger.success(f"{plugin_name} ({path.name})文件已重载")

    def _clean_tasks(self):
        for task in self._tasks:
            task.cancel()
