from copy import deepcopy

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends
from typing_extensions import override

from amrita.plugins.menu.models import MatcherData

from ..API.admin import is_lp_admin
from ..command_manager import command
from ..models import (
    MemberPermissionPydantic,
    PermissionGroupPydantic,
    PermissionStorage,
)
from ..nodelib import Permissions
from .cmd_utils import parse_command
from .main import PermissionHandler


class PermissionOperation(PermissionHandler):
    @override
    async def execute(self, id: str, operation: str, target: str, value: str):
        store = PermissionStorage()
        user_data = await store.get_member_permission(id, "user")
        user_perm = Permissions(user_data.permissions)
        msg_str = ""
        match operation:
            case "del":
                user_perm.del_permission(target)
                msg_str = f"✅ 已删除权限节点 {target}"
            case "set":
                if value.lower() not in ("true", "false"):
                    return "❌ 值必须是 true/false", None
                user_perm.set_permission(target, value == "true")
                msg_str = f"✅ 已设置 {target} : {value}"
            case "check":
                msg_str = (
                    "✅ 按照权限"
                    if user_perm.check_permission(target)
                    else "❌ 未持有该权限"
                )
            case "list":
                msg_str = f"用户权限列表：\n{user_perm.permissions_str}"
            case _:
                return "❌ 不支持的操作类型", None
        user_data.permissions = user_perm.dump_data()
        return msg_str, user_data


class ParentGroupHandler(PermissionHandler):
    @override
    async def execute(self, id: str, operation: str, target: str, value: str):
        store = PermissionStorage()
        user_data = await store.get_member_permission(id, "user")

        perm_target_data = (
            await store.get_permission_group(target)
            if await store.permission_group_exists(target)
            else None
        )
        if perm_target_data is None:
            return "❌ 权限组不存在", None
        string_msg = ""

        match operation:
            case "add" | "del":
                self._modify_inheritance(user_data, perm_target_data, operation)
                string_msg = (
                    f"✅ 已{'添加' if operation == 'add' else '移除'}继承组 {target}"
                )
            case "set":
                user_data.permissions = deepcopy(perm_target_data.permissions) or {}
                string_msg = f"✅ 已覆盖为组 {target} 的权限"
            case _:
                return "❌ 未知操作类型", None
        return string_msg, user_data

    def _modify_inheritance(
        self,
        user_data: MemberPermissionPydantic,
        perm_group_data: PermissionGroupPydantic,
        operation,
    ):
        group_perms = Permissions(perm_group_data.permissions)
        user_perms = Permissions(user_data.permissions)

        for node, state in group_perms.data.items():
            if operation == "add" and not user_perms.check_permission(node):
                user_perms.set_permission(node, state)
            elif operation == "del" and user_perms.check_permission(node):
                user_perms.del_permission(node)
        user_data.permissions = user_perms.dump_data()


class PermissionGroupHandler(PermissionHandler):
    @override
    async def execute(self, id: str, operation: str, target: str, value: str):
        store = PermissionStorage()
        msg_str = ""
        if operation == "add":
            if not await store.is_member_in_permission_group(id, "user", target):
                # 检查权限组是否存在
                if not await store.permission_group_exists(target):
                    msg_str = f"❌ 权限组 {target} 不存在"
                    return msg_str, None
                await store.add_member_related_permission_group(id, "user", target)
                msg_str = f"✅ 成功添加权限组 {target}"
        elif operation == "del":
            if await store.is_member_in_permission_group(id, "user", target):
                await store.del_member_related_permission_group(id, "user", target)
                msg_str = f"✅ 将用户从权限组 {target} 移除成功"
            else:
                msg_str = f"❌ {target} 不存在该已关系的用户"
        return msg_str, None


# 获取可用的权限处理器
def get_handler(
    action_type: str,
) -> PermissionHandler | None:
    handlers = {
        "permission": PermissionOperation(),
        "parent": ParentGroupHandler(),
        "perm_group": PermissionGroupHandler(),
    }
    return handlers.get(action_type)


# 运行进入点
@command.command(
    "user",
    permission=is_lp_admin,
    state=MatcherData(
        name="lp用户权限配置",
        description="配置特定用户权限",
        usage="/lp.user",
    ).model_dump(),
).handle()
async def lp_user(
    event: MessageEvent,
    matcher: Matcher,
    params: tuple[str, str, str, str, str] = Depends(parse_command),
):
    user_id, action_type, operation, target, value = params
    handler = get_handler(action_type)
    if handler is None:
        await matcher.finish("❌ 未知操作类型")
    try:
        result, data = await handler.execute(user_id, operation, target, value)
        if data:
            await PermissionStorage().update_member_permission(data)
    except ValueError as e:
        result = f"❌ 操作失败：{e!s}"

    await matcher.finish(result)
