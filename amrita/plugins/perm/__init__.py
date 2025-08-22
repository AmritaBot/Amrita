from nonebot.plugin import PluginMetadata, require

require("nonebot_plugin_localstore")
require("amrita.plugins.menu")
from . import command_manager, config, on_init

# ,hooks
from .commands import lp_chat_group, lp_perm_group, lp_user, main

# ,lp_command

__all__ = [
    "command_manager",
    "config",
    #    "hooks",
    "lp_chat_group",
    # "lp_command",
    "lp_perm_group",
    "lp_user",
    "main",
    "on_init",
]

__plugin_meta__ = PluginMetadata(
    name="LitePerm 权限管理插件",
    description="基于权限节点/权限组/特殊权限的权限管理插件。",
    usage="https://github.com/LiteSuggarDEV/plugin-liteperm/blob/main/README.md",
    homepage="https://github.com/LiteSuggarDEV/plugin-liteperm/",
    type="library",
    supported_adapters={"~onebot.v11"},
)
