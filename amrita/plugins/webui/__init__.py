import nonebot
from nonebot.plugin import PluginMetadata, require

require("amrita.plugins.manager")

from .service import config, models
from .service.config import get_webui_config

__plugin_meta__ = PluginMetadata(
    name="Amrita WebUI",
    description="PROJ.Amrita的原生WebUI",
    usage="打开bot 的webui页面",
    config=config.Config,
)

__all__ = ["config", "models"]

webui_config = get_webui_config()
if webui_config.webui_enable:
    nonebot.logger.info("Mounting webui......")
    from .service import main
    from .service.route import api, bot, index, user

    __all__ += [
        "api",
        "bot",
        "index",
        "main",
        "user",
    ]
