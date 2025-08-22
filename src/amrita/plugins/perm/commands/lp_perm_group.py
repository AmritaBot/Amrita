from typing import Any

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends
from typing_extensions import override

from ..API.admin import is_lp_admin
from ..command_manager import command
from ..config import PermissionGroupData, data_manager
from ..nodelib import Permissions
from .cmd_utils import parse_command
from .main import PermissionHandler


class PermissionOperation(PermissionHandler):
    @override
    async def execute(
        self, group: str, operation: str, node: str, value: str
    ) -> tuple[str, dict[str, Any]]:
        permission_group_data = data_manager.get_permission_group_data(group, new=True)
        if permission_group_data is None:
            return f"❌ 权限组{group}不存在", {}
        user_perm = Permissions(permission_group_data.permissions)
        msg_str = ""
        match operation:
            case "del":
                user_perm.del_permission(node)
                msg_str = f"✅ 已删除权限节点 {node}"
            case "set":
                if value.lower() not in ("true", "false"):
                    return "❌ 值必须是 true/false", permission_group_data.model_dump()
                user_perm.set_permission(node, value == "true", False)
                msg_str = f"✅ 已设置 {node} : {value}"
            case "check":
                msg_str = (
                    "✅ 持有该权限"
                    if user_perm.check_permission(node)
                    else "❌ 未持有该权限"
                )
            case "list":
                msg_str = f"用户权限列表：\n{user_perm.permissions_str}"
            case _:
                msg_str = "❌ 不支持的操作类型"
        return msg_str, permission_group_data.model_dump()


class ParentGroupHandler(PermissionHandler):
    @override
    async def execute(
        self, group: str, operation: str, target_group: str, _: str
    ) -> tuple[str, dict[str, Any]]:
        permission_group_data = data_manager.get_permission_group_data(group)
        perm_group_data = data_manager.get_permission_group_data(target_group, False)
        if perm_group_data is None:
            return "❌ 权限组不存在", {}
        string_msg = "❌ 操作失败"
        if permission_group_data is None:
            return "❌ 目标权限组不存在", {}

        match operation:
            case "add" | "del":
                self._modify_inheritance(
                    permission_group_data, perm_group_data, operation
                )
                string_msg = f"✅ 已{'添加' if operation == 'add' else '移除'}继承组 {target_group}"
            case "set":
                permission_group_data.permissions = perm_group_data.permissions.copy()
                string_msg = f"✅ 已覆盖为组 {target_group} 的权限"
            case _:
                string_msg = "❌ 不支持的操作类型"
        return string_msg, permission_group_data.model_dump()

    def _modify_inheritance(
        self,
        permission_group_data: PermissionGroupData,
        perm_group_data: PermissionGroupData,
        operation,
    ):
        group_perms = Permissions(perm_group_data.permissions)
        user_perms = Permissions(permission_group_data.permissions)

        for node, state in group_perms.data.items():
            if operation == "add" and not user_perms.check_permission(node):
                user_perms.set_permission(node, state, False)
            elif operation == "del" and user_perms.check_permission(node):
                user_perms.del_permission(node)


class PermissionGroupHandler(PermissionHandler):
    async def execute(
        self, group: str, operation: str, *_
    ) -> tuple[str, dict[str, Any]]:
        if operation == "create":
            if data_manager.get_permission_group_data(group) is not None:
                return "❌ 权限组已存在", {}
            data_manager.get_permission_group_data(group, True)
            return "✅ 权限组创建成功", {}
        elif operation == "remove":
            if data_manager.get_permission_group_data(group) is None:
                return "❌ 权限组不存在", {}
            data_manager.remove_permission_group(group)
            return "✅ 权限组删除成功", {}
        return "❌ 操作错误", {}


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
@command.command("perm_group", permission=is_lp_admin).handle()
async def lp_user(
    event: MessageEvent,
    matcher: Matcher,
    params: tuple[str, str, str, str, str] = Depends(parse_command),
):
    user_id, action_type, operation, target, value = params
    handler = get_handler(action_type)
    if handler is None:
        await matcher.finish("❌ 未知操作类型")
    else:
        try:
            result, data = await handler.execute(user_id, operation, target, value)
        except ValueError as e:
            result = f"❌ 操作失败：{e!s}"
        finally:
            if data is not None:
                data_manager.save_permission_group_data(user_id, data)

    await matcher.finish(result)
