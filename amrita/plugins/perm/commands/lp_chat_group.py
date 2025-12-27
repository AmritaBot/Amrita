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
    async def execute(
        self, id: str, operation: str, target: str, value: str
    ) -> tuple[str, MemberPermissionPydantic | None]:
        store = PermissionStorage()
        group_data = await store.get_member_permission(id, "group")
        group_perm = Permissions(group_data.permissions)
        msg_str = ""
        match operation:
            case "del":
                group_perm.del_permission(target)
                msg_str = f"✅ 已删除权限节点 {target}"
            case "set":
                if value.lower() not in ("true", "false"):
                    return "❌ 值必须是 true/false", None
                group_perm.set_permission(target, value == "true")
                msg_str = f"✅ 已设置 {target} : {value}"
            case "check":
                msg_str = (
                    "✅ 持有该权限"
                    if group_perm.check_permission(target)
                    else "❌ 未持有该权限"
                )
            case "list":
                msg_str = f"群聊权限列表：\n{group_perm.permissions_str}"
            case _:
                msg_str = "❌ 不支持的操作类型"
        group_data.permissions = group_perm.dump_data()
        return msg_str, group_data


class ParentGroupHandler(PermissionHandler):
    @override
    async def execute(
        self, id: str, operation: str, target: str, value: str
    ) -> tuple[str, MemberPermissionPydantic | None]:
        store = PermissionStorage()
        group_data = await store.get_member_permission(id, "group")

        perm_target_data = (
            await store.get_permission_group(target)
            if await store.permission_group_exists(target)
            else None
        )
        if perm_target_data is None:
            return "❌ 权限组不存在", None
        string_msg = ""
        if not perm_target_data:
            string_msg = f"❌ 权限组 {target} 不存在"

        match operation:
            case "add" | "del":
                self._modify_inheritance(group_data, perm_target_data, operation)
                string_msg = (
                    f"✅ 已{'添加' if operation == 'add' else '移除'}继承组 {target}"
                )
            case "set":
                group_data.permissions = deepcopy(perm_target_data.permissions) or {}
                string_msg = f"✅ 已完全Copy覆盖为组 {target} 的权限"
            case _:
                string_msg = "❌ 不支持的操作类型"
        return string_msg, group_data

    def _modify_inheritance(
        self,
        group_data: MemberPermissionPydantic,
        perm_group_data: PermissionGroupPydantic,
        operation,
    ):
        perm_group_perms = Permissions(perm_group_data.permissions)
        group_perms = Permissions(group_data.permissions)

        for node, state in perm_group_perms.data.items():
            if operation == "add" and not group_perms.check_permission(node):
                group_perms.set_permission(node, state)
            elif operation == "del" and group_perms.check_permission(node):
                group_perms.del_permission(node)
        group_data.permissions = group_perms.dump_data()


class PermissionGroupHandler(PermissionHandler):
    @override
    async def execute(
        self, id: str, operation: str, target: str, value: str
    ) -> tuple[str, None]:
        store = PermissionStorage()
        msg_str = ""
        if operation == "add":
            if await store.permission_group_exists(target):
                # 检查权限组是否存在

                await store.add_member_related_permission_group(id, "group", target)
                msg_str = f"✅ 成功添加权限组 {target}"
            else:
                msg_str = f"❌ 权限组 {target} 不存在"
                return msg_str, None
        elif operation == "del":
            if await store.is_member_in_permission_group(id, "group", target):
                await store.del_member_related_permission_group(id, "group", target)
                msg_str = f"✅ 删除权限组关系 `{target}` 成功"
            else:
                msg_str = f"❌ 目标不在权限组： `{target}`"
        return msg_str, None


# 获取可用的权限处理器
def get_handler(
    action_type: str,
) -> PermissionGroupHandler | ParentGroupHandler | PermissionOperation | None:
    handlers = {
        "permission": PermissionOperation(),
        "parent": ParentGroupHandler(),
        "perm_group": PermissionGroupHandler(),
    }
    return handlers.get(action_type)


# 运行进入点
@command.command(
    "chat_group",
    permission=is_lp_admin,
    state=MatcherData(
        name="lp聊群权限配置",
        description="配置特定群权限",
        usage="/lp.chat_group",
    ).model_dump(),
).handle()
async def lp_group(
    event: MessageEvent,
    matcher: Matcher,
    params: tuple[str, str, str, str, str] = Depends(parse_command),
):
    id, action_type, operation, target, value = params
    handler = get_handler(action_type)
    if handler is None:
        await matcher.finish("❌ 未知操作类型")
    try:
        result, data = await handler.execute(id, operation, target, value)
        if data:
            await PermissionStorage().update_member_permission(data)
    except ValueError as e:
        result = f"❌ 操作失败：{e!s}"

    await matcher.finish(result)
