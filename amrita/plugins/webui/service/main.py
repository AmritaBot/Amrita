from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import nonebot
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nonebot import logger

from .authlib import AuthManager, TokenManager

app: FastAPI = nonebot.get_app()
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


def try_get_bot():
    try:
        bot = nonebot.get_bot()
    except Exception:
        bot = None
    return bot


@app.exception_handler(404)
async def _(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_code": 404,
            "debug": app.debug,
            "error_details": "Not Found",
        },
    )


@app.exception_handler(400)
@app.exception_handler(402)
@app.exception_handler(403)
@app.exception_handler(405)
@app.exception_handler(500)
async def _(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        response = templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": exc.status_code,
                "debug": app.debug,
                "error_details": str(exc) if app.debug else None,
            },
            status_code=exc.status_code,
        )
    else:
        response = templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_code": 500,
                "debug": True,
                "error_details": f"Unexpected Exception!{exc!s}",
            },
        )
    return response


@app.exception_handler(HTTPException)
async def _(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        logger.warning("401!" + str(request))
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
    public_paths = [
        "/",
        "/public",
        "/login",
        "/docs",
        "/onebot/v11",
        "/password-help",
        "/robots.txt",
        "/sitemap.xml",
    ]
    if request.url.path in public_paths or request.url.path.startswith("/static"):
        response = await call_next(request)
    else:
        try:
            await AuthManager().check_current_user(request)
            access_token = request.cookies.get("access_token")
            assert access_token
            response: Response = await call_next(request)
            if (
                not request.url.path.startswith("/api")
                and (
                    token_data := await TokenManager().get_token_data(
                        access_token, None
                    )
                )
                is not None
            ):
                expire = token_data.expire
                if expire - datetime.utcnow() < timedelta(minutes=10):
                    access_token = await AuthManager().refresh_token(request)
                    response.set_cookie(
                        key="access_token",
                        value=access_token,
                        httponly=True,
                        samesite="lax",
                    )
        except HTTPException as e:
            # 令牌无效或过期，重定向到登录页面
            response = RedirectResponse(url="/", status_code=303)
            if e.status_code == 401:
                response.delete_cookie("access_token")
                return response
            raise e
    return response
