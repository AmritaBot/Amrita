"""权限缓存清理事件后处理器"""
import asyncio
from typing import TYPE_CHECKING

from nonebot import on_message, on_notice, on_request
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Event

from .API.rules import expire_event_cache

if TYPE_CHECKING:
    from nonebot.adapters.onebot.v11 import Bot

# 创建通用事件后处理钩子（覆盖所有事件类型）
_message_cleanup_hook = on_message(priority=999, block=False)
_notice_cleanup_hook = on_notice(priority=999, block=False)
_request_cleanup_hook = on_request(priority=999, block=False)


async def cleanup_permission_cache(event: Event):
    """通用缓存清理函数"""
    try:
        # 获取事件ID
        event_id = str(id(event))
        
        # 清理相关权限缓存
        await expire_event_cache(event_id)
        
        logger.debug(f"权限缓存清理完成，事件ID: {event_id}")
        
    except Exception as e:
        logger.warning(f"权限缓存清理失败: {e}")
        # 不阻断事件处理，只记录日志


@_message_cleanup_hook.handle()
async def cleanup_message_permission_cache(event: Event, bot: "Bot" = None):
    """消息事件后处理钩子：清理权限缓存"""
    await cleanup_permission_cache(event)


@_notice_cleanup_hook.handle()
async def cleanup_notice_permission_cache(event: Event, bot: "Bot" = None):
    """通知事件后处理钩子：清理权限缓存"""
    await cleanup_permission_cache(event)


@_request_cleanup_hook.handle()
async def cleanup_request_permission_cache(event: Event, bot: "Bot" = None):
    """请求事件后处理钩子：清理权限缓存"""
    await cleanup_permission_cache(event)


# 简化的注册函数（只保留日志记录）
def register_permission_cleanup():
    """注册权限缓存清理功能"""
    logger.info("权限缓存清理功能已注册 - 支持消息、通知、请求事件")