from __future__ import annotations

from datetime import timedelta

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from amrita.plugins.manager.models import get_usage
from amrita.utils.system_health import calculate_system_health

from ..authlib import AuthManager
from ..main import app, templates, try_get_bot
from ..sidebar import SideBarManager


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 检查是否有有效的令牌
    try:
        await AuthManager().check_current_user(request)
        # 如果有有效的令牌，重定向到仪表板
        response = RedirectResponse(url="/dashboard", status_code=303)
        return response
    except HTTPException:
        # 如果没有有效令牌，显示登录页面
        return templates.TemplateResponse("index.html", {"request": request})


@app.post("/login", response_class=RedirectResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    # 验证用户名和密码
    if not AuthManager().authenticate_user(username, password):
        # 认证失败，返回登录页面并显示错误
        response = RedirectResponse(url="/?error=invalid_credentials", status_code=303)
        return response
    access_token_expires = timedelta(minutes=30)
    access_token = await AuthManager().create_token(username, access_token_expires)
    url = "/dashboard"
    if password == "admin123":
        url += "?warn=weak_password"
    response = RedirectResponse(url=url, status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    import nonebot

    bot = try_get_bot()
    if bot is not None:
        usage = await get_usage(bot.self_id)
        usage.sort(key=lambda u: u.id)
        message_stats = {
            "labels": [u.created_at for u in usage],
            "data": [u.msg_received + u.msg_sent for u in usage],
        }

        msg_io_status = {
            "labels": ["收", "发"],
            "data": [usage[-1].msg_received, usage[-1].msg_sent],
        }
    else:
        usage = []
        message_stats = {
            "labels": ["Bot未连接"],
            "data": [0],
        }

        msg_io_status = {
            "labels": ["Bot未连接"],
            "data": [0],
        }
    side_bar = SideBarManager().get_sidebar_dump()
    for bar in side_bar:
        if bar.get("name") == "控制台":
            bar["active"] = True
            break
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "loaded_plugins": len(nonebot.get_loaded_plugins()),
            "recent_activity": [],
            "message_stats": message_stats,
            "msg_io_status": msg_io_status,
            "total_message": (
                (usage[-1].msg_received + usage[-1].msg_sent) if bot else -1
            ),
            "bot_connected": bot is not None,
            "health": f"{calculate_system_health()['overall_health']}%",
        },
    )


@app.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    if token := request.cookies.get("access_token"):
        await AuthManager().user_log_out(token)
    response.delete_cookie("access_token")
    return response
