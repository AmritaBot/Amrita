from nonebot import on_command
from nonebot.matcher import Matcher


def generate_info():
    # 动态导入
    import os
    import platform
    import shutil
    import sys

    import psutil

    system_name = platform.system()
    system_version = platform.version()
    python_version = sys.version
    memory = psutil.virtual_memory()
    cpu_usage = psutil.cpu_percent(interval=1)
    logical_cores = psutil.cpu_count(logical=True)
    physical_cores = psutil.cpu_count(logical=False)
    disk_usage_origin = shutil.disk_usage(os.getcwd())
    disk_usage = (disk_usage_origin.used / disk_usage_origin.total) * 100

    return (
        f"系统类型: {system_name}\n\n"
        f"系统版本: {system_version}\n\n"
        f"CPU 物理核心数：{physical_cores}\n\n"
        f"CPU 总核心: {logical_cores}\n\n"
        f"CPU 已使用: {cpu_usage}%\n\n"
        f"已用内存: {memory.percent}%\n\n"
        f"总共内存: {memory.total / (1024**3):.2f} GB\n\n"
        f"可用内存: {memory.available / (1024**3):.2f} GB\n\n"
        f"磁盘存储占用：{disk_usage:.2f}%\n\n"
        f"Python 版本: {python_version}\n\n"
        "Powered by Amrita"
    )


@on_command(
    "status",
).handle()
async def _(matcher: Matcher):
    await matcher.finish(generate_info())
