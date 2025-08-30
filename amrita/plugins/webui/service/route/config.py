from __future__ import annotations

import os
from pathlib import Path

import aiofiles
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..main import app, templates
from ..sidebar import SideBarManager

# 获取项目根目录
ENV_FILE = Path(os.getcwd()) / ".env"


@app.get("/bot/config", response_class=HTMLResponse)
async def config_editor(request: Request):
    """
    配置文件编辑器页面
    """
    # 读取.env文件内容
    env_content = ""
    if ENV_FILE.exists():
        async with aiofiles.open(ENV_FILE, encoding="utf-8") as f:
            env_content = await f.read()

    # 获取侧边栏
    side_bar = SideBarManager().get_sidebar_dump()
    for bar in side_bar:
        if bar.get("name") == "机器人管理":
            bar["active"] = True
            break

    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "env_content": env_content,
        },
    )


class ConfigUpdateRequest:
    def __init__(self, content: str):
        self.content = content


@app.post("/api/bot/config")
async def update_config(request: Request):
    """
    更新配置文件API
    """

    # 获取请求数据
    data = await request.json()
    content = data.get("content", "")
    if not content:
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid request data"},
        )

    try:
        # 写入.env文件
        async with aiofiles.open(ENV_FILE, "w", encoding="utf-8") as f:
            await f.write(content)
        return JSONResponse(
            {"code": 200, "message": "配置文件更新成功", "error": None}, 200
        )
    except Exception as e:
        return JSONResponse(
            {"code": 500, "message": "配置文件更新失败", "error": str(e)}, 500
        )
