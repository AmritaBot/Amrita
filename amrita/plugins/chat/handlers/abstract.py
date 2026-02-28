from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from amrita.plugins.chat.utils.sql import get_any_id

from ..check_rule import is_group_admin_if_is_in_group
from ..utils.app import CachedUserDataRepository


async def abstract_show(
    bot: Bot, event: MessageEvent, matcher: Matcher, args: Message = CommandArg()
):
    if not await is_group_admin_if_is_in_group(event, bot):
        return
    data = await CachedUserDataRepository().get_memory(*get_any_id(event))
    arg = args.extract_plain_text().strip().split()
    if not arg:
        await matcher.send(
            f"当前对话上下文摘要：\n{str(data.memory_json.abstract) or '无'}"
        )
    elif len(arg) == 1:
        if arg[0] in ("clear", "clean", "reset"):
            data.memory_json.abstract = ""
            await CachedUserDataRepository().update_memory_data(data)
            await matcher.send("已清空对话上下文摘要")
        else:
            await matcher.send("参数错误")
    data.clean()  # Ensure the memory is not dirty
