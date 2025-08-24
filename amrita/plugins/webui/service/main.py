from __future__ import annotations

import hashlib
import os
import secrets
from asyncio import Lock
from datetime import datetime, timedelta
from pathlib import Path

import nonebot
from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nonebot import get_bot
from pydantic import BaseModel

from amrita.config import get_amrita_config
from amrita.plugins.manager.models import get_usage
from amrita.plugins.webui.service.config import get_webui_config
from amrita.utils.system_health import calculate_system_health, calculate_system_usage
from amrita.utils.utils import get_amrita_version

from .sidebar import SideBarManager


class TokenData(BaseModel):
    username: str
    expire: datetime


app: FastAPI = nonebot.get_app()
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")
tokens: dict[str, TokenData] = {}
token_locks: dict[str, Lock] = {}
tokens_lock = Lock()
USERS = {
    get_webui_config().webui_user_name: hashlib.sha256(
        get_webui_config().webui_password.encode("utf-8")
    ).hexdigest()
}


def try_get_bot():
    try:
        bot = nonebot.get_bot()
    except Exception:
        bot = None
    return bot


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password


def authenticate_user(username: str, password: str) -> bool:
    if username in USERS:
        return verify_password(password, USERS[username])
    return False


async def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = secrets.token_urlsafe(32)

    # 使用锁保护tokens字典的并发访问
    async with tokens_lock:
        tokens[encoded_jwt] = TokenData(username=to_encode["sub"], expire=expire)
    return encoded_jwt


async def get_current_user(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token or token not in tokens:
        raise HTTPException(status_code=401, detail="未认证")

    token_data = tokens[token]
    if token_data.expire < datetime.utcnow():
        async with tokens_lock:
            # 双重检查，确保在获得锁之后token仍然存在且未过期
            if token in tokens and tokens[token].expire < datetime.utcnow():
                del tokens[token]
        raise HTTPException(status_code=401, detail="认证已过期")

    return token_data.username


async def refresh_token(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token or token not in tokens:
        raise HTTPException(status_code=401, detail="未认证")

    # 为每个token创建一个锁，避免同一token的并发刷新问题
    async with tokens_lock:
        if token not in token_locks:
            token_locks[token] = Lock()
        token_lock = token_locks[token]

    # 使用特定token的锁保护刷新过程
    async with token_lock:
        # 双重检查，确保token仍然有效
        if token not in tokens:
            raise HTTPException(status_code=401, detail="未认证")

        data_cache = tokens[token]
        del tokens[token]

        # 清理锁以避免内存泄漏
        async with tokens_lock:
            token_locks.pop(token, None)

        access_token_expires = timedelta(minutes=30)
        access_token = await create_access_token(
            data={"sub": data_cache.username}, expires_delta=access_token_expires
        )
        return access_token


@app.exception_handler(400)
@app.exception_handler(402)
@app.exception_handler(403)
@app.exception_handler(404)
@app.exception_handler(405)
@app.exception_handler(500)
async def _(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_code": exc.status_code,
            "debug": app.debug,
            "error_details": str(exc) if app.debug else None,
        },
    )


@app.exception_handler(HTTPException)
async def _(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_code": exc.status_code,
            "debug": app.debug,
            "error_details": str(exc) if app.debug else None,
        },
    )


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 定义不需要认证的路径
    public_paths = ["/", "/public", "/static", "/login", "/docs", "/onebot/v11"]
    if request.url.path in public_paths:
        response = await call_next(request)
    else:
        try:
            await get_current_user(request)
            response: Response = await call_next(request)
            access_token = await refresh_token(request)
            response.set_cookie(key="access_token", value=access_token, httponly=True)
        except HTTPException as e:
            # 令牌无效或过期，重定向到登录页面
            response = RedirectResponse(url="/", status_code=303)
            if e.status_code in (401, 403):
                response.delete_cookie("access_token")
                return response
            raise e
    return response


# 路由
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # 检查是否有有效的令牌
    try:
        await get_current_user(request)
        # 如果有有效的令牌，重定向到仪表板
        response = RedirectResponse(url="/dashboard", status_code=303)
        return response
    except HTTPException:
        # 如果没有有效令牌，显示登录页面
        return templates.TemplateResponse("index.html", {"request": request})


@app.post("/login", response_class=RedirectResponse)
async def login(username: str = Form(...), password: str = Form(...)):
    # 验证用户名和密码
    if not authenticate_user(username, password):
        # 认证失败，返回登录页面并显示错误
        response = RedirectResponse(url="/?error=invalid_credentials", status_code=303)
        return response

    # 认证成功，创建访问令牌
    access_token_expires = timedelta(minutes=30)
    access_token = await create_access_token(
        data={"sub": username}, expires_delta=access_token_expires
    )

    # 设置cookie并重定向到仪表板
    url = "/dashboard"
    if password == "admin123":
        url += "?warn=weak_password"
    response = RedirectResponse(url=url, status_code=303)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response


@app.get("/api/bot/status")
async def _(request: Request):
    return {
        "status": "online" if try_get_bot() else "offline",
        **calculate_system_usage(),
    }


@app.get("/bots/status")
async def _(request: Request):
    bot = try_get_bot()
    sys_info = calculate_system_usage()
    side_bar = SideBarManager().get_sidebar_dump()
    for bar in side_bar:
        if bar.get("name") == "机器人管理":
            bar["active"] = True
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "sidebar_items": side_bar,  # 侧边栏菜单项
            "bot_static_info": {  # 机器人静态信息
                "id": bot.self_id if bot else "unknown",
                "name": get_amrita_config().bot_name,
                "version": get_amrita_version(),
                "platform": "QQ OneBot V11",  # 运行平台
                "author": "Amrita[NoneBot2]",
            },
            "bot_dynamic_info": {  # 机器人动态信息(初始值，将通过API实时更新)
                "status": "online" if bot else "offline",  # 状态: online/offline
                **sys_info,
            },
            "system_info": {  # 系统信息
                "os": sys_info["system_version"],
                "python_version": "python_version",
                "hostname": os.uname().nodename,
            },
        },
    )


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


@app.post("/logout")
async def logout(response: Response):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response
