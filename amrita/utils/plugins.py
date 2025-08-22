from pathlib import Path

import nonebot
import toml

from amrita.config import get_amrita_config


def load_plugins():
    nonebot.load_from_toml("pyproject.toml")
    nonebot.logger.info("Loading built-in plugins...")
    config = get_amrita_config()
    for name in (Path(__file__).parent.parent / "plugins").iterdir():
        if name in config.disabled_builtin_plugins:
            continue
        nonebot.logger.info(f"Require plugin {name.name}...")
        nonebot.require(f"amrita.plugins.{name.name}")
    nonebot.logger.info("Loading plugins......")
    from amrita.cmds.main import PyprojectFile

    meta = PyprojectFile.model_validate(toml.load("pyproject.toml"))
    for plugin in meta.tool.nonebot.plugins:
        nonebot.logger.info(f"Require plugin {plugin}...")
        try:
            nonebot.require(plugin)
        except Exception as e:
            nonebot.logger.error(f"Failed to load plugin {plugin}: {e}")
    nonebot.logger.info("Require local plugins......")
    nonebot.load_plugins("plugins")
