import nonebot
from nonebot.plugin import PluginMetadata, require

require("amrita.plugins.manager")

from .service import config, models
from .service.config import get_webui_config

__plugin_metadata__ = PluginMetadata(
    name="Amrita WebUI",
    description="WebUI for Amrita",
    usage="",
    config=config.Config,
)

__all__ = ["config", "models"]

webui_config = get_webui_config()
if webui_config.webui_enable:
    nonebot.logger.info("Mounting webui......")
    from .service import main

    __all__ += ["main"]
