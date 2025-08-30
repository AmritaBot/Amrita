from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from amrita.plugins.manager.blacklist.black import BL_Manager

from ..main import app, templates
from ..sidebar import SideBarManager


@app.get("/user/blacklist", response_class=HTMLResponse)
async def _(request: Request):
    side_bar = SideBarManager().get_sidebar_dump()
    data = await BL_Manager.get_full_blacklist()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            break
    response = templates.TemplateResponse(
        "blacklist.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "group_blacklist": [
                {
                    "id": k,
                    "reason": v.reason,
                    "added_time": v.time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for k, v in data["group"].items()
            ],
            "user_blacklist": [
                {
                    "id": k,
                    "reason": v.reason,
                    "added_time": v.time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for k, v in data["private"].items()
            ],
        },
    )
    return response
