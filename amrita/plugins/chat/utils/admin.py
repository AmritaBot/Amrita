from nonebot import logger
from nonebot.adapters.onebot.v11 import (
    Bot,
)

from amrita.utils.admin import send_to_admin


async def send_to_admin_as_error(msg: str, bot: Bot | None = None) -> None:
    logger.error(msg)
    await send_to_admin(msg, bot)
