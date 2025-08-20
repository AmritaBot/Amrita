import asyncio
import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import nonebot
import toml
from dotenv import dotenv_values, load_dotenv
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from nonebot.adapters.onebot.v11 import Bot, MessageSegment
from nonebot.log import default_format, logger_id

if not Path(".env").exists():
    with open(".env", "w") as f:
        f.write("".join(f"{k}={v}\n" for k, v in dotenv_values(".env.example").items()))
if not Path(".env.prod").exists():
    with open(".env.prod", "a") as f:
        f.write("LOG_LEVEL=INFO")
if not Path(".env.dev").exists():
    with open(".env.dev", "a") as f:
        f.write("LOG_LEVEL=DEBUG")

Path("plugins").mkdir(exist_ok=True)

load_dotenv()

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)

nonebot.load_from_toml("pyproject.toml")

from .utils.admin import send_forward_msg_to_admin

if TYPE_CHECKING:
    # avoid sphinx autodoc resolve annotation failed
    # because loguru module do not have `Logger` class actually
    from loguru import Record

SUPERUSER_list = list(get_driver().config.superusers)

load_dotenv()


def default_filter(record: "Record"):
    """默认的日志过滤器，根据 `config.log_level` 配置改变日志等级。"""
    log_level = record["extra"].get("nonebot_log_level", "INFO")
    levelno = (
        nonebot.logger.level(log_level).no if isinstance(log_level, str) else log_level
    )
    return record["level"].no >= levelno


log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

# 移除 NoneBot 默认的日志处理器
nonebot.logger.remove(logger_id)
# 添加新的日志处理器
nonebot.logger.add(
    sys.stdout,
    level=0,
    diagnose=True,
    format=default_format,
    filter=default_filter,
)
nonebot.logger.add(
    f"{log_dir}/" + "{time}.log",  # 传入函数，每天自动更新日志路径
    level=os.getenv("AMRITA_LOG_LEVEL", "WARNING"),
    format=default_format,
    rotation="00:00",
    retention="7 days",
    encoding="utf-8",
    enqueue=True,
)


class AsyncErrorHandler:
    def write(self, message):
        self.task = asyncio.create_task(self.process(message))

    async def process(self, message):
        try:
            record = message.record
            if record["level"].name == "ERROR":
                # 处理异常 traceback
                if record["exception"]:
                    exc_info = record["exception"]
                    traceback_str = "".join(
                        traceback.format_exception(
                            exc_info.type, exc_info.value, exc_info.traceback
                        )
                    )
                else:
                    traceback_str = "无堆栈信息"

                content = (
                    f"错误信息: {record['message']}\n"
                    f"时间: {record['time']}\n"
                    f"模块: {record['name']}\n"
                    f"文件: {record['file'].path}\n"
                    f"行号: {record['line']}\n"
                    f"函数: {record['function']}\n"
                    f"堆栈信息:\n{traceback_str}"
                )

                bot = nonebot.get_bot()
                if isinstance(bot, Bot):
                    await send_forward_msg_to_admin(
                        bot,
                        "Amrita-Exception",
                        bot.self_id,
                        [MessageSegment.text(content)],
                    )

        except Exception as e:
            nonebot.logger.warning(f"发送群消息失败: {e}")


nonebot.logger.add(AsyncErrorHandler(), level="ERROR")


def run(*args, **kwargs):
    nonebot.logger.info("Loading built-in plugins...")
    for name in (Path(__file__).parent / "plugins").iterdir():
        nonebot.logger.info(f"Loading plugin {name.name}...")
        nonebot.load_plugin(f"amrita.plugins.{name.name}")
    nonebot.logger.info("Loading plugins......")
    from amrita.cli import PyprojectFile

    config = PyprojectFile.model_validate(toml.load("pyproject.toml"))
    for plugin in config.tool.amrita.plugins:
        nonebot.logger.info(f"Loading plugin {plugin}...")
        nonebot.load_plugin(plugin)
    nonebot.run(*args, **kwargs)


if __name__ == "__main__":
    __name__ = "Amrita"
    run()
