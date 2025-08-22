import asyncio
import os
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import nonebot
from dotenv import load_dotenv
from nonebot.log import default_format, logger_id

from amrita.config import get_amrita_config

from .admin import send_forward_msg_to_admin

if TYPE_CHECKING:
    # avoid sphinx autodoc resolve annotation failed
    # because loguru module do not have `Logger` class actually
    from loguru import Record


def default_filter(record: "Record"):
    """默认的日志过滤器，根据 `config.log_level` 配置改变日志等级。"""
    log_level = record["extra"].get("nonebot_log_level", "INFO")
    levelno = (
        nonebot.logger.level(log_level).no if isinstance(log_level, str) else log_level
    )
    return record["level"].no >= levelno


def init():
    from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
    from nonebot.adapters.onebot.v11 import Bot, MessageSegment

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

    Path("plugins").mkdir(exist_ok=True)

    load_dotenv()

    nonebot.init()

    driver = nonebot.get_driver()
    driver.register_adapter(ONEBOT_V11Adapter)
    load_dotenv()
    config = get_amrita_config()
    log_dir = config.log_dir
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
        level=config.amrita_log_level,
        format=default_format,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        enqueue=True,
    )
    nonebot.logger.add(AsyncErrorHandler(), level="ERROR")
