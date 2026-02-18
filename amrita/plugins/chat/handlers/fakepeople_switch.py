from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from ..utils.app import CachedUserDataRepository


async def switch(
    event: GroupMessageEvent, matcher: Matcher, args: Message = CommandArg()
):
    arg = args.extract_plain_text().strip()
    data = await CachedUserDataRepository().get_group_config(event.group_id)
    if arg in ("开启", "on", "启用", "enable"):
        if not data.autoreply:
            data.autoreply = True
            await data.save(event)
            await matcher.send("开启FakePeople")
        else:
            await matcher.send("已开启")
    elif arg in ("关闭", "off", "禁用", "disable"):
        if data.autoreply:
            data.autoreply = False
            await data.save(event)
            await matcher.send("关闭FakePeople")
        else:
            await matcher.send("已关闭")
    else:
        await matcher.send("请输入开启或关闭")
