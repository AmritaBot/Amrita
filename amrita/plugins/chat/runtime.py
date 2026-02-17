import contextlib
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
from amrita_core.types import ImageContent, ImageUrl, TextContent
from nonebot import logger
from nonebot.adapters.onebot.v11 import (
    Bot,
)
from nonebot.adapters.onebot.v11.event import (
    GroupMessageEvent,
    MessageEvent,
    Reply,
)
from nonebot.matcher import Matcher
from pydantic import BaseModel, Field
from pytz import utc
from typing_extensions import override

from amrita.plugins.chat.utils.app import (
    AwaredMemory,
    CachedUserDataRepository,
    MemorySchema,
)
from amrita.plugins.chat.utils.event import GroupEvent

from .config import Config, config_manager
from .utils.functions import (
    get_friend_name,
    synthesize_message,
)
from .utils.sql import (
    MemorySessions,
    UserDataExecutor,
    get_any_id,
    get_uni_user_id,
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
    data: AwaredMemory  # type: ignore
    memory: MemorySchema
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
        self,
        event: MessageEvent,
        matcher: Matcher,
        bot: Bot,
        *args,
        **kwargs,
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
        config = self.bot_config
        self.memory = await CachedUserDataRepository().get_memory(*get_any_id(event))
        self.data = self.memory.memory_json  # type: ignore[Assignment]
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
        self.user_input = content
        debug_log(f"添加用户消息到记忆，当前消息总数: {len(data.messages)}")

        self.train["content"] = (
            "<SCHEMA_EXTENSIONS>\n"
            + "你在纯文本环境工作，不允许使用MarkDown回复，你的工作环境是一个社交软件，我会提供聊天记录，你可以从这里面获取一些关键信息，比如时间与用户身份"
            + "（e.g.: [管理员/群主/自己/群员][YYYY-MM-DD weekday hh:mm:ss AM/PM][昵称（QQ号）]说:<内容>），但是请不要以聊天记录的格式做回复，而是纯文本方式。"
            + "请以你自己的角色身份参与讨论，交流时不同话题尽量不使用相似句式回复，用户与你交谈的信息在用户的消息输入内。"
            + "\n</SCHEMA_EXTENSION>\n"
            + (
                self.train["content"]
                .replace("{cookie}", config.cookies.cookie)
                .replace("{self_id}", str(event.self_id))
                .replace("{user_id}", str(event.user_id))
                .replace("{user_name}", str(event.sender.nickname))
            )
        )

        await super()._run()

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
            uni_id = get_uni_user_id(event)
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
                    async with UserDataExecutor(uni_id) as executor:
                        await executor.add_session(data)
                    await MemorySessions._expire(
                        uni_id, config.session.session_control_history
                    )
                    data.messages = []
                    timestamp = data.time
                    data.time = time_now
                    CachedUserDataRepository._cached_memory.pop(uni_id, None)
                    self.memory.memory_json = data
                    await CachedUserDataRepository().update_memory_data(self.memory)
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
                    sessions = await CachedUserDataRepository().get_sesssions(
                        *get_any_id(event)
                    )
                    data.messages = sessions[-1].data.messages
                    session = sessions[-1]
                    async with UserDataExecutor(uni_id) as executor:
                        await executor.remove_session(session.id)
                    CachedUserDataRepository._cached_sessions.pop(uni_id, None)
                    self.memory.memory_json = data
                    await CachedUserDataRepository().update_memory_data(self.memory)
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

    @override
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
