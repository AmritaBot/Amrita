import nonebot
from pydantic import BaseModel


class Config(BaseModel):
    amrita_admin_group: int = 0


def get_amrita_config() -> Config:
    return nonebot.get_plugin_config(Config)
