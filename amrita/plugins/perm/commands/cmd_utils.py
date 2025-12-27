from nonebot.adapters.onebot.v11 import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg


async def parse_command(
    matcher: Matcher, args: Message = CommandArg()
) -> tuple[str, str, str, str, str]:
    """统一参数解析器
    user_id, action_type, operation, target, value
    """
    args_list = args.extract_plain_text().strip().split(maxsplit=5)

    # 参数校验
    if len(args_list) < 1:
        await matcher.finish("❌ 缺少ID")
    if len(args_list) < 2:
        await matcher.finish("❌ 缺少操作类型")
    if len(args_list) < 3:
        await matcher.finish("❌ 缺少操作目标")

    id = args_list[0]
    action_type = args_list[1]
    operation = args_list[2]
    target = args_list[3] if len(args_list) >= 4 else ""
    value = args_list[4] if len(args_list) == 5 else ""

    return id, action_type, operation, target, value
