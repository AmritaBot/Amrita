from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from nonebot import logger
from starlette.templating import _TemplateResponse

from .service.authlib import AuthManager, OnetimeTokenData, TokenData, TokenManager
from .service.main import TEMPLATES_PATH, TemplatesManager, app, templates
from .service.sidebar import SideBarCategory, SideBarItem, SideBarManager


@dataclass
class PageResponse:
    """
    自定义的响应类，用于处理页面渲染结果
    """

    name: str
    context: dict[str, Any] = field(default_factory=dict)
    status_code: int = field(default=200)
    headers: Mapping[str, str] | None = None
    media_type: str | None = None


@dataclass
class PageContext:
    """Page context
    A class that holds the context for a page
    """

    request: Request
    auth: AuthManager
    token_manager: TokenManager


def on_page(path: str, page_name: str, category: str = "其他功能"):
    """
    页面路由装饰器，用于注册Web UI页面

    该装饰器会自动处理页面的侧边栏显示、权限验证等通用功能，
    并将请求上下文传递给被装饰的处理函数。

    Args:
        path (str): 页面的URL路径
        page_name (str): 页面名称，将显示在侧边栏中
        category (str, optional): 页面所属的分类，分类不存在时将创建一个分类

    Returns:
        Callable: 返回一个装饰器函数
    """

    def decorator(func: Callable[[PageContext], Awaitable[PageResponse]]):
        # 将当前页面添加到侧边栏对应分类中
        if all(cate.name != category for cate in SideBarManager().get_sidebar().items):
            SideBarManager().add_sidebar_category(
                SideBarCategory(name=category, icon="fa fa-question", url="#")
            )
        SideBarManager().add_sidebar_item(
            category, SideBarItem(name=page_name, url=path)
        )
        page_path = path

        async def route(request: Request) -> _TemplateResponse:
            # 深拷贝侧边栏数据，避免修改原始数据
            side_bar = deepcopy(SideBarManager().get_sidebar().items)
            logger.debug(page_path)
            # 设置当前分类和页面为激活状态
            if request.url.path == page_path:
                for bar in side_bar:
                    if bar.name == category:
                        bar.active = True
                        for item in bar.children:
                            if item.name == page_name:
                                item.active = True
                                break
                        break
                else:
                    logger.warning(
                        f"Invalid page category `{category}` for page {path}"
                    )

            # 构造页面上下文并调用实际的处理函数
            ctx = PageContext(request, AuthManager(), TokenManager())
            page = await func(ctx)

            # 构建模板上下文
            context = page.context
            # 更新页面特定的上下文
            context.update(
                {
                    "sidebar_items": [a.model_dump() for a in side_bar],
                    "debug": app.debug,
                    "base_html": "base.html",
                }
            )

            return TemplatesManager().TemplateResponse(
                request,
                page.name,
                context,
                status_code=page.status_code,
                headers=page.headers,
                media_type=page.media_type,
            )

        # 将路由添加到FastAPI应用中
        app.add_route(path, route, methods=["GET"], name=page_name)

    return decorator


def get_templates_dir() -> Path:
    return TEMPLATES_PATH


__all__ = [
    "TEMPLATES_PATH",
    "AuthManager",
    "HTMLResponse",
    "JSONResponse",
    "OnetimeTokenData",
    "PageContext",
    "SideBarManager",
    "TokenData",
    "TokenManager",
    "app",
    "get_templates_dir",
    "on_page",
    "templates",
]
