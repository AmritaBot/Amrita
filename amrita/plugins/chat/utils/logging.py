from typing import Protocol

from nonebot import logger

from ..chatmanager import chat_manager


class CastToStringAble(Protocol):
    def __str__(self) -> str: ...


def debug_log(msg: CastToStringAble):
    if chat_manager.debug:
        logger.debug(msg)
