import nonebot
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    MessageSegment,
)
from nonebot.matcher import Matcher

from amrita.config import get_amrita_config
from amrita.utils.send import send_forward_msg

from .manager import menu_mamager
from .models import MatcherData
from .utils import (
    generate_menu,
)

command_start = get_driver().config.command_start


@nonebot.on_fullmatch(
    tuple(
        [f"{prefix}menu" for prefix in command_start]
        + [f"{prefix}菜单" for prefix in command_start]
        + [f"{prefix}help" for prefix in command_start]
    ),
    state=MatcherData(
        name="Menu",
        description="展示菜单",
        usage="/menu",
    ).model_dump(),
    rule=lambda: not get_amrita_config().disable_builtin_menu,
).handle()
async def show_menu(matcher: Matcher, bot: Bot, event: MessageEvent):
    """显示菜单"""
    if not menu_mamager.plugins:
        await matcher.finish("菜单加载失败，请检查日志")

    menu_datas = generate_menu(menu_mamager.plugins)

    if not menu_datas:
        await matcher.finish("没有可用的菜单")

    menu_datas_pics = [
        MessageSegment.text(menu_datas_string) for menu_datas_string in menu_datas
    ]

    await send_forward_msg(
        bot,
        event,
        name="Menu",
        uin=str(bot.self_id),
        msgs=menu_datas_pics,
    )
