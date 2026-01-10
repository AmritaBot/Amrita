from nonebot import logger

from ..chatmanager import chat_manager


def debug_log(msg: str):
    if chat_manager.debug:
        logger.debug(msg)
