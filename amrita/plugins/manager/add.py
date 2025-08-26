from nonebot import on_request
from nonebot.adapters.onebot.v11 import (
    Bot,
    FriendRequestEvent,
    GroupRequestEvent,
    RequestEvent,
)

from amrita.utils.admin import send_to_admin

from .blacklist.black import BL_Manager


@on_request(priority=1, block=True).handle()
async def _(event: RequestEvent, bot: Bot):
    if isinstance(event, FriendRequestEvent):
        if await BL_Manager.is_private_black(str(event.user_id)):
            await send_to_admin(f"尝试拒绝添加黑名单用户{event.user_id}.......")
            await event.reject(bot)
        else:
            await event.approve(bot=bot)
            await send_to_admin(f"收到{event.user_id}的好友请求：{event.comment or ''}")
    elif isinstance(event, GroupRequestEvent):
        if await BL_Manager.is_private_black(str(event.user_id)):
            await send_to_admin(
                f"尝试拒绝添加黑名单用户{event.user_id}的拉群请求......."
            )
            await event.reject(bot)
            return
        elif await BL_Manager.is_group_black(str(event.group_id)):
            await send_to_admin(
                f"尝试拒绝添加黑名单群组{event.group_id}的拉群请求......."
            )
            await event.reject(bot)
            return
        group_list = await bot.get_group_list()
        group_joins = [int(group["group_id"]) for group in group_list]
        if event.sub_type != "invite":
            return
        if event.group_id not in group_joins:
            await send_to_admin(
                f"收到{event.user_id}加入群组邀请，已自动加入群组{event.group_id}"
            )
            await event.approve(bot=bot)
