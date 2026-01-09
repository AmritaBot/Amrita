"""聊天处理器模块

该模块实现了聊天功能的核心逻辑，包括群聊和私聊的处理、会话管理、消息处理等功能。
主要通过ChatObject类来处理消息，使用MemoryLimiter类来管理上下文长度和token数量限制。
"""

import asyncio
import contextlib
import copy
import random
import time
from datetime import datetime
from uuid import uuid4

from nonebot import get_driver, logger
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
from pydantic import BaseModel, Field
from pytz import utc
from typing_extensions import Self

from amrita.plugins.chat.builtin_hook import ChatException
from amrita.plugins.chat.utils.event import GroupEvent

from ..chatmanager import SessionTemp, chat_manager
from ..check_rule import FakeEvent
from ..config import Config, config_manager
from ..event import BeforeChatEvent, ChatEvent
from ..matcher import MatcherManager
from ..utils.functions import (
    get_current_datetime_timestamp,
    get_friend_name,
    split_message_into_chats,
    synthesize_message,
)
from ..utils.libchat import get_chat, get_tokens, text_generator
from ..utils.lock import get_group_lock, get_private_lock
from ..utils.memory import (
    Memory,
    MemoryModel,
    Message,
    ToolResult,
    get_memory_data,
)
from ..utils.models import (
    SEND_MESSAGES,
    ImageContent,
    ImageUrl,
    InsightsModel,
    TextContent,
    UniResponseUsage,
)
from ..utils.protocol import UniResponse
from ..utils.tokenizer import hybrid_token_count

command_prefix = get_driver().config.command_start or "/"


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


class ChatObjectMeta(BaseModel):
    """聊天对象元数据模型

    用于存储聊天对象的标识、事件和时间信息。
    """

    stream_id: str  # 聊天流ID
    event: MessageEvent  # 消息事件
    time: datetime = Field(default_factory=datetime.now)  # 创建时间


class MemoryLimiter:
    """上下文处理器

    该类负责处理聊天上下文的记忆长度和token数量限制，通过上下文摘要和消息删除等方式，
    确保聊天上下文在预设的限制范围内，避免超出模型处理能力。
    """

    memory: MemoryModel  # 要处理的记忆模型
    config: Config  # 配置对象
    usage: UniResponseUsage | None = None  # token使用情况，初始为None
    _train: dict[str, str]  # 训练数据（系统提示词）
    _dropped_messages: list[Message[str] | ToolResult]  # 被删除的消息列表
    _copied_messages: Memory  # 原始消息副本（用于异常时回滚）
    _abstract_instruction = """<<SYS>>
你是一个专业的上下文摘要器，严格按照用户指令执行摘要任务。
<</SYS>>

<<INSTRUCTIONS>>
1. 直接摘要用户输入的内容
2. 保持原文的核心信息和关键细节
3. 不产生任何额外内容、解释或评论
4. 摘要应简洁、准确、完整
<</INSTRUCTIONS>>

<<RULE>>
- 仅对用户提供文本进行摘要
- 不添加任何解释、评论或补充信息
- 不改变原文的主要意思
- 保持客观中立的语调
<</RULE>>

<<FORMATTING>>
用户输入 → 直接输出摘要结果
<</FORMATTING>>"""

    def __init__(self, memory: MemoryModel, train: dict[str, str]) -> None:
        """初始化上下文处理器

        Args:
            memory: 要处理的记忆模型
            train: 训练数据（系统提示词）
        """
        self.memory = memory
        self.config = config_manager.config
        self._train = train

    async def __aenter__(self) -> Self:
        """异步上下文管理器入口，初始化处理状态

        Returns:
            返回自身实例以供使用
        """
        self._dropped_messages = []
        self._copied_messages = copy.deepcopy(self.memory.memory)
        return self

    async def _make_abstract(self):
        """生成上下文摘要

        通过调用LLM将当前记忆中的所有消息内容摘要为一段简短的内容，
        以减少上下文长度，同时保留关键信息。
        """
        proportion = self.config.llm_config.memory_abstract_proportion  # 摘要比例
        index = int(len(self.memory.memory.messages) * proportion)
        dropped_part = self.memory.memory.messages[index:]
        self.memory.memory.messages = self.memory.memory.messages[:index]
        msg_list: SEND_MESSAGES = [
            Message[str](role="system", content=self._abstract_instruction),
            Message[str](
                role="user",
                content=(
                    "消息列表：\n```text\n".join(
                        [
                            f"{it}\n"
                            for it in text_generator(
                                self._dropped_messages + dropped_part, split_role=True
                            )
                        ]
                    )
                    + "\n```"
                ),
            ),
        ]
        logger.info("正在进行上下文摘要......")
        response = await get_chat(msg_list)
        usage = await get_tokens(msg_list, response)
        self.usage = usage
        logger.debug(f"获取到上下文摘要：{response.content}")
        self.memory.memory_abstract = response.content

    async def run_enforce(self):
        """执行记忆限制处理

        按顺序执行记忆长度限制和token数量限制，确保聊天上下文在预设范围内。
        该方法必须在异步上下文管理器中使用。

        Raises:
            RuntimeError: 当未在异步上下文管理器中使用时抛出
        """
        if not hasattr(self, "_dropped_messages") and not hasattr(
            self, "_copied_messages"
        ):
            raise RuntimeError(
                "MemoryLimiter is not initialized, please use use `async with MemoryLimiter(memory)` before calling."
            )
        await self._limit_length()
        await self._limit_tokens()
        if self.config.llm_config.enable_memory_abstract and self._dropped_messages:
            await self._make_abstract()

    async def _limit_length(self):
        """控制记忆长度，删除超出限制的旧消息，移除不支持的消息。"""
        is_multimodal = (
            await config_manager.get_preset(config_manager.config.preset)
        ).multimodal
        data = self.memory

        # Process multimodal messages when needed
        for message in data.memory.messages:
            if (
                isinstance(message.content, list)
                and not is_multimodal
                and message.role == "user"
            ):
                message_text = ""
                for content_part in message.content:
                    if content_part.type == "text":
                        message_text += content_part.text
                message.content = message_text

        # Enforce memory length limit
        while len(data.memory.messages) > 0:
            if data.memory.messages[0].role != "user":
                del data.memory.messages[0]
            elif len(data.memory.messages) > self.config.llm_config.memory_lenth_limit:
                self._dropped_messages.append(data.memory.messages.pop(0))
            else:
                break

    async def _limit_tokens(self):
        """控制 token 数量，删除超出限制的旧消息

        通过计算当前消息列表的token数量，当超出配置的session最大token限制时，
        逐步删除最早的消息直到满足token数量限制。
        """

        def get_token(memory: list[Message | ToolResult]) -> int:
            tk_tmp: int = 0
            for msg in text_generator(memory):
                tk_tmp += hybrid_token_count(
                    msg,
                    config_manager.config.llm_config.tokens_count_mode,
                )
            return tk_tmp

        train = self._train
        train_model = Message.model_validate(train)
        data = self.memory
        memory_l: list[Message | ToolResult] = [train_model, *data.memory.messages]
        if not config_manager.config.llm_config.enable_tokens_limit:
            return
        prompt_length = hybrid_token_count(train["content"])
        if prompt_length > config_manager.config.session.session_max_tokens:
            logger.warning(
                f"提示词大小过大！为{prompt_length}>{config_manager.config.session.session_max_tokens}！请调整提示词或者设置！"
            )
            return
        tk_tmp: int = get_token(memory_l)

        while tk_tmp > config_manager.config.session.session_max_tokens:
            if len(data.memory.messages) > 1:
                self._dropped_messages.append(data.memory.messages.pop(0))
            else:
                break

            tk_tmp: int = get_token(memory_l)
            memory_l = [train_model, *data.memory.messages]
            await asyncio.sleep(0)  # CPU 密集型任务可能造成性能问题，我们在这里让出协程

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口，处理异常情况下的回滚

        当发生异常时，将消息恢复到处理前的状态，确保数据一致性。

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常追踪栈
        """
        if exc_type is not None:
            logger.warning("Rolling back messages......")
            self.memory.memory.messages = self._copied_messages.messages
            return


class ChatObject:
    """聊天处理对象

    该类负责处理单次聊天会话，包括消息接收、上下文管理、模型调用和响应发送。
    """

    stream_id: str  # 聊天对象ID
    matcher: Matcher  # (lateinit) 匹配器
    bot: Bot  # (lateinit) Bot实例
    event: MessageEvent  # (lateinit) 消息事件
    config: Config  # 配置
    timestamp: str  # 时间戳(用于LLM)
    time: datetime  # 时间
    data: MemoryModel  # (lateinit) 记忆文件
    train: dict[str, str]  # 训练数据（根据群聊/私聊选择）
    _is_running: bool = False  # 是否正在运行
    _is_done: bool = False  # 是否已经完成

    def __init__(self) -> None:
        """初始化聊天对象"""
        self.timestamp = get_current_datetime_timestamp()
        self.time = datetime.now(utc)
        self.config = config_manager.config

    async def __call__(self, event: MessageEvent, matcher: Matcher, bot: Bot) -> None:
        """调用聊天对象处理消息

        Args:
            event: 消息事件
            matcher: 匹配器
            bot: Bot实例
        """
        if not self._is_running and not self._is_done:
            self.stream_id = uuid4().hex
            self.bot = bot
            self.matcher = matcher
            self.event = event
            self.train = copy.deepcopy(
                config_manager.group_train
                if isinstance(event, GroupMessageEvent)
                else config_manager.private_train
            )

            self._is_running = True
            try:
                lock = (
                    get_group_lock(event.group_id)
                    if isinstance(event, GroupMessageEvent)
                    else get_private_lock(event.user_id)
                )
                match self.config.function.chat_pending_mode:
                    case "queue":
                        pass
                    case "single":
                        if lock.locked():
                            return matcher.stop_propagation()
                    case "single_with_report":
                        if lock.locked():
                            await matcher.finish("聊天任务正在处理中，请稍后再试")
                async with lock:
                    self.data = await get_memory_data(event)
                    await self._run()
            except BaseException as e:
                if isinstance(e, ChatException):
                    raise
                await self._throw(e)
            finally:
                self._is_running = False
                self._is_done = True

        else:
            raise RuntimeError(
                f"ChatObject of event <{event.model_dump_json()}> is already running or done"
            )

    async def _run(self):
        """运行聊天处理流程

        执行消息处理的主要逻辑，包括获取用户信息、处理消息内容、
        管理上下文长度和token限制，以及发送响应。
        """
        event = self.event
        data = self.data
        bot = self.bot
        user_id = event.user_id
        config = self.config
        await self._manage_sessions()

        if isinstance(event, GroupMessageEvent):
            # 群聊消息处理
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
            user_name = (
                await get_friend_name(event.user_id, bot=bot)
                if not isinstance(event, GroupMessageEvent)
                else event.sender.nickname
            )
            role = ""
        content = await synthesize_message(event.get_message(), bot)

        if content.strip() == "":
            content = ""
        if event.reply:
            group_id = event.group_id if isinstance(event, GroupMessageEvent) else None
            content = await self._handle_reply(event.reply, bot, group_id, content)

        reply_pics = self._get_reply_pics()

        content = await synthesize_message_to_msg(
            event, role, self.timestamp, str(user_name), str(user_id), content
        )
        if isinstance(content, list):
            content.extend(reply_pics)
        data.memory.messages.append(Message(role="user", content=content))

        if chat_manager.debug:
            debug_msg = (
                f"当前群组提示词：\n{config_manager.group_train}"
                if isinstance(event, GroupMessageEvent)
                else f"当前私聊提示词：\n{config_manager.private_train}"
            )
            logger.debug(debug_msg)
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
            + f"\n<SUMMARY>{data.memory_abstract if config.llm_config.enable_memory_abstract else ''}\n</SUMMARY>"
        )
        async with MemoryLimiter(self.data, self.train) as lim:
            await lim.run_enforce()
            abs_usage = lim.usage
        send_messages = self._prepare_send_messages()
        response = await self._process_chat(send_messages, abs_usage)
        await self.send_response(response.content)

    async def send_response(self, response: str):
        """发送聊天模型的回复，根据配置选择不同的发送方式。

        Args:
            response: 模型响应内容
        """
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
        if config_manager.config.matcher_function:
            chat_event = BeforeChatEvent(
                nbevent=event,
                send_message=send_messages,
                model_response="",
                user_id=event.user_id,
            )
            await MatcherManager.trigger_event(chat_event, event, bot)
            send_messages = chat_event.get_send_message()

        response = await get_chat(send_messages)

        if config_manager.config.matcher_function:
            chat_event = ChatEvent(
                nbevent=event,
                send_message=send_messages,
                model_response=response.content or "",
                user_id=event.user_id,
            )
            await MatcherManager.trigger_event(chat_event, event, bot)

        tokens = await get_tokens(send_messages, response)
        # 记录模型回复
        data.memory.messages.append(
            Message(
                content=response.content,
                role="assistant",
            )
        )

        insights = await InsightsModel.get()

        # 写入全局统计
        insights.usage_count += 1
        add_usage(insights, tokens)
        if extra_usage:
            add_usage(insights, extra_usage)
        await insights.save()

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
            await d.save(ev)

        return response

    def _prepare_send_messages(
        self,
    ) -> list:
        """准备发送给聊天模型的消息列表，包括系统提示词数据和上下文。

        Returns:
            准备发送的消息列表
        """
        train: Message[str] = Message[str].model_validate(self.train)
        assert isinstance(train.content, str)
        data = self.data
        train.content += (
            f"\n以下是一些补充内容，如果与上面任何一条有冲突请忽略。\n<EXTRA>\n{data.prompt if data.prompt != '' else '无'}\n<EXTRA>"
            if self.config.function.allow_custom_prompt
            else ""
        )
        return [Message.model_validate(train), *copy.deepcopy(data.memory.messages)]

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
        return f"{content}\n<引用的消息>\n{formatted_time} {weekday} [{role}]{reply.sender.nickname}（QQ:{reply.sender.user_id}）说：{reply_content}\n</引用的消息>"

    def _get_reply_pics(
        self,
    ) -> list[ImageContent]:
        """获取引用消息中的图片内容

        Returns:
            图片内容列表
        """
        if reply := self.event.reply:
            msg = reply.message
            images = [
                ImageContent(image_url=ImageUrl(url=url))
                for seg in msg
                if seg.type == "image" and (url := seg.data.get("url")) is not None
            ]

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
        role = (
            await self.bot.get_group_member_info(group_id=group_id, user_id=user_id)
        )["role"]
        return {"admin": "群管理员", "owner": "群主", "member": "普通成员"}.get(
            role, "[获取身份失败]"
        )

    async def _manage_sessions(
        self,
    ):
        """管理会话上下文：
        - 控制会话超时和历史记录。
        - 提供"继续"功能以恢复上下文。

        """
        event = self.event
        data = self.data
        matcher = self.matcher
        bot = self.bot
        config = self.config
        if config.session.session_control:
            session_clear_map: dict[str, SessionTemp] = (
                chat_manager.session_clear_group
                if isinstance(event, GroupEvent)
                else chat_manager.session_clear_user
            )
            session_id = str(
                event.group_id
                if isinstance(event, GroupMessageEvent)
                else event.user_id
            )
            try:
                if session := session_clear_map.get(session_id):
                    if "继续" not in event.message.extract_plain_text():
                        del session_clear_map[session_id]
                        return

                # 检查会话超时
                time_now = time.time()
                if (time_now - data.timestamp) >= (
                    float(config_manager.config.session.session_control_time * 60)
                ):
                    data.sessions.append(
                        Memory(messages=data.memory.messages, time=time_now)
                    )
                    while (
                        len(data.sessions)
                        > config_manager.config.session.session_control_history
                    ):
                        data.sessions.remove(data.sessions[0])
                    data.memory.messages = []
                    timestamp = data.timestamp
                    data.timestamp = time_now
                    await data.save(event, raise_err=True)
                    if not (
                        (time_now - timestamp)
                        > float(config.session.session_control_time * 60 * 2)
                    ):
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
                    with contextlib.suppress(Exception):
                        if time_now - session.timestamp.timestamp() < 100:
                            await bot.delete_msg(message_id=session.message_id)

                    session_clear_map.pop(session_id, None)

                    data.memory.messages = data.sessions[-1].messages
                    data.sessions.pop()
                    await matcher.send("让我们继续聊天吧～")
                    await data.save(event, raise_err=True)
                    return await matcher.finish()

            finally:
                data.timestamp = time.time()

    async def _throw(self, e: BaseException):
        """处理异常：
        - 通知用户出错。
        - 记录日志并通知管理员。

        Args:
            e: 异常对象
        """
        if hasattr(self, "matcher"):
            await self.matcher.send("出错了稍后试试吧（错误已反馈）")
        logger.opt(exception=e, colors=True).exception("程序发生了未捕获的异常")

    def get_snapshot(self) -> ChatObjectMeta:
        """获取聊天对象的快照

        Returns:
            聊天对象元数据
        """
        return ChatObjectMeta.model_validate(self, from_attributes=True)


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
    return await ChatObject()(event, matcher, bot)
