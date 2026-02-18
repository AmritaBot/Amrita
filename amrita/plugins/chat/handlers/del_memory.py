from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.matcher import Matcher

from amrita.plugins.chat.utils.sql import get_any_id

from ..check_rule import is_group_admin_if_is_in_group
from ..utils.app import CachedUserDataRepository


async def del_memory(bot: Bot, event: MessageEvent, matcher: Matcher):
    """处理删除记忆的指令"""
    if not await is_group_admin_if_is_in_group(event, bot):
        return
    data = await CachedUserDataRepository().get_memory(*get_any_id(event))
    data.memory_json.messages.clear()
    await CachedUserDataRepository().update_memory_data(data)
    await matcher.send(message="上下文已清除")
    logger.info(
        f"{event.get_event_name()}:{getattr(event, 'group_id') if hasattr(event, 'group_id') else event.user_id} 的记忆已清除"
    )
