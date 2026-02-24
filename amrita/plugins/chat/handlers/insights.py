from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from amrita.plugins.chat.utils.app import CachedUserDataRepository

from ..check_rule import is_bot_admin
from ..config import config_manager
from ..utils.sql import InsightsModel, get_any_id


async def insights(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    msg = "未知参数。"
    config = config_manager.config
    if not (arg := args.extract_plain_text().strip()):
        data = await CachedUserDataRepository().get_metadata(event.user_id, False)
        user_limit = config.usage_limit.user_daily_limit
        user_token_limit = config.usage_limit.user_daily_token_limit
        group_limit = config.usage_limit.group_daily_limit
        group_token_limit = config.usage_limit.group_daily_token_limit
        enable_limit = config.usage_limit.enable_usage_limit
        is_admin = await is_bot_admin(event)

        msg = (
            f"您今日的使用次数为：{data.called_count}/{user_limit if (user_limit != -1 and enable_limit and not is_admin) else '♾'}次"
            + f"\n您今日的token使用量为：{data.tokens_input + data.tokens_output}/{user_token_limit if (user_token_limit != -1 and enable_limit and not is_admin) else '♾'}tokens"
            + f"(输入：{data.tokens_input},输出：{data.tokens_output})"
        )
        if isinstance(event, GroupMessageEvent):
            data = await CachedUserDataRepository().get_metadata(*get_any_id(event))
            msg = (
                f"群组使用次数为：{data.called_count}/{group_limit if (group_limit != -1 and enable_limit) else '♾'}次"
                + f"\n群组使用token为：{data.tokens_input + data.tokens_output}/{group_token_limit if (group_token_limit != -1 and enable_limit) else '♾'}tokens"
                + f"（输入：{data.tokens_input},输出：{data.tokens_output}）"
                + f"\n\n{msg}"
            )
    elif arg == "global":
        total_token_limit = config.usage_limit.total_daily_token_limit
        total_limit = config.usage_limit.total_daily_limit
        if not await is_bot_admin(event):
            await matcher.finish("你没有权限查看全局数据")
        data = await InsightsModel.get()
        msg = (
            f"\n今日全局数据：\n输入token使用量：{data.token_input}/{total_token_limit}(您的限制：♾)token"
            + f"\n输出token使用量：{data.token_output}token"
            + f"\n总使用次数：{data.usage_count}/{total_limit}(您的限制：♾)次"
            + f"\n总使用token为：{data.token_input + data.token_output}tokens"
        )

    await matcher.finish(
        MessageSegment.at(event.user_id) + MessageSegment.text(f"\n{msg}")
    )
