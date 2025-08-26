from nonebot import get_plugin_config
from pydantic import BaseModel


class Config(BaseModel):
    """
    Configuration for webui
    """

    webui_enable: bool = True
    webui_user_name: str = "admin"
    webui_password: str = "admin123"


def get_webui_config() -> Config:
    return get_plugin_config(Config)
