import json
import random
import typing
from typing import Any

from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot
from nonebot.log import logger

from amrita.plugins.chat.utils.sql import SEND_MESSAGES, ToolCall, UniResponse
from amrita.utils.admin import send_to_admin

from .config import Config, config_manager
from .event import UniChatEvent
from .on_event import on_before_chat, on_chat
from .utils.libchat import (
    tools_caller,
)
from .utils.llm_tools.builtin_tools import (
    REPORT_TOOL_HIGH,
    REPORT_TOOL_LOW,
    REPORT_TOOL_MEDIUM,
    report,
)
from .utils.memory import (
    get_memory_data,
)

prehook = on_before_chat(block=False, priority=2)
checkhook = on_before_chat(block=False, priority=1)
posthook = on_chat(block=False, priority=1)


BUILTIN_TOOLS_NAME = {
    REPORT_TOOL_MEDIUM.function.name,
    STOP_TOOL.function.name,
    REASONING_TOOL.function.name,
    PROCESS_MESSAGE.function.name,
}

AGENT_PROCESS_TOOLS = (
    REASONING_TOOL,
    STOP_TOOL,
    PROCESS_MESSAGE,
)


async def report_to_hooman(
    config: Config,
    /,
    text: str,
    level: Literal["low", "medium", "high"] = "medium",
    exclude_context: bool = False,
    exclude_system_prompt: bool = False,
):
    if not config.llm.tools.enable_report:
        return ReportResult(action=ReportAction.ALLOW, content=text)

    match config.llm.tools.report_invoke_level:
        case "low":
            threshold = 0.3
        case "medium":
            threshold = 0.2
        case "high":
            threshold = 0.1
        case _:
            threshold = 0.2

    if level_value(level) >= threshold:
        if (
            exclude_context
            and config.llm.tools.report_exclude_context
            and config.llm.tools.report_exclude_system_prompt
        ):
            return ReportResult(action=ReportAction.ALLOW, content=text)
        elif config.llm.tools.report_exclude_system_prompt:
            # 只排除系统提示词
            return ReportResult(action=ReportAction.REPORT, content=text)
        elif config.llm.tools.report_exclude_context:
            # 只排除上下文
            return ReportResult(action=ReportAction.REPORT, content=text)

        return ReportResult(action=ReportAction.REPORT, content=text)

    return ReportResult(action=ReportAction.ALLOW, content=text)


@checkhook.handle()
async def text_check(event: UniChatEvent) -> None:
    config: Config = config_manager.config
    if not config.llm_config.tools.enable_report:
        checkhook.pass_event()
    logger.info("Content checking in progress......")
    bot = get_bot()
    match config.llm_config.tools.report_invoke_level:
        case "low":
            tool_list = [REPORT_TOOL_LOW]
        case "medium":
            tool_list = [REPORT_TOOL_MEDIUM]
        case "high":
            tool_list = [REPORT_TOOL_HIGH]
        case _:
            raise ValueError("Invalid report_invoke_level")
    msg: SEND_MESSAGES = event.get_context_messages().unwrap()
    if (
        config.llm_config.tools.report_exclude_context
        and config.llm_config.tools.report_exclude_system_prompt
    ):
        msg = [event.get_context_messages().get_user_query()]
    elif config.llm_config.tools.report_exclude_system_prompt:
        msg = event.get_context_messages().get_memory()
    elif config.llm_config.tools.report_exclude_context:
        msg = [
            event.get_context_messages().get_train(),
            event.get_context_messages().get_user_query(),
        ]
    if not msg:
        logger.warning("Message list is empty, skipping content check")
        return
    response: UniResponse[None, list[ToolCall] | None] = await tools_caller(
        msg, tool_list
    )
    nonebot_event = event.nb_event
    if tool_calls := response.tool_calls:
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_args: dict[str, Any] = json.loads(tool_call.function.arguments)
            if function_name == REPORT_TOOL_MEDIUM.function.name:
                if not function_args.get("invoke"):
                    return
                await report(
                    event,
                    function_args,
                    typing.cast(Bot, bot),
                )
                if config_manager.config.llm_config.tools.report_then_block:
                    data = await get_memory_data(nonebot_event)
                    data.memory.messages = []
                    await data.save(nonebot_event)
                    await bot.send(
                        nonebot_event,
                        random.choice(config_manager.config.llm_config.block_msg),
                    )
                    prehook.cancel_matcher()
            else:
                await send_to_admin(
                    f"[LLM-Report] Detected non-passed tool call: {function_name}, please feedback this issue to the model provider."
                )


async def check_limit(
    session: ChatSession,
    config: Config,
):
    # 检查使用限制
    if config_manager.config.llm.limit.enable:  # 这里可能需要创建limit配置
        if config_manager.config.llm.limit.max_tokens:  # 这里可能需要创建limit配置
            if (
                session.total_tokens >= config_manager.config.llm.limit.max_tokens
            ):  # 这里可能需要创建limit配置
                await session.send(
                    random.choice(
                        config_manager.config.llm.limit_msg
                    ),  # 这里可能需要创建limit_msg配置
                    at_sender=True,
                )
                return False
        if (
            config_manager.config.llm.limit.max_conversations
        ):  # 这里可能需要创建limit配置
            if (
                session.conversation_count
                >= config_manager.config.llm.limit.max_conversations
            ):  # 这里可能需要创建limit配置
                await session.send(
                    random.choice(
                        config_manager.config.llm.limit_msg
                    ),  # 这里可能需要创建limit_msg配置
                    at_sender=True,
                )
                return False

    return True


async def check_limit(
    session: ChatSession,
    config: Config,
):
    if config_manager.config.llm_config.limit.enable:  # 更新配置路径
        if config_manager.config.llm_config.limit.max_tokens:  # 更新配置路径
            if (
                session.total_tokens
                >= config_manager.config.llm_config.limit.max_tokens
            ):  # 更新配置路径
                await session.send(
                    random.choice(
                        config_manager.config.llm_config.limit_msg
                    ),  # 更新配置路径
                    at_sender=True,
                )
                prehook.cancel_matcher()
        if config_manager.config.llm_config.limit.max_conversations:  # 更新配置路径
            if (
                session.conversation_count
                >= config_manager.config.llm_config.limit.max_conversations
            ):  # 更新配置路径
                await session.send(
                    random.choice(
                        config_manager.config.llm_config.limit_msg
                    ),  # 更新配置路径
                    at_sender=True,
                )
                prehook.cancel_matcher()

    if (
        config_manager.config.llm.tools.report_then_block  # 更新配置路径
        and result.action == ReportAction.REPORT
    ):
        # 发送熔断消息
        await session.send(
            random.choice(config_manager.config.llm.block_msg),  # 更新配置路径
            at_sender=True,
        )
        # 清空会话
        await session.clear()
        prehook.cancel_matcher()
