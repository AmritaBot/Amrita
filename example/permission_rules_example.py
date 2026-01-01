"""
LP权限系统Rules检查器示例
这个模块演示如何使用LP权限系统创建Rules检查器来检查用户权限
"""

from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageEvent
from nonebot.params import CommandArg
from nonebot.permission import Permission

from amrita.plugins.perm.API.rules import GroupPermissionChecker, UserPermissionChecker

# 示例1：创建一个需要特定用户权限的命令
# 只有拥有 "chat.admin" 权限的用户才能执行此命令
admin_command = on_command(
    "admin_action",
    permission=Permission(UserPermissionChecker(permission="chat.admin").checker()),
    priority=10,
    block=True,
)


@admin_command.handle()
async def handle_admin_command(event: MessageEvent):
    """处理需要管理员权限的命令"""
    await admin_command.finish("您已成功执行管理员命令！")


# 示例2：创建一个需要群组权限的消息处理器
# 只有在拥有 "chat.manage" 权限的群组中才能触发
group_manage_msg = on_message(
    permission=Permission(
        GroupPermissionChecker(permission="chat.manage", only_group=True).checker()
    ),
    priority=15,
    block=True,
)


@group_manage_msg.handle()
async def handle_group_manage_msg(event: GroupMessageEvent):
    """处理群组管理相关的消息"""
    if "管理" in event.get_plaintext():
        await group_manage_msg.finish("检测到管理相关的消息，已处理。")


# 示例3：创建一个命令，需要用户权限或群组权限
# 用户需要 "chat.use" 权限，或者在拥有 "chat.global" 权限的群组中
flexible_command = on_command(
    "flexible_action",
    permission=Permission(UserPermissionChecker(permission="chat.use").checker())
    | Permission(
        GroupPermissionChecker(permission="chat.global", only_group=False).checker()
    ),
    priority=10,
    block=True,
)


@flexible_command.handle()
async def handle_flexible_command(args: Message = CommandArg()):
    """处理灵活权限的命令"""
    message = args.extract_plain_text()
    await flexible_command.finish(f"灵活权限命令执行成功！输入参数：{message}")


# 示例4：创建一个需要特定权限的命令，展示权限检查的详细过程
permission_demo = on_command(
    "permission_demo",
    permission=Permission(UserPermissionChecker(permission="chat.demo").checker()),
    priority=20,
    block=True,
)


@permission_demo.handle()
async def handle_permission_demo(event: MessageEvent):
    """演示权限检查的使用"""
    await permission_demo.finish("权限检查成功！")


# 示例5：创建一个权限检查失败的示例处理器（无权限检查）
public_command = on_command("public_action", priority=5, block=True)


@public_command.handle()
async def handle_public_command():
    """处理无需权限检查的公共命令"""
    await public_command.finish("这是一个公共命令，任何人都可以执行。")
