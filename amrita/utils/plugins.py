import sys
from pathlib import Path

import nonebot
import toml

from amrita.config import get_amrita_config


def apply_alias():
    from ..plugins import chat

    sys.modules["nonebot_plugin_suggarchat"] = chat


def load_plugins():
    config = get_amrita_config()
    nonebot.load_from_toml("pyproject.toml")
    for name in (Path(__file__).parent.parent / "plugins").iterdir():
        if name in config.disabled_builtin_plugins:
            continue
        nonebot.logger.debug(f"Require plugin {name.name}...")
        nonebot.require(f"amrita.plugins.{name.name}")
    nonebot.logger.debug("Appling Patches")
    apply_alias()
    nonebot.logger.info("Loading built-in plugins...")
    nonebot.logger.info("Loading plugins......")
    from amrita.cmds.main import PyprojectFile

    meta = PyprojectFile.model_validate(toml.load("pyproject.toml"))
    for plugin in meta.tool.nonebot.plugins:
        nonebot.logger.debug(f"Require plugin {plugin}...")
        try:
            nonebot.require(plugin)
        except Exception as e:
            nonebot.logger.error(f"Failed to load plugin {plugin}: {e}")
    nonebot.logger.info("Require local plugins......")
    nonebot.load_plugins("plugins")
