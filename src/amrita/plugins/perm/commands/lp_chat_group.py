from typing import Any

from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Depends
from typing_extensions import override

from ..API.admin import is_lp_admin
from ..command_manager import command
from ..config import GroupData, PermissionGroupData, data_manager
from ..nodelib import Permissions
from .cmd_utils import parse_command
from .main import PermissionHandler


class PermissionOperation(PermissionHandler):
    @override
    async def execute(
        self, group_id: str, operation: str, node: str, value: str
    ) -> tuple[str, dict[str, Any]]:
        group_data = data_manager.get_group_data(group_id)
        group_perm = Permissions(group_data.permissions)
        msg_str = ""
        match operation:
            case "del":
                group_perm.del_permission(node)
                msg_str = f"✅ 已删除权限节点 {node}"
            case "set":
                if value.lower() not in ("true", "false"):
                    return "❌ 值必须是 true/false", group_data.model_dump()
                group_perm.set_permission(node, value == "true", False)
                msg_str = f"✅ 已设置 {node} : {value}"
            case "check":
                msg_str = (
                    "✅ 持有该权限"
                    if group_perm.check_permission(node)
                    else "❌ 未持有该权限"
                )
            case "list":
                msg_str = f"群聊权限列表：\n{group_perm.permissions_str}"
            case _:
                msg_str = "❌ 不支持的操作类型"
        return msg_str, group_data.model_dump()


class ParentGroupHandler(PermissionHandler):
    @override
    async def execute(
        self, group_id: str, operation: str, perm_group: str, _: str
    ) -> tuple[str, dict[str, Any]]:
        group_data = data_manager.get_group_data(group_id)
        perm_perm_group_data = data_manager.get_permission_group_data(perm_group, False)
        if perm_perm_group_data is None:
            return "❌ 权限组不存在", group_data.model_dump()
        string_msg = ""
        if not perm_perm_group_data:
            string_msg = f"❌ 权限组 {perm_group} 不存在"

        match operation:
            case "add" | "del":
                self._modify_inheritance(group_data, perm_perm_group_data, operation)
                string_msg = f"✅ 已{'添加' if operation == 'add' else '移除'}继承组 {perm_group}"
            case "set":
                group_data.permissions = perm_perm_group_data.permissions.copy()
                string_msg = f"✅ 已覆盖为组 {perm_group} 的权限"
            case _:
                string_msg = "❌ 不支持的操作类型"
        return string_msg, group_data.model_dump()

    def _modify_inheritance(
        self,
        group_data: GroupData,
        perm_perm_group_data: PermissionGroupData,
        operation,
    ):
        perm_group_perms = Permissions(perm_perm_group_data.permissions)
        group_perms = Permissions(group_data.permissions)

        for node, state in perm_group_perms.data.items():
            if operation == "add" and not group_perms.check_permission(node):
                group_perms.set_permission(node, state, False)
            elif operation == "del" and group_perms.check_permission(node):
                group_perms.del_permission(node)


class PermissionGroupHandler(PermissionHandler):
    @override
    async def execute(
        self, group_id: str, operation: str, target: str, value: str
    ) -> tuple[str, dict[str, Any]]:
        group_data = data_manager.get_group_data(group_id)
        msg_str = ""
        if operation == "add":
            if target not in group_data.permission_groups:
                msg_str = f"❌ 权限组 {target} 不存在"
                return msg_str, group_data.model_dump()
            group_data.permission_groups.append(target)
            msg_str = f"✅ 成功添加权限组 {target}"
        elif operation == "del":
            if target in group_data.permission_groups:
                group_data.permission_groups.remove(target)
                msg_str = f"✅ 删除权限组 {target} 成功"
            else:
                msg_str = f"❌ 权限组 {target} 不存在"
        return msg_str, group_data.model_dump()


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
@command.command("chat_group", permission=is_lp_admin).handle()
async def lp_group(
    event: MessageEvent,
    matcher: Matcher,
    params: tuple[str, str, str, str, str] = Depends(parse_command),
):
    group_id, action_type, operation, target, value = params
    handler = get_handler(action_type)
    if handler is None:
        await matcher.finish("❌ 未知操作类型")
    try:
        result, data = await handler.execute(group_id, operation, target, value)
    except ValueError as e:
        result = f"❌ 操作失败：{e!s}"
    finally:
        data_manager.save_group_data(group_id, data)

    await matcher.finish(result)
