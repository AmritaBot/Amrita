from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from amrita.plugins.chat.utils.app import CachedUserDataRepository
from amrita.plugins.perm.API.rules import any_has_permission

from ..check_rule import is_bot_admin
from ..config import config_manager
from ..utils.sql import InsightsModel, UserDataExecutor, get_any_id


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
        is_bypass = await is_bot_admin(event) or await (
            any_has_permission("amrita.usage.bypass")
        )(event)

        msg = (
            f"您今日的使用次数为：{data.called_count}/{user_limit if (user_limit != -1 and enable_limit and not is_bypass) else '♾'}次"
            + f"\n您今日的token使用量为：{data.tokens_input + data.tokens_output}/{user_token_limit if (user_token_limit != -1 and enable_limit and not is_bypass) else '♾'}tokens"
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
    elif arg.startswith("top10"):
        if not await is_bot_admin(event):
            await matcher.finish("你没有权限查看排名数据")
        parts = arg.split()
        if len(parts) == 1:
            top_type = "all"
        elif len(parts) == 2:
            if parts[1] == "--group":
                top_type = "group"
            elif parts[1] == "--private":
                top_type = "private"
            elif parts[1] == "--all":
                top_type = "all"
            else:
                await matcher.finish(
                    "无效的参数。支持的参数：--group, --private, --all"
                )
        else:
            await matcher.finish(
                "参数格式错误。使用方法：top10 [--group|--private|--all]"
            )

        # 获取top10数据
        top_users = await UserDataExecutor.get_top10_users(top_type=top_type, limit=10)

        if not top_users:
            msg = "暂无使用数据。"
        else:
            # 构建排名消息
            type_names = {"group": "群组", "private": "私聊", "all": "全部"}
            msg = f"今日{type_names[top_type]}使用量Top10：\n"

            for i, user in enumerate(top_users, 1):
                # 提取用户ID（去掉前缀）
                user_id = (
                    user.user_id.split("_", 1)[1]
                    if "_" in user.user_id
                    else user.user_id
                )
                user_type = "群" if user.user_id.startswith("group_") else "用户"

                total_tokens = user.tokens_input + user.tokens_output
                msg += f"{i}. {user_type}{user_id}: {user.called_count}次, {total_tokens}tokens\n"

    await matcher.finish(
        MessageSegment.at(event.user_id) + MessageSegment.text(f"\n{msg}")
    )
