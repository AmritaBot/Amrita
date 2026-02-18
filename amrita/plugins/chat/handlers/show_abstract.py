from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.matcher import Matcher

from amrita.plugins.chat.utils.sql import get_any_id

from ..check_rule import is_group_admin_if_is_in_group
from ..utils.app import CachedUserDataRepository


async def abstract_show(bot: Bot, event: MessageEvent, matcher: Matcher):
    if not await is_group_admin_if_is_in_group(event, bot):
        return
    data = await CachedUserDataRepository().get_memory(*get_any_id(event))
    await matcher.send(f"当前对话上下文摘要：{str(data.memory_json.abstract) or '无'}")
    data.clean()  # Ensure the memory is not dirty
