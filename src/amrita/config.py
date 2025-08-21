from typing import Literal

from nonebot import get_plugin_config
from pydantic import BaseModel


class AmritaConfig(BaseModel):
    log_dir: str = "logs"
    admin_group: int = 0
    disabled_builtin_plugins: list[Literal["chat"]] = []
    amrita_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        "WARNING"
    )


def get_amrita_config() -> AmritaConfig:
    return get_plugin_config(AmritaConfig)
