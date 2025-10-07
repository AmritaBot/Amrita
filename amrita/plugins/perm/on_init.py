from nonebot import get_driver

from .config import data_manager

banner_template = """\033[34m▗▖   ▗▄▄▖
▐▌   ▐▌ ▐▌  \033[96mLitePerm\033[34m  \033[1;4;34mV2-Amrita\033[0m\033[34m
▐▌   ▐▛▀▘   is initializing...
▐▙▄▄▖▐▌\033[0m"""


@get_driver().on_startup
async def load_config():
    print(banner_template)
    data_manager.init()
