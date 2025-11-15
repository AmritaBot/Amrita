from nonebot import on_request
from nonebot.adapters.onebot.v11 import (
    Bot,
    FriendRequestEvent,
    GroupRequestEvent,
    RequestEvent,
)

from amrita.config import get_amrita_config
from amrita.utils.admin import send_to_admin

from .blacklist.black import BL_Manager


@on_request(priority=1, block=True).handle()
async def _(event: RequestEvent, bot: Bot):
    config = get_amrita_config()
    if isinstance(event, FriendRequestEvent):
        if await BL_Manager.is_private_black(str(event.user_id)):
            await send_to_admin(f"尝试拒绝添加黑名单用户{event.user_id}.......")
            await event.reject(bot)
        elif config.auto_approve_friend_request:
            await event.approve(bot=bot)
            await send_to_admin(
                f"收到{event.user_id}的好友请求：{event.comment or ''}，已确认。"
            )
        else:
            await send_to_admin(
                f"收到{event.user_id}的好友请求：{event.comment or ''}，请手动处理。"
            )
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
        if config.auto_approve_group_request:
            group_list = await bot.get_group_list()
            group_joins = {int(group["group_id"]) for group in group_list}
            if event.sub_type != "invite":
                return
            if event.group_id not in group_joins:
                await send_to_admin(
                    f"收到{event.user_id}加入群组邀请，已自动加入群组{event.group_id}",
                    bot,
                )
                await event.approve(bot=bot)
        else:
            group_list = await bot.get_group_list()
            group_joins = {int(group["group_id"]) for group in group_list}
            if event.sub_type != "invite":
                return
            if event.group_id not in group_joins:
                await send_to_admin(
                    f"{event.user_id} 邀请我加入群 {event.group_id}，请手动处理。", bot
                )
