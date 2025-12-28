from nonebot.plugin import PluginMetadata, require

require("nonebot_plugin_localstore")
require("nonebot_plugin_orm")
require("amrita.plugins.menu")
from . import command_manager, config, on_init, cleanup
from .commands import lp_chat_group, lp_perm_group, lp_user, main
from .config import DataManager

__all__ = [
    "DataManager",
    "command_manager",
    "config",
    "cleanup",
    "lp_chat_group",
    "lp_perm_group",
    "lp_user",
    "main",
    "on_init",
]

# 注册权限缓存清理功能
cleanup.register_permission_cleanup()

__plugin_meta__ = PluginMetadata(
    name="LitePerm 权限管理插件",
    description="基于权限节点/权限组/特殊权限的权限管理插件。",
    usage="https://amrita.suggar.top/amrita/plugins/liteperm/",
    homepage="https://amrita.suggar.top/amrita/plugins/liteperm/",
    type="library",
    supported_adapters={"~onebot.v11"},
)