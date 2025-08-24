from datetime import datetime

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot
from nonebot.matcher import Matcher

from amrita.plugins.menu.models import MatcherData
from amrita.utils.utils import get_amrita_version

from .models import get_usage


async def generate_info(bot: Bot):
    # 动态导入
    import os
    import platform
    import shutil
    import sys

    import psutil

    system_name = platform.system()
    python_version = sys.version
    memory = psutil.virtual_memory()
    cpu_usage = psutil.cpu_percent(interval=1)
    logical_cores = psutil.cpu_count(logical=True)
    disk_usage_origin = shutil.disk_usage(os.getcwd())
    disk_usage = (disk_usage_origin.used / disk_usage_origin.total) * 100
    msg_status_all = await get_usage(bot.self_id)
    for i in msg_status_all:
        if i.created_at == datetime.now().strftime("%Y-%m-%d"):
            msg_status = i
            msg_received = msg_status.msg_received
            msg_sent = msg_status.msg_sent
            return (
                f"系统类型: {system_name}\n"
                f"CPU 核心: {logical_cores}\n"
                f"CPU 已使用: {cpu_usage}%\n"
                f"已用内存: {memory.percent}%\n"
                f"磁盘存储占用：{disk_usage:.2f}%\n"
                f"Python 版本: {python_version}\n"
                f"消息收{msg_received} 发{msg_sent}\n"
                f"Powered by Amrita V{get_amrita_version()}"
            )


@on_command(
    "status",
    state=MatcherData(
        description="查看系统状态", name="查看系统状态", usage="/status"
    ).model_dump(),
).handle()
async def _(matcher: Matcher, bot: Bot):
    await matcher.finish(await generate_info(bot))
