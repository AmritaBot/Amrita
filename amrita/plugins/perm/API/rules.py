from abc import abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias

from async_lru import alru_cache
from nonebot.adapters.onebot.v11 import (
    Event,
    GroupAdminNoticeEvent,
    GroupBanNoticeEvent,
    GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent,
    GroupMessageEvent,
    GroupRecallNoticeEvent,
    GroupRequestEvent,
    GroupUploadNoticeEvent,
)
from nonebot.log import logger
from typing_extensions import override

from ..models import (
    PermissionStorage,
)
from ..nodelib import Permissions

GroupEvent: TypeAlias = (
    GroupIncreaseNoticeEvent
    | GroupAdminNoticeEvent
    | GroupBanNoticeEvent
    | GroupDecreaseNoticeEvent
    | GroupMessageEvent
    | GroupRecallNoticeEvent
    | GroupRequestEvent
    | GroupUploadNoticeEvent
)


@alru_cache()
async def _check_user_permission_with_cache(user_id: str, perm: str) -> bool:
    """检查用户权限的缓存函数"""
    store = PermissionStorage()
    user_data = await store.get_member_permission(user_id, "user")
    logger.debug(f"正在检查用户权限 {user_id}:{perm}")

    if perm_groups := (
        await store.get_member_related_permission_groups(user_id, "user")
    ).groups:
        logger.info(f"正在检查用户权限组，用户ID：{user_id}")
        for permg in perm_groups:
            logger.debug(f"正在检查用户权限组 {permg}，用户ID：{user_id}")
            if not await store.permission_group_exists(permg):
                logger.warning(f"权限组 {permg} 不存在")
                continue
            group_data = await store.get_permission_group(permg)
            if Permissions(group_data.permissions).check_permission(perm):
                return True
    return Permissions(user_data.permissions).check_permission(perm)


@alru_cache()
async def _check_group_permission_with_cache(
    group_id: str, perm: str, only_group: bool
) -> bool:
    """检查群组权限的缓存函数"""
    store = PermissionStorage()
    group_data = await store.get_member_permission(member_id=group_id, type="group")
    logger.debug(f"正在检查群组权限 {group_id} {perm}")
    if permd := await store.get_member_related_permission_groups(group_id, "group"):
        for permg in permd.groups:
            logger.debug(f"正在检查群组 {group_id} 的权限组 {permg}")
            if not await store.permission_group_exists(permg):
                logger.warning(f"权限组 {permg} 不存在")
                continue
            data = await store.get_permission_group(permg)
            if Permissions(data.permissions).check_permission(perm):
                return True

    return Permissions(group_data.permissions).check_permission(perm)


@dataclass
class PermissionChecker:
    """
    权限检查器基类
    args:
        permission: 权限节点
    """

    permission: str = field(default="")

    def __hash__(self) -> int:
        return hash(self.permission)

    def checker(self) -> Callable[[Event], Awaitable[bool]]:
        """生成可被 Rule 使用的检查器闭包

        Returns:
            Callable[[Event], Awaitable[bool]]: 供Rule检查的Async函数
        """
        current_perm = self.permission

        async def _checker(event: Event) -> bool:
            """实际执行检查的协程函数"""
            # 通过闭包访问类变量（self.permission）
            return await self._check_permission(event, current_perm)

        return _checker

    @abstractmethod
    async def _check_permission(self, event: Event, perm: str) -> bool:
        raise NotImplementedError("Awaitable '_check_permission' not implemented")


@dataclass
class UserPermissionChecker(PermissionChecker):
    """
    用户权限检查器
    """

    def __hash__(self) -> int:
        return hash(self.permission)

    @override
    async def _check_permission(self, event: Event, perm: str) -> bool:
        user_id = event.get_user_id()
        return await _check_user_permission_with_cache(user_id, perm)


@dataclass
class GroupPermissionChecker(PermissionChecker):
    """
    群组权限检查器
    args:
        only_group: 是否只允许群事件
    """

    only_group: bool = True

    def __hash__(self) -> int:
        return hash(self.permission + str(self.only_group))

    @override
    async def _check_permission(self, event: Event, perm: str) -> bool:
        if not isinstance(event, GroupEvent) and not self.only_group:
            return True
        elif not isinstance(event, GroupEvent):
            return False
        else:
            g_event: GroupEvent = event
        group_id: str = str(g_event.group_id)
        return await _check_group_permission_with_cache(group_id, perm, self.only_group)
