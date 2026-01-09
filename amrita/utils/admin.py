from __future__ import annotations

import time
import typing
from asyncio import Lock
from collections import defaultdict

import nonebot
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from amrita.config import get_amrita_config
from amrita.utils.rate import TokenBucket

# 用于跟踪消息发送的计数器和时间戳
_message_tracker = defaultdict(int)
# 异常状态标志
_critical_error_occurred = False
# 线程锁，确保计数器操作的线程安全
_tracker_lock = Lock()
bucket = TokenBucket(
    1 / 7,  # 7s一次
    1,
)
_last_exception_time = 0


# 数据库出现问题时可能导致一直产生错误，这里的设计也是为了账号安全。
async def _check_and_handle_rate_limit():
    """检查消息发送频率并处理速率限制"""
    global _critical_error_occurred, bucket, _last_exception_time
    from amrita.plugins.manager.status_manager import StatusManager

    async with _tracker_lock:
        consume = bucket.consume()
        _message_tracker["admin"] += int(not consume)

        if _message_tracker["admin"] > 6 and not _critical_error_occurred:
            _critical_error_occurred = True
            StatusManager().set_unready(True)
            nonebot.logger.info(
                "严重异常警告！Amrita可能无法从这个错误恢复！之后的推送将被阻断！请立即查看控制台！现在amrita将进入维护模式！"
            )
            await send_to_admin(
                "严重异常警告！Amrita可能无法从这个错误恢复！之后的推送将被阻断！请立即查看控制台！现在amrita将进入维护模式！"
            )
            nonebot.logger.info("Critical error occurred!Rejected pushing!")
            return True

        elif _critical_error_occurred:
            if consume and time.time() - _last_exception_time > 15:
                _critical_error_occurred = False
                _message_tracker["admin"] = 0
                logger.info("[LOGGER] Fall back to logging-ready status.")
            else:
                logger.info("Rejecting pushing due to critical error.")
                return True  # 仍然处于异常状态
        else:
            _message_tracker["admin"] = 0
    return False  # 表示不需要阻断消息发送


async def send_to_admin(msg: str, bot: Bot | None = None):
    """发送消息到管理

    Args:
        bot (Bot): Bot
        msg (str): 消息内容
    """
    config = get_amrita_config()
    if config.admin_group == -1:
        return nonebot.logger.warning("SEND_TO_ADMIN\n" + msg)
    if bot is None:
        bot = typing.cast(Bot, nonebot.get_bot())
    await bot.send_group_msg(group_id=config.admin_group, message=msg)


async def send_forward_msg_to_admin(
    bot: Bot, name: str, uin: str, msgs: list[MessageSegment]
):
    """发送消息到管理

    Args:
        bot (Bot): Bot
        name (str): 名称
        uin (str): UID
        msgs (list[MessageSegment]): 消息列表

    Returns:
        dict: 发送消息后的结果
    """
    global _last_exception_time
    # 检查是否需要阻断消息发送
    if await _check_and_handle_rate_limit():
        return  # 阻断消息发送
    _last_exception_time = time.time()

    def to_json(msg: MessageSegment) -> dict:
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    config = get_amrita_config()
    if config.admin_group == -1:
        return nonebot.logger.warning(
            "LOG_MSG_FORWARD\n".join(
                [msg.data.get("text", "") for msg in msgs if msg.is_text()]
            )
        )

    messages = [to_json(msg) for msg in msgs]
    await bot.send_group_forward_msg(group_id=config.admin_group, messages=messages)
