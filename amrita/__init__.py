"""Amrita框架初始化模块

该模块是Amrita框架的入口点，负责导入和初始化核心组件。
"""

import nonebot
from nonebot import run

from . import cli
from .cmds import main as cmd_main
from .cmds import plugin
from .config import get_amrita_config
from .utils.bot_utils import init
from .utils.plugins import load_plugins

__all__ = [
    "cli",
    "cmd_main",
    "get_amrita_config",
    "init",
    "load_plugins",
    "nonebot",
    "plugin",
    "run",
]
