"""聊天处理器模块"""

from datetime import datetime

from amrita.plugins.chat.utils.memory import get_memory_data
from amrita_core import debug_log
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
)
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot.matcher import Matcher
from pytz import utc

from amrita.plugins.chat.config import config_manager
from amrita.plugins.chat.matcher import ChatException
from amrita.plugins.chat.utils.lock import get_group_lock, get_private_lock

from ..runtime import AmritaChatObject

command_prefix = get_driver().config.command_start or "/"


async def entry(event: MessageEvent, matcher: Matcher, bot: Bot):
    """聊天处理器入口函数

    该函数作为消息事件的入口点，处理命令前缀检查并启动聊天对象。

    Args:
        event: 消息事件
        matcher: 匹配器
        bot: Bot实例

    Returns:
        聊天处理结果
    """
    if any(
        event.message.extract_plain_text().strip().startswith(prefix)
        for prefix in command_prefix
        if prefix.strip()
    ):
        matcher.skip()
    session_id = (
        f"{event.group_id}_{event.user_id}"
        if isinstance(event, GroupMessageEvent)
        else f"private_{event.user_id}"
    )
    train = (
        config_manager.group_train
        if isinstance(event, GroupMessageEvent)
        else config_manager.private_train
    )
    chat: AmritaChatObject = AmritaChatObject(
        event=event,
        matcher=matcher,
        bot=bot,
        session_id=session_id,
        train=train,
    )

    config = chat.bot_config
    event = chat.event
    matcher = chat.matcher

    try:
        lock = (
            get_group_lock(event.group_id)
            if isinstance(event, GroupMessageEvent)
            else get_private_lock(event.user_id)
        )

        match config.function.chat_pending_mode:
            case "queue":
                debug_log("聊天队列模式")
                chat._pending = lock.locked()
            case "single":
                if lock.locked():
                    debug_log("聊天已被锁定，跳过")
                    return matcher.stop_propagation()
            case "single_with_report":
                if lock.locked():
                    debug_log("聊天已被锁定，发送报告")
                    await matcher.finish("聊天任务正在处理中，请稍后再试")

        async with lock:
            chat._is_running = True
            chat.last_call = datetime.now(utc)
            chat._pending = False
            debug_log("获取锁成功，开始获取记忆数据")
            memory = await get_memory_data(event)
            debug_log("记忆数据获取完成，开始运行聊天流程")

            async with chat:
                ...
    except BaseException as e:
        if isinstance(e, ChatException):
            raise
        debug_log(f"处理聊天事件时发生异常: {e}")
        await chat._throw(e)
    finally:
        chat._pending = False
