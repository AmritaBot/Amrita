"""聊天处理器模块"""

import asyncio
import random
from datetime import datetime

from amrita_core import (
    MemoryModel,
    PresetManager,
    SessionsManager,
    TextContent,
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
from amrita_core.types import USER_INPUT, ImageContent, ImageUrl
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
)
from nonebot.adapters.onebot.v11.event import (
    GroupMessageEvent,
    MessageEvent,
    Reply,
)
from nonebot.exception import MatcherException, NoneBotException, ProcessException
from nonebot.matcher import Matcher
from pytz import utc

from amrita.plugins.chat.config import ConfigManager, config_manager
from amrita.plugins.chat.matcher import ChatException
from amrita.plugins.chat.utils.app import CachedUserDataRepository, UserMetadataSchema
from amrita.plugins.chat.utils.functions import (
    get_friend_name,
    split_message_into_chats,
    synthesize_message,
)
from amrita.plugins.chat.utils.lock import get_group_lock, get_private_lock
from amrita.plugins.chat.utils.sql import InsightsModel, get_any_id, get_uni_user_id
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


async def handle_reply(
    reply: Reply, bot: Bot, group_id: int | None, content: str
) -> str:
    """处理引用消息：
    - 提取引用消息的内容和时间信息。
    - 格式化为可读的引用内容。

    Args:
        reply: 回复消息
        bot: Bot实例
        group_id: 群组ID（私聊为None）
        content: 原始内容

    Returns:
        格式化后的内容
    """
    if not reply.sender.user_id:
        return content
    dt_object = datetime.fromtimestamp(reply.time)
    weekday = dt_object.strftime("%A")
    formatted_time = dt_object.strftime("%Y-%m-%d %I:%M:%S %p")
    role = (
        f"{await get_user_role(bot, group_id, reply.sender.user_id)}"
        if group_id
        else ""
    )

    reply_content = await synthesize_message(reply.message, bot)
    result = f"{content}\n<MESSAGE_REFERED>\n{formatted_time} {weekday} {role}{reply.sender.nickname}（QQ:{reply.sender.user_id}）说：{reply_content}\n</MESSAGE_REFERED>"
    debug_log(f"处理引用消息完成: {result[:50]}..")
    return result


def get_reply_pics(event: MessageEvent) -> list[ImageContent]:
    """获取引用消息中的图片内容

    Returns:
        图片内容列表
    """
    if reply := event.reply:
        msg = reply.message
        images = [
            ImageContent(image_url=ImageUrl(url=url))
            for seg in msg
            if seg.type == "image" and (url := seg.data.get("url")) is not None
        ]
        debug_log(f"获取引用图片完成，共 {len(images)} 张")
        return images
    return []


async def get_user_role(bot: Bot, group_id: int, user_id: int) -> str:
    """获取用户在群聊中的身份（群主、管理员或普通成员）。

    Args:
        group_id: 群组ID
        user_id: 用户ID

    Returns:
        用户角色字符串
    """
    role_data = await bot.get_group_member_info(group_id=group_id, user_id=user_id)
    role = role_data["role"]
    role_str = {"admin": "群管理员", "owner": "群主", "member": "普通成员"}.get(
        role, "[获取身份失败]"
    )
    debug_log(f"获取用户角色完成: {role_str}")
    return role_str


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


async def synthesize_message_to_msg(
    event: MessageEvent,
    role: str,
    user_name: str,
    user_id: str,
    content: str,
):
    """将消息转换为Message

    根据配置和多模态支持情况，将事件消息转换为适当的格式，
    支持文本和图片内容的组合。

    Args:
        event: 消息事件
        role: 用户角色
        date: 时间戳
        user_name: 用户名
        user_id: 用户ID
        content: 消息内容

    Returns:
        转换后的消息内容
    """
    is_multimodal: bool = (
        any(
            [
                (await config_manager.get_preset(preset=preset)).config.multimodal
                for preset in [
                    config_manager.config.preset,
                    *config_manager.config.preset_extension.backup_preset_list,
                ]
            ]
        )
        or len(config_manager.config.preset_extension.multi_modal_preset_list) > 0
    )

    if config_manager.config.parse_segments:
        text = (
            [TextContent(text=f"[{role}][{user_name}（{user_id}）]说:{content}")]
            + [
                ImageContent(image_url=ImageUrl(url=seg.data["url"]))
                for seg in event.message
                if seg.type == "image" and seg.data.get("url")
            ]
            if is_multimodal
            else f"[{role}][{user_name}（{user_id}）]说:{content}"
        )
    else:
        text = event.message.extract_plain_text()
    return text


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
    session_id = get_uni_user_id(event)
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
        if isinstance(message, str):
            return
        elif isinstance(message, MessageWithMetadata):
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

    content: USER_INPUT = await synthesize_message(event.get_message(), bot)
    debug_log(f"合成消息完成: {content}")

    if content.strip() == "":
        content = ""
    if event.reply:
        group_id = event.group_id if isinstance(event, GroupMessageEvent) else None
        debug_log("处理引用消息..")
        content = await handle_reply(event.reply, bot, group_id, content)

    reply_pics = get_reply_pics(event)
    debug_log(f"获取引用图片完成，共 {len(reply_pics)} 张")
    if isinstance(event, GroupMessageEvent):
        # 群聊消息处理
        debug_log("处理群聊消息")
        group_id = event.group_id

        user_name = (
            (await bot.get_group_member_info(group_id=group_id, user_id=event.user_id))[
                "nickname"
            ]
            if not config.function.use_user_nickname
            else event.sender.nickname
        )
    else:
        debug_log("处理私聊消息")
        user_name = (
            await get_friend_name(event.user_id, bot=bot)
            if not isinstance(event, GroupMessageEvent)
            else event.sender.nickname
        )
    role = (
        await get_user_role(bot, event.group_id, event.user_id)
        if isinstance(event, GroupMessageEvent)
        else ""
    )
    content = await synthesize_message_to_msg(
        event, role, str(user_name), str(event.user_id), content
    )
    if isinstance(content, list):
        content.extend(reply_pics)
    chat: AmritaChatObject = AmritaChatObject(
        event=event,
        matcher=matcher,
        bot=bot,
        session_id=session_id,
        train=train,
        auto_create_session=False,
        user_input=content,
        context=MemoryModel(),
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
            async with chat.begin():
                await chat  # Wait for workflow to complete
                chat.memory.memory_json = chat.data
                await cudr.update_memory_data(chat.memory)
                if can_send_message:
                    await send_response(chat, chat.response.content)

    except BaseException as e:
        if isinstance(e, (NoneBotException, ChatException)):
            raise
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
                await cudr.update_metadata(d)
        SessionsManager().drop_session(session_id)
        chat._pending = False
