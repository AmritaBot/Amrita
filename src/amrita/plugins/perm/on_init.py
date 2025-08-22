from nonebot import get_driver

from .config import data_manager

banner_template = """\033[34m▗▖   ▗▄▄▖
▐▌   ▐▌ ▐▌  \033[96mLitePerm\033[34m  \033[1;4;34mV{version}-Amrita\033[0m\033[34m
▐▌   ▐▛▀▘   is initializing...
▐▙▄▄▖▐▌\033[0m"""


@get_driver().on_startup
async def load_config():
    version = "0.0.2-LTS"

    print(banner_template.format(version=version))
    data_manager.init()
