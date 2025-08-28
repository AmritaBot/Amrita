from nonebot import get_driver, logger

from . import config
from .config import config_manager
from .hook_manager import run_hooks

driver = get_driver()
__LOGO = "\033[34mLoading SuggarChat \033[33m {version}-Amrita......\033[0m"


@driver.on_bot_connect
async def hook():
    logger.debug("运行钩子...")
    await run_hooks()


@driver.on_startup
async def onEnable():
    kernel_version = "V3"
    config.__kernel_version__ = kernel_version
    logger.info(__LOGO.format(version=kernel_version))
    logger.debug("加载配置文件...")
    await config_manager.load()
    config_manager.init_watch()
    logger.debug("成功启动！")
