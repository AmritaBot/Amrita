from copy import deepcopy

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends
from typing_extensions import override

from amrita.plugins.menu.models import MatcherData

from ..API.admin import is_lp_admin
from ..command_manager import command
from ..models import (
    PermissionGroupPydantic,
    PermissionStorage,
)
from ..nodelib import Permissions
from .cmd_utils import parse_command
from .main import PermissionHandler


class PermissionOperation(PermissionHandler):
    @override
    async def execute(
        self, id: str, operation: str, target: str, value: str
    ) -> tuple[str, PermissionGroupPydantic | None]:
        store = PermissionStorage()
        permission_group_data = await store.get_permission_group(id)
        user_perm = Permissions(permission_group_data.permissions)
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
                    "✅ 持有该权限"
                    if user_perm.check_permission(target)
                    else "❌ 未持有该权限"
                )
            case "list":
                msg_str = f"权限组权限列表：\n{user_perm.permissions_str}"
            case _:
                msg_str = "❌ 不支持的操作类型"
        permission_group_data.permissions = user_perm.dump_data()
        return msg_str, permission_group_data


class ParentGroupHandler(PermissionHandler):
    @override
    async def execute(
        self, id: str, operation: str, target: str, value: str
    ) -> tuple[str, PermissionGroupPydantic | None]:
        store = PermissionStorage()
        permission_group_data = await store.get_permission_group(id)

        perm_target_data = (
            await store.get_permission_group(target)
            if await store.permission_group_exists(target)
            else None
        )
        if perm_target_data is None:
            return "❌ 权限组不存在", None
        string_msg = "❌ 操作失败"

        match operation:
            case "add" | "del":
                self._modify_inheritance(
                    permission_group_data, perm_target_data, operation
                )
                string_msg = (
                    f"✅ 已{'添加' if operation == 'add' else '移除'}于继承组 {target}"
                )
            case "set":
                permission_group_data.permissions = (
                    deepcopy(perm_target_data.permissions) or {}
                )
                string_msg = f"✅ 已覆盖为组 {target} 的权限"
            case _:
                string_msg = "❌ 不支持的操作类型"
        await store.update_permission_group(permission_group_data)
        return string_msg, permission_group_data

    def _modify_inheritance(
        self,
        permission_group_data: PermissionGroupPydantic,
        perm_group_data: PermissionGroupPydantic,
        operation,
    ):
        group_perms = Permissions(perm_group_data.permissions)
        user_perms = Permissions(permission_group_data.permissions)

        for node, state in group_perms.data.items():
            if operation == "add" and not user_perms.check_permission(node):
                user_perms.set_permission(node, state)
            elif operation == "del" and user_perms.check_permission(node):
                user_perms.del_permission(node)
        permission_group_data.permissions = user_perms.dump_data()


class PermissionGroupHandler(PermissionHandler):
    async def execute(self, id: str, operation: str, target: str, value: str):  # type: ignore
        store = PermissionStorage()
        if operation == "create":
            # 检查权限组是否已存在
            if await store.permission_group_exists(id):
                return "❌ 权限组已存在", None
            # 创建新的权限组
            new_group_data = await store.get_permission_group(id)
            await store.update_permission_group(new_group_data)
            return "✅ 权限组创建成功", None
        elif operation == "remove":
            # 检查权限组是否存在
            if not await store.permission_group_exists(id):
                return "❌ 权限组不存在", None
            return "✅ 权限组删除成功", None
        return "❌ 操作错误", None


def get_handler(
    action_type: str,
) -> PermissionHandler | None:
    handlers = {
        "permission": PermissionOperation(),
        "parent": ParentGroupHandler(),
        "to": PermissionGroupHandler(),
    }
    return handlers.get(action_type)


# 运行进入点
@command.command(
    "perm_group",
    permission=is_lp_admin,
    state=MatcherData(
        name="lp权限组配置",
        description="配置权限组权限",
        usage="/lp.chat_group",
    ).model_dump(),
).handle()
async def lp_user(
    event: MessageEvent,
    matcher: Matcher,
    params: tuple[str, str, str, str, str] = Depends(parse_command),
):
    user_id, action_type, operation, target, value = params
    handler = get_handler(action_type)
    data = None
    if handler is None:
        await matcher.finish("❌ 未知操作类型")
    else:
        try:
            result, data = await handler.execute(user_id, operation, target, value)
            if data:
                await PermissionStorage().update_permission_group(data)
        except ValueError as e:
            result = f"❌ 操作失败：{e!s}"

    await matcher.finish(result)
