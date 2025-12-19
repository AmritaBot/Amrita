from __future__ import annotations

from pydantic import BaseModel
from typing_extensions import Self


class SideBarItem(BaseModel):
    name: str
    icon: str | None = None
    url: str | None = None
    active: bool = False


class SideBarCategory(BaseModel):
    name: str
    icon: str | None = None
    url: str | None = None
    active: bool = False
    children: list[SideBarItem] = []


class SideBar(BaseModel):
    items: list[SideBarCategory] = [
        SideBarCategory(
            name="仪表盘", icon="fa fa-dashboard", url="/dashboard", active=False
        ),
        SideBarCategory(
            name="机器人管理",
            icon="fa fa-robot",
            url="#",
            active=False,
            children=[
                SideBarItem(name="状态监控", url="/bot/status", active=False),
                SideBarItem(name="插件管理", url="/bot/plugins", active=False),
                SideBarItem(name="Dotenv编辑", url="/bot/config", active=False),
            ],
        ),
        SideBarCategory(
            name="用户管理",
            icon="fas fa-users",
            url="#",
            active=False,
            children=[
                SideBarItem(name="权限管理", url="/users/permissions", active=False),
                SideBarItem(name="黑名单管理", url="/user/blacklist", active=False),
            ],
        ),
    ]


class SideBarManager:
    _instance = None
    sidebar: SideBar

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.sidebar = SideBar()
        return cls._instance

    def get_sidebar(self) -> SideBar:
        return self.sidebar

    def get_sidebar_dump(self) -> list[dict]:
        return [item.model_dump() for item in self.sidebar.items]

    def add_sidebar_category(self, item: SideBarCategory):
        self.sidebar.items.append(item)

    def set_sidebar_items(self, items: list[SideBarCategory]):
        self.sidebar.items = items

    def add_sidebar_item(self, category: str, item: SideBarItem):
        for category_item in self.sidebar.items:
            if category_item.name == category:
                category_item.children.append(item)
                return

    def set_sidebar_item(self, category: str, item: SideBarItem):
        for category_item in self.sidebar.items:
            if category_item.name == category:
                category_item.children = [item]
                return
