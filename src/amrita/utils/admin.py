from nonebot import get_plugin_config
from nonebot.adapters.onebot.v11 import Bot, MessageSegment

from .config import Config


async def send_forward_msg_to_admin(
    bot: Bot, name: str, uin: str, msgs: list[MessageSegment]
):
    """发送消息到管理

    Args:
        bot (Bot): Bot
        name (str): 名称
        uin (str): UID
        msgs (list[MessageSegment]): 消息列表

    Returns:
        dict: 发送消息后的结果
    """

    def to_json(msg: MessageSegment) -> dict:
        return {"type": "node", "data": {"name": name, "uin": uin, "content": msg}}

    messages = [to_json(msg) for msg in msgs]
    await bot.send_group_forward_msg(group_id=get_plugin_config(Config).amrita_admin_group, messages=messages)
