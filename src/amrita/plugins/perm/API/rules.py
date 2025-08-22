from abc import abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias

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

from ..config import PermissionGroupData, data_manager
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


@dataclass
class PermissionChecker:
    """
    权限检查器基类
    args:
        permission: 权限节点
    """

    permission: str = field(default="")

    def checker(self) -> Callable[[Event, str], Awaitable[bool]]:
        """生成可被 Rule 使用的检查器闭包

        Returns:
            Callable[[Event], Awaitable[bool]]: 供Rule检查的Async函数
        """

        # 捕获当前权限值到闭包中
        current_perm = self.permission or ""

        async def _checker(event: Event, current_perm=current_perm) -> bool:
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

    @override
    async def _check_permission(self, event: Event, perm: str) -> bool:
        user_id = event.get_user_id()
        user_data = data_manager.get_user_data(user_id)
        logger.debug(f"checking user permission {user_id} {perm}")
        perm_groups = user_data.permission_groups

        for permg in perm_groups:
            group_data: PermissionGroupData | None = (
                data_manager.get_permission_group_data(permg)
            )
            if group_data is None:
                raise ValueError(f"permission group {permg} not found")
            if Permissions(group_data.permissions).check_permission(perm):
                return True
        return Permissions(user_data.model_dump()).check_permission(perm)


@dataclass
class GroupPermissionChecker(PermissionChecker):
    """
    群组权限检查器
    args:
        only_group: 是否只允许群事件
    """

    only_group: bool = True

    @override
    async def _check_permission(self, event: Event, perm: str) -> bool:
        if not isinstance(event, GroupEvent) and not self.only_group:
            return True
        elif not isinstance(event, GroupEvent):
            return False
        else:
            g_event: GroupEvent = event
        group_id: str = str(g_event.group_id)
        group_data = data_manager.get_group_data(group_id)
        logger.debug(f"checking group permission {group_id} {perm}")
        perm_groups = group_data.permission_groups
        for permg in perm_groups:
            if (data := data_manager.get_permission_group_data(permg)) is not None:
                if Permissions(data.permissions).check_permission(perm):
                    return True

        return Permissions(group_data.model_dump()).check_permission(perm)
