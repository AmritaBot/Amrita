"""权限缓存清理事件后处理器"""
import asyncio
from typing import TYPE_CHECKING

from nonebot import on_message
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Event

from .API.rules import expire_event_cache

if TYPE_CHECKING:
    from nonebot.adapters.onebot.v11 import Bot

# 创建后处理钩子
_permission_cleanup_hook = on_message(priority=999, block=False)


@_permission_cleanup_hook.handle()
async def cleanup_permission_cache(event: Event, bot: "Bot" = None):
    """事件后处理钩子：清理权限缓存"""
    try:
        # 获取事件ID
        event_id = str(id(event))
        
        # 清理相关权限缓存
        await expire_event_cache(event_id)
        
        logger.debug(f"权限缓存清理完成，事件ID: {event_id}")
        
    except Exception as e:
        logger.warning(f"权限缓存清理失败: {e}")
        # 不阻断事件处理，只记录日志


def register_permission_cleanup():
    """注册权限缓存清理功能"""
    logger.info("权限缓存清理功能已注册")