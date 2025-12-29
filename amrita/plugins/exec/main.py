import asyncio
import shlex
import subprocess

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.exception import FinishedException
from nonebot.params import CommandArg

from amrita.plugins.menu.models import MatcherData
from amrita.plugins.perm.API.rules import UserPermissionChecker
from amrita.utils.send import send_forward_msg

user_check = UserPermissionChecker(permission="admin.exec")
permission = user_check.checker()

execute = on_command("exec",
                     state=MatcherData(name="执行命令", usage="/exec <command>", description="在服务器上执行命令").model_dump(),
                     priority=1,
                     block=True,
                     rule=permission)

@execute.handle()
async def _(event: MessageEvent, bot: Bot, args: Message = CommandArg()):
    try:
        cmd_text = args.extract_plain_text().strip()
        if not cmd_text:
            await execute.finish("请输入要执行的命令")
        cmd_parts = shlex.split(cmd_text)

        execute_result = await asyncio.create_subprocess_exec(
            *cmd_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False
        )
        try:
            stdout, stderr = await asyncio.wait_for(execute_result.communicate(), timeout=10)
        except asyncio.TimeoutError:
            execute_result.kill()
            await execute.finish("执行超时")
        results = [
            MessageSegment.text(f"执行结果：{stdout.decode('utf-8')}"),
            MessageSegment.text(f"执行失败：{stderr.decode('utf-8')}") if stderr else None
        ]
        await send_forward_msg(bot, event, name="执行结果", uin=bot.self_id, msgs=results)
    except FinishedException:
        pass
    except Exception as e:
        await bot.send(event, f"执行失败：{e}")
