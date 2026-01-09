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
    name="Amrita Bot本体管理模块",
    description="Amrita内置的Bot管理功能",
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
