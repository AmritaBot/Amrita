from __future__ import annotations

from datetime import datetime
from importlib import metadata
from typing import Literal

import nonebot
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from nonebot import get_bot
from pydantic import BaseModel

from amrita.plugins.manager.blacklist.black import BL_Manager
from amrita.plugins.manager.models import get_usage
from amrita.utils.system_health import calculate_system_usage

from ..main import app, try_get_bot
from ..sidebar import SideBarManager


class RequestDataSchema(BaseModel):
    id: str
    type: Literal["group", "user"]
    reason: str


class BlacklistRemoveSchema(BaseModel):
    ids: list[str]


@app.post("/api/blacklist/add")
async def _(data: RequestDataSchema):
    try:
        func = (
            BL_Manager.private_append
            if data.type == "user"
            else BL_Manager.group_append
        )
        await func(data.id, data.reason)
    except Exception as e:
        return JSONResponse({"code": 500, "error": str(e)}, status_code=500)
    return JSONResponse({"code": 200, "error": None}, 200)


@app.get("/api/chart/messages")
async def get_messages_chart_data():
    try:
        bot = get_bot()
        usage = await get_usage(bot.self_id)
        lables = [usage[i].created_at for i in range(len(usage))]
        data = [usage[i].msg_received for i in range(len(usage))]
        return {"labels": lables, "data": data}
    except ValueError:
        raise HTTPException(status_code=500, detail="Bot未连接")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chart/today-usage")
async def get_msg_io_status_chart_data():
    try:
        bot = get_bot()
        usage_data = await get_usage(bot.self_id)
        for i in usage_data:
            if i.created_at == datetime.now().strftime("%Y-%m-%d"):
                data = [i.msg_received, i.msg_sent]
                break
        else:
            raise HTTPException(status_code=404, detail="数据不存在")
        return {"labels": ["收", "发"], "data": data}
    except ValueError:
        raise HTTPException(status_code=500, detail="Bot未连接")
    except HTTPException as e:
        raise e


@app.post("/api/blacklist/remove-batch/{type}")
async def _(data: BlacklistRemoveSchema, type: str):
    for id in data.ids:
        if type == "user":
            await BL_Manager.private_remove(id)
        elif type == "group":
            await BL_Manager.group_remove(id)
    return JSONResponse({"code": 200, "error": None}, 200)


@app.post("/api/blacklist/remove/{type}/{id}")
async def _(request: Request, type: str, id: str):
    func = BL_Manager.private_remove if type == "user" else BL_Manager.group_remove
    await func(id)
    return JSONResponse({"code": 200, "error": None}, 200)


@app.get("/api/plugins/list")
async def _(request: Request):
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
                metadata.version(plugin.module_name)
                if "." not in plugin.module_name
                else "(不适用)"
            ),
        }
        for plugin in plugins
    ]
    return plugin_list


@app.get("/api/bot/status", response_class=JSONResponse)
async def _(request: Request):
    side_bar = SideBarManager().get_sidebar_dump()
    for bar in side_bar:
        if bar.get("name") == "机器人管理":
            bar["active"] = True
            break
    return JSONResponse(
        {
            "status": "online" if try_get_bot() else "offline",
            **calculate_system_usage(),
            "sidebar_items": side_bar,
        }
    )
