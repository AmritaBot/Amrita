import asyncio
import contextlib
import random
import time
from asyncio import CancelledError, Lock
from dataclasses import dataclass, field
from datetime import datetime

from amrita_core import (
    ChatObject as CoreChatObject,
)
from amrita_core import (
    ChatObjectMeta as CoreChatObjectMeta,
)
from amrita_core.config import AmritaConfig
from amrita_core.logging import debug_log
from nonebot import logger
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
)
from nonebot.adapters.onebot.v11.event import (
    GroupMessageEvent,
    MessageEvent,
    Reply,
)
from nonebot.matcher import Matcher
from nonebot_plugin_orm import get_session
from pydantic import BaseModel, Field
from pytz import utc

from amrita.plugins.chat.utils.event import GroupEvent

from .check_rule import FakeEvent
from .config import Config, config_manager
from .matcher import MatcherManager
from .utils.functions import (
    get_friend_name,
    split_message_into_chats,
    synthesize_message,
)
from .utils.libchat import get_chat, get_tokens
from .utils.memory import (
    MemoryModel,
    get_memory_data,
)
from .utils.protocol import UniResponse
from .utils.sql import (
    SEND_MESSAGES,
    ImageContent,
    ImageUrl,
    InsightsModel,
    Message,
    SessionMemoryModel,
    TextContent,
    UniResponseUsage,
)

LOCK = Lock()


async def synthesize_message_to_msg(
    event: MessageEvent,
    role: str,
    date: str,
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
                (await config_manager.get_preset(preset=preset)).multimodal
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
            [
                TextContent(
                    text=f"[{role}][{date}][{user_name}（{user_id}）]说:{content}"
                )
            ]
            + [
                ImageContent(image_url=ImageUrl(url=seg.data["url"]))
                for seg in event.message
                if seg.type == "image" and seg.data.get("url")
            ]
            if is_multimodal
            else f"[{role}][{date}][{user_name}（{user_id}）]说:{content}"
        )
    else:
        text = event.message.extract_plain_text()
    return text


class ChatObjectMeta(CoreChatObjectMeta):
    """聊天对象元数据模型

    用于存储聊天对象的标识、事件和时间信息。
    """

    event: MessageEvent  # 消息事件


class AmritaChatObject(CoreChatObject):
    """聊天处理对象

    该类负责处理单次聊天会话，包括消息接收、上下文管理、模型调用和响应发送。
    """

    matcher: Matcher  # (lateinit) 匹配器
    bot: Bot  # (lateinit) Bot实例
    event: MessageEvent  # (lateinit) 消息事件
    config: AmritaConfig  # 配置
    bot_config: Config  # 插件配置
    _err: BaseException | None = None
    _pending: bool = False  # 是否在等待队列中

    def is_waitting(self) -> bool:
        """
        检查任务是否处于等待状态

        Returns:
            bool: 如果任务正在等待则返回True，否则返回False
        """
        return self._pending

    def __init__(
        self, event: MessageEvent, matcher: Matcher, bot: Bot, *args, **kwargs
    ):
        """Initialize chat object

        Args:
            event: MessageEvent
            matcher: Matcher
            bot: Bot
            train: Training data (system prompts)
            user_input: Input from the user
            context: Memory context for the session
            session_id: Unique identifier for the session
            callback: Callback function to be called when returning response
            config: Config used for this call
            preset: Preset used for this call
            auto_create_session: Whether to automatically create a session if it does not exist
            hook_args: Arguments could be passed to the Matcher function
            hook_kwargs: Keyword arguments could be passed to the Matcher function
            queue_size: Maximum number of message chunks to be stored in the queue
            overflow_queue_size: Maximum number of message chunks to be stored in the overflow queue
        """
        super().__init__(*args, **kwargs)
        self.event = event
        self.matcher = matcher
        self.bot = bot
        self.bot_config = config_manager.config

    async def _run(self):
        """运行聊天处理流程

        执行消息处理的主要逻辑，包括获取用户信息、处理消息内容、
        管理上下文长度和token限制，以及发送响应。
        """
        debug_log("开始运行聊天处理流程..")
        event = self.event
        data = self.data
        bot = self.bot
        user_id = event.user_id
        config = self.config
        debug_log("管理会话上下文..")
        await self._manage_sessions()
        debug_log("会话管理完成")

        if isinstance(event, GroupMessageEvent):
            # 群聊消息处理
            debug_log("处理群聊消息")
            group_id = event.group_id

            user_name = (
                (await bot.get_group_member_info(group_id=group_id, user_id=user_id))[
                    "nickname"
                ]
                if not config.function.use_user_nickname
                else event.sender.nickname
            )
            role = await self._get_user_role(group_id, user_id)
        else:
            debug_log("处理私聊消息")
            user_name = (
                await get_friend_name(event.user_id, bot=bot)
                if not isinstance(event, GroupMessageEvent)
                else event.sender.nickname
            )
            role = ""
        debug_log(f"获取用户信息完成: {user_name}, 角色: {role}")

        content = await synthesize_message(event.get_message(), bot)
        self.last_call = datetime.now(utc)
        debug_log(f"合成消息完成: {content}")

        if content.strip() == "":
            content = ""
        if event.reply:
            group_id = event.group_id if isinstance(event, GroupMessageEvent) else None
            debug_log("处理引用消息..")
            content = await self._handle_reply(event.reply, bot, group_id, content)

        reply_pics = self._get_reply_pics()
        debug_log(f"获取引用图片完成，共 {len(reply_pics)} 张")

        content = await synthesize_message_to_msg(
            event, role, self.timestamp, str(user_name), str(user_id), content
        )
        if isinstance(content, list):
            content.extend(reply_pics)
        data.memory.messages.append(Message(role="user", content=content))
        debug_log(f"添加用户消息到记忆，当前消息总数: {len(data.memory.messages)}")

        self.train["content"] = (
            "<SCHEMA>\n"
            + "你在纯文本环境工作，不允许使用MarkDown回复，你的工作环境是一个社交软件，我会提供聊天记录，你可以从这里面获取一些关键信息，比如时间与用户身份"
            + "（e.g.: [管理员/群主/自己/群员][YYYY-MM-DD weekday hh:mm:ss AM/PM][昵称（QQ号）]说:<内容>），但是请不要以聊天记录的格式做回复，而是纯文本方式。"
            + "请以你自己的角色身份参与讨论，交流时不同话题尽量不使用相似句式回复，用户与你交谈的信息在用户的消息输入内。"
            + "你的设定将在<SYSTEM_INSTRUCTIONS>标签对内，对于先前对话的摘要位于<SUMMARY>标签对内，"
            + "\n</SCHEMA>\n"
            + "<SYSTEM_INSTRUCTIONS>\n"
            + (
                self.train["content"]
                .replace("{cookie}", config.cookies.cookie)
                .replace("{self_id}", str(event.self_id))
                .replace("{user_id}", str(event.user_id))
                .replace("{user_name}", str(event.sender.nickname))
            )
            + "\n</SYSTEM_INSTRUCTIONS>"
            + f"\n<SUMMARY>\n{data.memory.abstract if config.llm_config.enable_memory_abstract else ''}\n</SUMMARY>"
        )

        debug_msg = (
            f"当前群组提示词：\n{config_manager.group_train}"
            if isinstance(event, GroupMessageEvent)
            else f"当前私聊提示词：\n{config_manager.private_train}"
        )
        debug_log(debug_msg)
        debug_log(self.train["content"])

        debug_log("开始应用记忆限制..")
        async with MemoryLimiter(self.data, self.train) as lim:
            await lim.run_enforce()
            abs_usage = lim.usage
            self.data = lim.memory
        debug_log("记忆限制应用完成")

        send_messages = self._prepare_send_messages()
        debug_log(f"准备发送消息完成，消息数量: {len(send_messages)}")
        response = await self._process_chat(send_messages, abs_usage)
        debug_log("聊天处理完成，准备发送响应")
        await self.send_response(response.content)
        debug_log("开始保存记忆数据..")
        await self.data.save(event)
        debug_log("记忆数据保存完成")

    async def send_response(self, response: str):
        """发送聊天模型的回复，根据配置选择不同的发送方式。

        Args:
            response: 模型响应内容
        """
        self.last_call = datetime.now(utc)
        debug_log(f"发送响应: {response[:50]}..")  # 只显示前50个字符
        if not self.config.function.nature_chat_style:
            await self.matcher.send(
                MessageSegment.reply(self.event.message_id)
                + MessageSegment.text(response)
            )
        elif response_list := split_message_into_chats(response):
            for message in response_list:
                await self.matcher.send(MessageSegment.text(message))
                await asyncio.sleep(
                    random.randint(1, 3) + (len(message) // random.randint(80, 100))
                )

    async def _process_chat(
        self,
        send_messages: SEND_MESSAGES,
        extra_usage: UniResponseUsage[int] | None = None,
    ) -> UniResponse[str, None]:
        """调用聊天模型生成回复，并触发相关事件。

        Args:
            send_messages: 发送消息列表
            extra_usage: 额外的token使用量信息

        Returns:
            模型响应
        """
        self.last_call = datetime.now(utc)

        def add_usage(ins: InsightsModel | MemoryModel, usage: UniResponseUsage[int]):
            if isinstance(ins, InsightsModel):
                ins.token_output += usage.completion_tokens
                ins.token_input += usage.prompt_tokens
            else:
                ins.input_token_usage += usage.prompt_tokens
                ins.output_token_usage += usage.completion_tokens

        event = self.event
        bot = self.bot
        data = self.data
        debug_log(f"开始处理聊天，发送消息数量: {len(send_messages)}")

        if config_manager.config.matcher_function:
            debug_log("触发匹配器函数..")
            chat_event = BeforeChatEvent(
                nbevent=event,
                send_message=send_messages,
                model_response="",
                user_id=event.user_id,
            )
            await MatcherManager.trigger_event(chat_event, event, bot)
            send_messages = chat_event.get_send_message().unwrap()

        debug_log("调用聊天模型..")
        response = await get_chat(send_messages)

        if config_manager.config.matcher_function:
            debug_log("触发聊天事件..")
            chat_event = ChatEvent(
                nbevent=event,
                send_message=send_messages,
                model_response=response.content or "",
                user_id=event.user_id,
            )
            await MatcherManager.trigger_event(chat_event, event, bot)
            response.content = chat_event.model_response

        debug_log("计算token使用情况..")
        tokens = await get_tokens(send_messages, response)
        # 记录模型回复
        data.memory.messages.append(
            Message[str](
                content=response.content,
                role="assistant",
            )
        )
        debug_log(f"添加助手回复到记忆，当前消息总数: {len(data.memory.messages)}")

        insights = await InsightsModel.get()
        debug_log(f"获取洞察数据完成，使用计数: {insights.usage_count}")

        # 写入全局统计
        insights.usage_count += 1
        add_usage(insights, tokens)
        if extra_usage:
            add_usage(insights, extra_usage)
        await insights.save()
        debug_log(f"更新全局统计完成，使用计数: {insights.usage_count}")

        # 写入记忆数据
        for d, ev in (
            (
                (data, event),
                (
                    await get_memory_data(user_id=event.user_id),
                    FakeEvent(
                        time=0,
                        self_id=0,
                        post_type="",
                        user_id=event.user_id,
                    ),
                ),
            )
            if hasattr(event, "group_id")
            else ((data, event),)
        ):
            d.usage += 1  # 增加使用次数
            add_usage(d, tokens)
            if extra_usage:
                add_usage(d, extra_usage)
            debug_log(f"更新记忆数据，使用次数: {d.usage}")
            await d.save(ev)

        debug_log("聊天处理完成")
        return response

    async def _handle_reply(
        self, reply: Reply, bot: Bot, group_id: int | None, content: str
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
        self.last_call = datetime.now(utc)
        if not reply.sender.user_id:
            return content
        dt_object = datetime.fromtimestamp(reply.time)
        weekday = dt_object.strftime("%A")
        formatted_time = dt_object.strftime("%Y-%m-%d %I:%M:%S %p")
        role = (
            await self._get_user_role(group_id, reply.sender.user_id)
            if group_id
            else ""
        )

        reply_content = await synthesize_message(reply.message, bot)
        result = f"{content}\n<MESSAGE_REFERED>\n{formatted_time} {weekday} [{role}]{reply.sender.nickname}（QQ:{reply.sender.user_id}）说：{reply_content}\n</MESSAGE_REFERED>"
        debug_log(f"处理引用消息完成: {result[:50]}..")
        return result

    def _get_reply_pics(
        self,
    ) -> list[ImageContent]:
        """获取引用消息中的图片内容

        Returns:
            图片内容列表
        """
        self.last_call = datetime.now(utc)
        if reply := self.event.reply:
            msg = reply.message
            images = [
                ImageContent(image_url=ImageUrl(url=url))
                for seg in msg
                if seg.type == "image" and (url := seg.data.get("url")) is not None
            ]
            debug_log(f"获取引用图片完成，共 {len(images)} 张")
            return images
        return []

    async def _get_user_role(self, group_id: int, user_id: int) -> str:
        """获取用户在群聊中的身份（群主、管理员或普通成员）。

        Args:
            group_id: 群组ID
            user_id: 用户ID

        Returns:
            用户角色字符串
        """
        self.last_call = datetime.now(utc)
        role_data = await self.bot.get_group_member_info(
            group_id=group_id, user_id=user_id
        )
        role = role_data["role"]
        role_str = {"admin": "群管理员", "owner": "群主", "member": "普通成员"}.get(
            role, "[获取身份失败]"
        )
        debug_log(f"获取用户角色完成: {role_str}")
        return role_str

    async def _manage_sessions(
        self,
    ):
        """管理会话上下文：
        - 控制会话超时和历史记录。
        - 提供"继续"功能以恢复上下文。

        """
        self.last_call = datetime.now(utc)
        debug_log("开始管理会话上下文..")
        event = self.event
        data = self.data
        matcher = self.matcher
        bot = self.bot
        config = self.bot_config
        if config.session.session_control:
            session_clear_map: dict[str, SessionTemp] = (
                chat_manager.session_clear_group
                if isinstance(event, GroupEvent)
                else chat_manager.session_clear_user
            )
            session_id = self.session_id
            try:
                if session := session_clear_map.get(session_id):
                    debug_log(f"找到会话清除记录: {session_id}")
                    if "继续" not in event.message.extract_plain_text():
                        debug_log("消息中不包含'继续'，清除会话记录")
                        del session_clear_map[session_id]
                        return

                # 检查会话超时
                time_now = time.time()
                debug_log(
                    f"检查会话超时，当前时间: {time_now}, 数据时间戳: {data.time}"
                )
                if (time_now - data.time) >= (
                    float(self.bot_config.session.session_control_time * 60)
                ):
                    debug_log("会话超时，开始创建新会话..")
                    data.sessions.append(
                        SessionMemoryModel(messages=data.memory.messages, time=time_now)
                    )
                    if (
                        len(data.sessions)
                        > config_manager.config.session.session_control_history
                    ):
                        offset = (
                            len(data.sessions)
                            - config_manager.config.session.session_control_history
                        )
                        dropped_sesssions = data.sessions[:offset]
                        data.sessions = data.sessions[offset:]
                        async with get_session() as session:
                            for i in dropped_sesssions:
                                try:
                                    debug_log(f"删除过期会话: {i.id}")
                                    await i.delete(session)
                                except Exception as e:  # noqa: PERF203
                                    logger.warning(f"删除Session{i.id}失败\n{e}")
                            await session.commit()
                    data.memory.messages = []
                    timestamp = data.timestamp
                    data.timestamp = time_now
                    await data.save(event, raise_err=True)
                    if not (
                        (time_now - timestamp)
                        > float(config.session.session_control_time * 60 * 2)
                    ):
                        debug_log("发送继续聊天提示")
                        chated = await matcher.send(
                            f'如果想和我继续用之前的上下文聊天，快at我回复✨"继续"✨吧！\n（超过{config.session.session_control_time}分钟没理我我就会被系统抱走存档哦！）'
                        )
                        session_clear_map[session_id] = SessionTemp(
                            message_id=chated["message_id"], timestamp=datetime.now()
                        )

                        return await matcher.finish()

                elif (
                    session := session_clear_map.get(session_id)
                ) and "继续" in event.message.extract_plain_text():
                    debug_log("检测到'继续'消息，恢复上下文..")
                    with contextlib.suppress(Exception):
                        if time_now - session.timestamp.timestamp() < 100:
                            await bot.delete_msg(message_id=session.message_id)

                    session_clear_map.pop(session_id, None)

                    data.memory.messages = data.sessions[-1].messages
                    session = data.sessions.pop()
                    await session.delete()
                    await data.save(event, raise_err=True)
                    return await matcher.finish("让我们继续聊天吧～")

            finally:
                data.time = time.time()
                debug_log("会话上下文管理完成")

    async def _throw(self, e: BaseException):
        """处理异常：
        - 通知用户出错。
        - 记录日志并通知管理员。

        Args:
            e: 异常对象
        """
        if isinstance(e, CancelledError):
            if hasattr(self, "matcher"):
                await self.matcher.send("成功终止了对话。")
            return
        self._err = e
        if hasattr(self, "matcher"):
            await self.matcher.send("出错了稍后试试吧（错误已反馈）")
        logger.opt(exception=e, colors=True).exception("程序发生了未捕获的异常")

    def get_snapshot(self) -> ChatObjectMeta:
        """获取聊天对象的快照

        Returns:
            聊天对象元数据
        """
        return ChatObjectMeta.model_validate(self, from_attributes=True)


class SessionTemp(BaseModel):
    message_id: int
    timestamp: datetime = Field(default_factory=datetime.now)


@dataclass
class SessionTempManager:
    session_clear_group: dict[str, SessionTemp] = field(default_factory=dict)
    session_clear_user: dict[str, SessionTemp] = field(default_factory=dict)


chat_manager = SessionTempManager()
