from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse

from .service.authlib import AuthManager, OnetimeTokenData, TokenData, TokenManager
from .service.main import app
from .service.sidebar import SideBarCategory, SideBarItem, SideBarManager


@dataclass
class PageContext:
    request: Request
    sidebar: list[SideBarCategory]
    auth: AuthManager
    token_manager: TokenManager

    def get_sidebar(self) -> list[dict[str, Any]]:
        return [item.model_dump() for item in self.sidebar]


def on_page(
    path: str, page_name: str, category: str = "其他功能", icon: str | None = None
):
    """
    页面路由装饰器，用于注册Web UI页面

    该装饰器会自动处理页面的侧边栏显示、权限验证等通用功能，
    并将请求上下文传递给被装饰的处理函数。

    Args:
        path (str): 页面的URL路径
        page_name (str): 页面名称，将显示在侧边栏中
        category (str, optional): 页面所属的分类，默认为"其他功能"
        icon (str | None, optional): 页面图标，用于在侧边栏中显示

    Returns:
        Callable: 返回一个装饰器函数
    """

    def decorator(func: Callable[[PageContext], Awaitable[HTMLResponse]]):
        # 将当前页面添加到侧边栏对应分类中
        SideBarManager().add_sidebar_item(
            category, SideBarItem(name=page_name, url=path, icon=icon)
        )

        async def route(request: Request) -> HTMLResponse:
            # 深拷贝侧边栏数据，避免修改原始数据
            side_bar = deepcopy(SideBarManager().get_sidebar().items)
            # 设置当前分类和页面为激活状态
            for bar in side_bar:
                if bar.name == category:
                    bar.active = True
                    for item in bar.children:
                        if item.name == page_name:
                            item.active = True
                            break
                    break

            # 构造页面上下文并调用实际的处理函数
            ctx = PageContext(request, side_bar, AuthManager(), TokenManager())
            return await func(ctx)

        # 将路由添加到FastAPI应用中
        app.add_route(path, route, methods=["GET"], name=page_name)

    return decorator


__all__ = [
    "AuthManager",
    "OnetimeTokenData",
    "SideBarManager",
    "TokenData",
    "TokenManager",
]
