from nonebot.plugin import PluginMetadata, require

require("amrita.plugins.perm")
require("amrita.plugins.menu")

from . import (
    add,
    amrita,
    apicall_insight,
    auto_clean,
    ban,
    black,
    checker,
    leave,
    list_black,
    pardon,
    send,
    status,
)
from .status_manager import StatusManager

__plugin_meta__ = PluginMetadata(
    name="机器人管理插件",
    description="管理器（TO超级管理员：您的每一个操作都会让用户发出尖锐的爆鸣声）",
    usage="管理器插件",
    type="application",
)

__all__ = [
    "StatusManager",
    "add",
    "amrita",
    "apicall_insight",
    "auto_clean",
    "ban",
    "black",
    "checker",
    "leave",
    "list_black",
    "pardon",
    "send",
    "status",
]
