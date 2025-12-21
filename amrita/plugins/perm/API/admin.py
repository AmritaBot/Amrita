from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Event

from ..config import DataManager
from .rules import UserPermissionChecker

ENV_ADMINS = get_driver().config.superusers


async def is_lp_admin(event: Event) -> bool:
    """
    判断是否为管理员
    """
    user_id = event.get_user_id()

    return user_id in ENV_ADMINS or (
        await (UserPermissionChecker("lp.admin").checker())(event)
        and DataManager().config.enable
    )
