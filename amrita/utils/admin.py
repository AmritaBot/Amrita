from __future__ import annotations

import time
import typing
from asyncio import Lock
from collections import defaultdict

import nonebot
from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from amrita.config import get_amrita_config
from amrita.utils.rate import TokenBucket

# 用于跟踪消息发送的计数器和时间戳
_message_tracker = defaultdict(list)
# 异常状态标志
_critical_error_occurred = False
# 线程锁，确保计数器操作的线程安全
_tracker_lock = Lock()
bucket = TokenBucket(0.2, 1)


# 数据库出现问题时可能导致一直产生错误，这里的设计也是为了账号安全。
async def _check_and_handle_rate_limit():
    """检查消息发送频率并处理速率限制"""
    global _critical_error_occurred, bucket
    from amrita.plugins.manager.status_manager import StatusManager

    current_time = time.time()
    window_start = current_time - 5  # 5秒窗口

    async with _tracker_lock:
        # 清理5秒前的消息记录
        for key in _message_tracker:
            _message_tracker[key] = [
                t for t in _message_tracker[key] if t > window_start
            ]

        # 检查是否超过7条消息
        msg_count = len(_message_tracker["admin"])
        if msg_count > 7 and not _critical_error_occurred:
            _critical_error_occurred = True
            StatusManager().set_unready(True)
            nonebot.logger.warning(
                "严重异常警告！Amrita可能无法从这个错误恢复！之后的推送将被阻断！请立即查看控制台！现在amrita将进入维护模式！"
            )
            await send_to_admin_unsafe(
                "严重异常警告！Amrita可能无法从这个错误恢复！之后的推送将被阻断！请立即查看控制台！现在amrita将进入维护模式！"
            )
            return True

    if _critical_error_occurred:
        if bucket.consume():
            _critical_error_occurred = False
            # 如果维护模式为开则自动关闭
            if StatusManager().is_unready():
                StatusManager().set_unready(False)
        else:
            return True  # 仍然处于异常状态
    return False  # 表示不需要阻断消息发送


async def send_to_admin_unsafe(msg: str, bot: Bot | None = None):
    config = get_amrita_config()
    if config.admin_group == -1:
        return nonebot.logger.warning("SEND_TO_ADMIN\n" + msg)
    if bot is None:
        bot = typing.cast(Bot, nonebot.get_bot())
    await bot.send_group_msg(group_id=config.admin_group, message=msg)


async def send_to_admin(msg: str, bot: Bot | None = None):
    """发送消息到管理

    Args:
        bot (Bot): Bot
        msg (str): 消息内容
    """
    # 检查是否需要阻断消息发送
    if await _check_and_handle_rate_limit():
        return  # 阻断消息发送

    # 记录消息发送时间
    async with _tracker_lock:
        _message_tracker["admin"].append(time.time())

    await send_to_admin_unsafe(msg, bot)


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
    # 检查是否需要阻断消息发送
    if await _check_and_handle_rate_limit():
        return  # 阻断消息发送

    # 记录消息发送时间
    async with _tracker_lock:
        _message_tracker["admin"].append(time.time())

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
