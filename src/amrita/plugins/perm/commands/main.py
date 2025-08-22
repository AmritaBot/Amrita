from typing import Any, Protocol

from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.rule import to_me

from ..command_manager import command


class PermissionHandler(Protocol):
    async def execute(
        self, user_id: str, operation: str, target: str, value: str
    ) -> tuple[str, dict[str, Any]]:
        raise NotImplementedError("Not Implemented")


@command.command("", rule=to_me()).handle()
async def lp(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    args_list = args.extract_plain_text().strip().split()
    if not args_list:
        lp_0_help = "LP LitePerm\n请输入参数\nlp user\nlp chat_group\nlp perm_group\nlp command\n"

        await matcher.finish(lp_0_help)
