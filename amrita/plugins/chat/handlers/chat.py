"""聊天处理器模块"""

import asyncio
import random
from datetime import datetime

from amrita_core import (
    PresetManager,
    SessionsManager,
    UniResponse,
    UniResponseUsage,
    debug_log,
    logger,
)
from amrita_core.protocol import (
    COMPLETION_RETURNING,
    ImageMessage,
    MessageWithMetadata,
    StringMessageContent,
)
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
)
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, MessageEvent
from nonebot.exception import MatcherException, NoneBotException, ProcessException
from nonebot.matcher import Matcher
from pytz import utc

from amrita.plugins.chat.config import ConfigManager, config_manager
from amrita.plugins.chat.matcher import ChatException
from amrita.plugins.chat.utils.app import CachedUserDataRepository, UserMetadataSchema
from amrita.plugins.chat.utils.functions import split_message_into_chats
from amrita.plugins.chat.utils.lock import get_group_lock, get_private_lock
from amrita.plugins.chat.utils.sql import InsightsModel, get_any_id
from amrita.utils.admin import send_to_admin

from ..runtime import AmritaChatObject

command_prefix = get_driver().config.command_start or "/"


def add_usage(
    ins: InsightsModel | UserMetadataSchema, usage: UniResponseUsage[int] | None
):
    if isinstance(ins, InsightsModel):
        if usage:
            ins.token_output += usage.completion_tokens
            ins.token_input += usage.prompt_tokens
        ins.usage_count += 1
    else:
        if usage:
            ins.tokens_input += usage.prompt_tokens
            ins.tokens_output += usage.completion_tokens
            ins.total_input_token += usage.prompt_tokens
            ins.total_output_token += usage.completion_tokens
        ins.called_count += 1
        ins.total_called_count += 1


async def send_response(chat: AmritaChatObject, response: str):
    """发送聊天模型的回复，根据配置选择不同的发送方式。

    Args:
        response: 模型响应内容
    """
    chat.last_call = datetime.now(utc)
    debug_log(f"发送响应: {response[:50]}..")  # 只显示前50个字符
    if not chat.bot_config.function.nature_chat_style:
        await chat.matcher.send(
            MessageSegment.reply(chat.event.message_id) + MessageSegment.text(response)
        )
    elif response_list := split_message_into_chats(response):
        for message in response_list:
            await chat.matcher.send(MessageSegment.text(message))
            await asyncio.sleep(
                random.randint(1, 3) + (len(message) // random.randint(80, 100))
            )


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
    config = ConfigManager().config
    can_send_message: bool = True
    cudr = CachedUserDataRepository()

    async def filter(message: COMPLETION_RETURNING):
        nonlocal can_send_message
        if isinstance(message, MessageWithMetadata):
            match message.metadata.get("type", ""):
                case "system":
                    if (
                        message.content
                        == "Some error occurred, please try again later."
                    ):
                        can_send_message = False
                        await send_to_admin(
                            f"安全警告：用户请求导致了可能的Prompt泄露。已在response检测到cookie泄露，请检查！\n用户请求：\n{chat.user_input!s}\n模型模型输出：\n{chat.response.content!s}"
                        )
                        await matcher.send(random.choice(config.llm.block_msg))
                    await matcher.send(message.content)
                case "reasoning":
                    if not config.llm.tools.agent_reasoning_hide:
                        await matcher.send(message.content)
                case "function_call":
                    if (
                        message.metadata["is_done"]
                        and config.llm.tools.agent_tool_call_notice == "notify"
                    ):
                        function_name = message.metadata["function_name"]
                        if err := message.metadata.get("err") is not None:
                            logger.opt(exception=err, colors=True).exception(
                                f"Tool {function_name} execution failed: {err}"
                            )
                            await matcher.send(
                                f"ERR: {function_name} 执行失败",
                            )
                        else:
                            await matcher.send(f"调用了工具：{function_name}")
                case "error":
                    error = message.metadata["error"]
                    logger.opt(exception=error, colors=True).exception(
                        f"有错误发生:{error}"
                    )
        elif isinstance(message, StringMessageContent):
            await matcher.send(message.get_content())
        elif isinstance(message, ImageMessage):
            msg = MessageSegment.image(await message.get_image())
            await matcher.send(msg)

    chat: AmritaChatObject = AmritaChatObject(
        event=event,
        matcher=matcher,
        bot=bot,
        session_id=session_id,
        train=train,
        auto_create_session=True,
        context=None,
        config=config.to_core_config(),
        preset=PresetManager().get_preset(config.preset),
        hook_args=(event, matcher, bot),
        exception_ignored=(ProcessException, MatcherException),
    )
    chat.set_callback_func(filter)
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
            chat.last_call = datetime.now(utc)
            chat._pending = False
            debug_log("获取锁成功，开始获取记忆数据")
            await chat.begin()
            chat.memory.memory_json = chat.data
            await cudr.update_memory_data(chat.memory)
            if can_send_message:
                await send_response(chat, chat.response.content)

    except BaseException as e:
        if isinstance(e, (NoneBotException, ChatException)):
            raise
        debug_log(f"处理聊天事件时发生异常: {e}")
        await chat._throw(e)
    finally:
        response: UniResponse[str, None] | None
        if (response := getattr(chat, "response", None)) is not None:
            insights = await InsightsModel.get()
            debug_log(f"获取洞察数据完成，使用计数: {insights.usage_count}")
            add_usage(insights, response.usage)
            await insights.save()
            debug_log(f"更新全局统计完成，使用计数: {insights.usage_count}")

            ins = await cudr.get_metadata(*get_any_id(event))
            for d in (
                (
                    ins,
                    await cudr.get_metadata(event.user_id, False),
                )
                if hasattr(event, "group_id")
                else (ins,)
            ):
                d.called_count  # 增加使用次数
                add_usage(d, response.usage)
                debug_log(f"更新记忆数据，使用次数: {d.usage}")
                await cudr.update_metadata(d)
        SessionsManager().drop_session(session_id)
        chat._pending = False
