from abc import abstractmethod
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias, Dict, Set, Tuple, Any

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

# 事件ID到权限节点的映射（使用元组避免字符串分割脆弱性）
_event_permission_mapping: Dict[str, Dict[str, Set[Tuple[str, str]]]] = defaultdict(
    lambda: {"users": set(), "groups": set()}
)

# 缓存存储引用，用于手动清理
_user_cache_ref: Any = None
_group_cache_ref: Any = None


def register_event_permission(event_id: str, user_id: str | None, group_id: str | None, permission: str):
    """注册事件使用的权限节点"""
    if user_id:
        _event_permission_mapping[event_id]["users"].add((user_id, permission))
    if group_id:
        _event_permission_mapping[event_id]["groups"].add((group_id, permission))


def _expire_cache_by_key(cache_ref: Any, key: Tuple[str, ...]) -> bool:
    """通过key过期特定缓存条目"""
    try:
        # 尝试使用invalidate方法
        if hasattr(cache_ref, 'invalidate'):
            cache_ref.invalidate(key)
            return True
        # 尝试使用expire方法
        elif hasattr(cache_ref, 'expire'):
            cache_ref.expire(key)
            return True
        # 尝试使用cache_expire方法
        elif hasattr(cache_ref, 'cache_expire'):
            cache_ref.cache_expire(key=key)
            return True
        else:
            # 如果都没有，尝试直接操作内部缓存
            if hasattr(cache_ref, '_cache'):
                cache_ref._cache.pop(key, None)
                return True
    except Exception as e:
        logger.warning(f"缓存过期操作失败: {e}")
    return False


async def expire_event_cache(event_id: str):
    """根据事件ID清理相关缓存"""
    if event_id not in _event_permission_mapping:
        return
    
    mapping = _event_permission_mapping[event_id]
    
    # 清理用户权限缓存
    global _user_cache_ref
    for user_id, permission in mapping["users"]:
        try:
            if _user_cache_ref:
                key = (user_id, permission)
                if _expire_cache_by_key(_user_cache_ref, key):
                    logger.debug(f"已清理用户权限缓存: {user_id}:{permission}")
                else:
                    logger.debug(f"用户权限缓存清理方法不支持: {user_id}:{permission}")
            else:
                logger.debug("用户权限缓存引用未初始化")
        except Exception as e:
            logger.warning(f"清理用户权限缓存失败: {user_id}:{permission}, 错误: {e}")
    
    # 清理群组权限缓存 (需要考虑group_only的true/false两种情况)
    global _group_cache_ref
    for group_id, permission in mapping["groups"]:
        try:
            if _group_cache_ref:
                # 清理两种情况缓存: only_group=True 和 only_group=False
                for only_group in [True, False]:
                    key = (group_id, permission, only_group)
                    if _expire_cache_by_key(_group_cache_ref, key):
                        logger.debug(f"已清理群组权限缓存: {group_id}:{permission} (only_group={only_group})")
                    else:
                        logger.debug(f"群组权限缓存清理方法不支持: {group_id}:{permission} (only_group={only_group})")
            else:
                logger.debug("群组权限缓存引用未初始化")
        except Exception as e:
            logger.warning(f"清理群组权限缓存失败: {group_id}:{permission}, 错误: {e}")
    
    # 删除事件映射
    del _event_permission_mapping[event_id]
    logger.debug(f"已清理事件权限映射: {event_id}")


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


# 在模块初始化时设置缓存引用
_user_cache_ref = _check_user_permission_with_cache
_group_cache_ref = _check_group_permission_with_cache


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
            # 获取事件ID（避免在实例中存储可变状态）
            event_id = str(id(event))
            return await self._check_permission(event, current_perm, event_id)

        return _checker

    @abstractmethod
    async def _check_permission(self, event: Event, perm: str, event_id: str) -> bool:
        raise NotImplementedError("Awaitable '_check_permission' not implemented")


@dataclass
class UserPermissionChecker(PermissionChecker):
    """
    用户权限检查器
    """

    def __hash__(self) -> int:
        return hash(self.permission)

    @override
    async def _check_permission(self, event: Event, perm: str, event_id: str) -> bool:
        user_id = event.get_user_id()
        # 注册权限使用记录
        register_event_permission(event_id, user_id, None, perm)
        result = await _check_user_permission_with_cache(user_id, perm)
        return result


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
    async def _check_permission(self, event: Event, perm: str, event_id: str) -> bool:
        if not isinstance(event, GroupEvent) and not self.only_group:
            return True
        elif not isinstance(event, GroupEvent):
            return False
        else:
            g_event: GroupEvent = event
        
        group_id: str = str(g_event.group_id)
        user_id = event.get_user_id()
        
        # 注册权限使用记录
        register_event_permission(event_id, user_id, group_id, perm)
        
        result = await _check_group_permission_with_cache(group_id, perm, self.only_group)
        return result