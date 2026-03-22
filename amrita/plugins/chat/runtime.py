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
from amrita_core import (
    ToolResult,
    get_config,
)
from amrita_core.config import AmritaConfig
from amrita_core.logging import debug_log
from nonebot import logger
from nonebot.adapters.onebot.v11 import (
    Bot,
)
from nonebot.adapters.onebot.v11.event import (
    MessageEvent,
)
from nonebot.matcher import Matcher
from pydantic import BaseModel, Field
from pytz import utc
from typing_extensions import final, override

from amrita.plugins.chat.utils.app import (
    AwaredMemory,
    CachedUserDataRepository,
    MemorySchema,
)

from .config import Config, config_manager
from .utils.sql import (
    MemorySessions,
    UserDataExecutor,
    get_any_id,
    get_uni_user_id,
)

LOCK = Lock()


@final
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
        self.event = event
        self.matcher = matcher
        self.bot = bot
        self.bot_config = config_manager.config
        super().__init__(*args, **kwargs)
        self.session_id = get_uni_user_id(event)
        self.config = get_config()

    @override
    async def _run(self) -> None:
        """运行聊天处理流程

        执行消息处理的主要逻辑，包括获取用户信息、处理消息内容、
        管理上下文长度和token限制，以及发送响应。
        """
        debug_log("开始运行聊天处理流程..")
        event = self.event
        config = self.bot_config
        self.memory = await CachedUserDataRepository().get_memory(*get_any_id(event))
        for mem in self.memory.memory_json.messages:
            if (
                not isinstance(mem, ToolResult)
                and mem.content is not None
                and isinstance(mem.content, list)
            ):
                mem.content = [i for i in mem.content if hasattr(i, "type")]
        self.data = self.memory.memory_json  # type: ignore[Assignment]
        data = self.data
        debug_log("管理会话上下文..")
        await self._manage_sessions()
        debug_log("会话管理完成")

        debug_log(f"添加用户消息到记忆，当前消息总数: {len(data.messages)}")

        self.train["content"] = (
            "<SCHEMA_EXTENSIONS>\n"
            + "你在纯文本环境工作，不允许使用MarkDown回复，你的工作环境是一个社交软件，我会提供聊天记录，你可以从这里面获取一些关键信息，比如时间与用户身份"
            + "（e.g.: [管理员/群主/自己/群员][YYYY-MM-DD weekday hh:mm:ss AM/PM][昵称（QQ号）]说:<内容>），但是请不要以聊天记录的格式做回复，而是纯文本方式。"
            + "请以你自己的角色身份参与讨论，交流时不同话题尽量不使用相似句式回复，用户与你交谈的信息在用户的消息输入内。<EXTRA>规则仅作为补充，如果与EXTRA规则上文有冲突，请遵循上文规则。"
            + "\n</SCHEMA_EXTENSION>\n"
            + (
                self.train["content"]
                .replace("{cookie}", config.cookies.cookie)
                .replace("{self_id}", str(event.self_id))
                .replace("{user_id}", str(event.user_id))
                .replace("{user_name}", str(event.sender.nickname))
            )
            + (
                f"<EXTRA>\n（此处是EXTRA规则，如果与上文有任何冲突，请忽略此EXTRA规则）\n{self.memory.extra_prompt}\n</EXTRA>"
                if self.bot_config.function.allow_custom_prompt
                else ""
            )
        )

        await super()._run()

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
                if getattr(event, "group_id", None) is not None
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
                    if (
                        (time_now - timestamp)
                        <= float(config.session.session_control_time * 60 * 2)
                        and config.session.session_allow_continue
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
