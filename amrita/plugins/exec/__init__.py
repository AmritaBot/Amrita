from nonebot.plugin import PluginMetadata, require

require("amrita.plugins.perm")

from . import main

__plugin_meta__ = PluginMetadata(
    name="命令执行插件",
    description="执行命令",
    usage="/exec <command>",
    type="application",
)

__all__ = ["main"]

