from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
import typing

import nonebot
from fastapi import Request
from fastapi.responses import HTMLResponse
from nonebot.adapters.onebot.v11 import Bot

from amrita.config import get_amrita_config
from amrita.utils.system_health import calculate_system_usage
from amrita.utils.utils import get_amrita_version

from ..main import app, templates, try_get_bot
from ..sidebar import SideBarManager


@app.get("/bot/status", response_class=HTMLResponse)
async def _(request: Request):
    bot = try_get_bot()
    sys_info = calculate_system_usage()
    side_bar = SideBarManager().get_sidebar_dump()
    for bar in side_bar:
        if bar.get("name") == "机器人管理":
            bar["active"] = True
            break
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "sidebar_items": side_bar,  # 侧边栏菜单项
            "bot_static_info": {  # 机器人静态信息
                "id": bot.self_id if bot else "unknown",
                "name": get_amrita_config().bot_name,
                "version": get_amrita_version(),
                "platform": "OneBot V11",
                "bot_name": (
                    next(iter(typing.cast(Bot, bot).config.nickname))
                    if typing.cast(Bot, bot).config.nickname
                    else "<获取失败>"
                ),
            },
            "bot_dynamic_info": {  # 机器人动态信息(初始值，将通过API实时更新)
                "status": "online" if bot else "offline",  # 状态: online/offline
                **sys_info,
            },
            "system_info": {  # 系统信息
                "os": sys_info["system_version"],
                "python_version": sys.version,
                "hostname": os.uname().nodename,
            },
        },
    )


@app.get("/bot/plugins", response_class=HTMLResponse)
async def _(request: Request):
    side_bar = SideBarManager().get_sidebar_dump()
    for bar in side_bar:
        if bar.get("name") == "机器人管理":
            bar["active"] = True
            break
    plugins = nonebot.get_loaded_plugins()
    plugin_list = [
        {
            "name": (plugin.metadata.name if plugin.metadata else plugin.name),
            "homepage": (plugin.metadata.homepage if plugin.metadata else None),
            "is_local": "." in plugin.module_name,
            "type": (
                (plugin.metadata.type or "Unknown") if plugin.metadata else "Unknown"
            ),
            "description": (
                plugin.metadata.description or "(还没有介绍呢)"
                if plugin.metadata
                else "（还没有介绍呢）"
            ),
            "version": (
                importlib.metadata.version(plugin.module_name)
                if "." not in plugin.module_name
                else "(不适用)"
            ),
        }
        for plugin in plugins
    ]
    return templates.TemplateResponse(
        "plugins.html",
        context={
            "plugins": plugin_list,
            "plugin_types": ["application", "library"],
            "request": request,
            "sidebar_items": side_bar,
        },
    )
