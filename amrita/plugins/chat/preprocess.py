from nonebot import get_driver, logger

from amrita.plugins.chat.utils.llm_tools.mcp_client import ClientManager

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
    if (conf := config.config_manager.config).llm_config.tools.agent_mcp_client_enable:
        logger.info("正在初始化MCP Client......")
        mcp_servers = conf.llm_config.tools.agent_mcp_server_scripts
        for server in mcp_servers:
            try:
                await ClientManager().initialize_this(server)
            except Exception as e:  # noqa: PERF203
                logger.error(f"初始化MCP Client@{server}失败: {e}")
                logger.opt(exception=e, colors=True).exception(e)
        logger.info("MCP Client初始化完成！")
    logger.debug("成功启动！")
