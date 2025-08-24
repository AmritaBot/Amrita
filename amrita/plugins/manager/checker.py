import contextlib
from collections import defaultdict
from typing import Any

from nonebot import logger, on_command, on_message, on_notice
from nonebot.adapters import Bot
from nonebot.adapters.onebot.v11 import (
    GroupBanNoticeEvent,
    GroupMessageEvent,
    Message,
    MessageEvent,
)
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor
from nonebot.params import CommandArg
from nonebot.rule import (
    CommandRule,
    EndswithRule,
    FullmatchRule,
    KeywordsRule,
    RegexRule,
    ShellCommandRule,
    StartswithRule,
    ToMeRule,
)
from pydantic import BaseModel

from amrita import get_amrita_config
from amrita.plugins.menu.models import MatcherData
from amrita.plugins.perm.API.admin import is_lp_admin
from amrita.utils.admin import send_to_admin

from .models import add_usage
from .status_manager import StatusManager
from .utils import TokenBucket

watch_group = defaultdict(
    lambda: TokenBucket(rate=1 / get_amrita_config().rate_limit, capacity=1)
)
watch_user = defaultdict(
    lambda: TokenBucket(rate=1 / get_amrita_config().rate_limit, capacity=1)
)


@on_notice(block=False, priority=10).handle()
async def _(event: GroupBanNoticeEvent):
    if event.user_id != event.self_id:
        return
    await send_to_admin(
        f"{get_amrita_config().bot_name}在群{event.group_id}中{f'被禁言了{event.duration / 60}分钟' if event.duration else '被解除了禁言'}，请不要错过这条消息。"
    )


@on_command(
    "set_enable",
    priority=2,
    state=MatcherData(
        name="Bot可用状态设置",
        usage="/set_enable <true/false>",
        description="设置Bot状态",
    ).model_dump(),
).handle()
async def _(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not await is_lp_admin(event):
        return
    arg = args.extract_plain_text().strip()
    if arg in ("true", "yes", "1", "on"):
        StatusManager().set_disable(False)
        await matcher.finish("已启用")
    elif arg in ("false", "no", "0", "off"):
        StatusManager().set_disable(True)
        await matcher.finish("已关闭")
    else:
        await matcher.finish("请输入正确的参数，true/yes/1/on/false/no/0/off")


@on_message(priority=1, block=False).handle()
async def _(bot: Bot):
    try:
        logger.debug("Received message.")
        await add_usage(bot.self_id, 1, 0)
    except Exception as e:
        logger.warning(e)


@run_preprocessor
async def run(matcher: Matcher, event: MessageEvent):
    has_text_rule = any(
        isinstance(
            checker.call,
            FullmatchRule
            | CommandRule
            | StartswithRule
            | EndswithRule
            | KeywordsRule
            | ShellCommandRule
            | RegexRule
            | ToMeRule,
        )
        for checker in matcher.rule.checkers
    )  # 检查该匹配器是否有文字类匹配类规则
    if not has_text_rule:
        return
    ins_id = str(
        event.group_id if isinstance(event, GroupMessageEvent) else event.user_id
    )
    data = watch_group if isinstance(event, GroupMessageEvent) else watch_user
    bucket = data[ins_id]
    if not bucket.consume() and (not await is_lp_admin(event)):
        raise IgnoredException("Rate limit exceeded, operation ignored.")
    if (not StatusManager().ready) and (not await is_lp_admin(event)):
        with contextlib.suppress(Exception):
            await matcher.send("正在维护/数据迁移中，暂时不支持该操作！")
        raise IgnoredException("Maintenance in progress, operation not supported.")


@Bot.on_calling_api
async def handle_api_call(bot: Bot, api: str, data: dict[str, Any]):
    if "send" in api and "msg" in api:
        try:
            await add_usage(bot.self_id, 0, 1)
        except Exception as e:
            logger.warning(e)


class Status(BaseModel):
    lables: list[str]
    data: list[int]
