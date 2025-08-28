"""聊天插件匹配器管理模块

该模块负责管理聊天插件中的所有事件匹配器，包括消息、命令和通知事件的处理。
"""

from nonebot import MatcherGroup, on_command
from nonebot.rule import Rule

from ..menu.models import MatcherData
from .check_rule import (
    is_bot_admin,
    is_bot_enabled,
    is_group_admin,
    is_group_admin_if_is_in_group,
    should_respond_to_message,
)
from .handlers.add_notices import add_notices
from .handlers.chat import chat
from .handlers.choose_prompt import choose_prompt
from .handlers.debug_switchs import debug_switchs
from .handlers.del_memory import del_memory
from .handlers.disable import disable
from .handlers.enable import enable
from .handlers.fakepeople_switch import switch
from .handlers.insights import insights
from .handlers.poke_event import poke_event
from .handlers.presets import presets
from .handlers.prompt import prompt
from .handlers.recall import recall
from .handlers.sessions import sessions
from .handlers.set_preset import set_preset

# 创建基础匹配器组，所有匹配器都需满足is_bot_enabled规则
base_matcher = MatcherGroup(rule=is_bot_enabled)

# 添加通知事件处理器
base_matcher.on_notice(
    priority=5,
    block=False,
).append_handler(add_notices)

base_matcher.on_notice(
    priority=5,
    block=False,
).append_handler(poke_event)

base_matcher.on_notice(
    priority=5,
    block=False,
).append_handler(recall)

# 添加消息事件处理器，处理聊天消息
base_matcher.on_message(
    block=False,
    priority=11,
    rule=Rule(should_respond_to_message, is_bot_enabled),
).append_handler(chat)

# 添加各种命令处理器
base_matcher.on_command(
    "prompt",
    priority=10,
    block=True,
    permission=is_group_admin_if_is_in_group,
    state=MatcherData(
        name="设置系统提示",
        description="设置系统提示词，用于指导AI回复",
        usage="/prompt <提示词内容>",
    ).model_dump(),
).append_handler(prompt)

base_matcher.on_command(
    "presets",
    priority=10,
    block=True,
    permission=is_bot_admin,
    state=MatcherData(
        name="预设列表",
        description="查看所有可用的预设列表",
        usage="/presets",
    ).model_dump(),
).append_handler(presets)

base_matcher.on_command(
    "set_preset",
    aliases={"设置预设", "设置模型预设"},
    priority=10,
    block=True,
    permission=is_bot_admin,
    state=MatcherData(
        name="设置预设",
        description="设置当前会话使用的预设",
        usage="/set_preset <预设名>",
    ).model_dump(),
).append_handler(set_preset)

base_matcher.on_command(
    "debug",
    priority=10,
    block=True,
    permission=is_bot_admin,
    state=MatcherData(
        name="调试模式",
        description="切换调试模式，用于查看详细日志",
        usage="/debug <on|off>",
    ).model_dump(),
).append_handler(debug_switchs)

base_matcher.on_command(
    "autochat",
    aliases={"自动回复", "autoreply"},
    priority=10,
    block=True,
    permission=is_group_admin,
    state=MatcherData(
        name="自动聊天开关",
        description="切换自动回复模式",
        usage="/autochat <on|off>",
    ).model_dump(),
).append_handler(switch)

base_matcher.on_command(
    "choose_prompt",
    priority=10,
    block=True,
    permission=is_bot_admin,
    state=MatcherData(
        name="选择提示词",
        description="从预设提示词中选择一个",
        usage="/choose_prompt",
    ).model_dump(),
).append_handler(choose_prompt)

base_matcher.on_command(
    "sessions",
    priority=10,
    block=True,
    permission=is_bot_admin,
    state=MatcherData(
        name="会话管理",
        description="管理当前所有会话",
        usage="/sessions [list|clear]",
    ).model_dump(),
).append_handler(sessions)

base_matcher.on_command(
    "del_memory",
    aliases={"失忆", "删除记忆", "删除历史消息", "删除回忆"},
    block=True,
    priority=10,
    permission=is_group_admin,
    state=MatcherData(
        name="删除记忆",
        description="删除AI的历史记忆",
        usage="/del_memory",
    ).model_dump(),
).append_handler(del_memory)

on_command(
    "enable",
    aliases={"启用聊天", "enable_chat"},
    block=True,
    priority=10,
    permission=is_group_admin,
    state=MatcherData(
        name="启用聊天",
        description="在当前群组启用AI聊天功能",
        usage="/enable",
    ).model_dump(),
).append_handler(enable)

on_command(
    "disable",
    aliases={"禁用聊天", "disable_chat"},
    block=True,
    priority=10,
    permission=is_group_admin,
    state=MatcherData(
        name="禁用聊天",
        description="在当前群组禁用AI聊天功能",
        usage="/disable",
    ).model_dump(),
).append_handler(disable)

base_matcher.on_command(
    "insights",
    aliases={"今日用量"},
    block=True,
    priority=10,
    state=MatcherData(
        name="用量统计",
        description="查看今日AI用量统计",
        usage="/insights [global]",
    ).model_dump(),
).append_handler(insights)
