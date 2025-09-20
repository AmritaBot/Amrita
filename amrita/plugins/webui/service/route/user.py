from __future__ import annotations

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from amrita.plugins.manager.blacklist.black import BL_Manager
from amrita.plugins.perm.config import data_manager
from amrita.plugins.perm.nodelib import Permissions

from ..main import TemplatesManager, app
from ..sidebar import SideBarManager


@app.get("/user/blacklist", response_class=HTMLResponse)
async def _(request: Request):
    side_bar = SideBarManager().get_sidebar_dump()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            for child in bar.get("children", []):
                if child["name"] == "黑名单管理":
                    child["active"] = True
            break
    data = await BL_Manager.get_full_blacklist()
    response = TemplatesManager().TemplateResponse(
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


@app.get("/users/permissions", response_class=HTMLResponse)
async def permissions_page(request: Request):
    side_bar = SideBarManager().get_sidebar_dump()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            for child in bar.get("children", []):
                if child["name"] == "权限管理":
                    child["active"] = True
            break

    # 获取所有权限组
    permission_groups = []
    permission_groups_path = data_manager.permission_groups_path
    if permission_groups_path.exists():
        for file_path in permission_groups_path.glob("*.json"):
            group_name = file_path.stem
            group_data = Permissions()
            group_data.load_from_json(str(file_path))
            permission_groups.append(
                {
                    "name": group_name,
                    "permissions": group_data.perm_str,
                }
            )

    return TemplatesManager().TemplateResponse(
        "permissions.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "permission_groups": permission_groups,
        },
    )


@app.post("/api/users/permissions/perm_group/delete", response_class=JSONResponse)
async def delete_perm_group(request: Request):
    group_name = (await request.json()).get("group_name")
    if not group_name:
        return {"code": 400, "error": "请选择要删除的权限组"}
    data_manager.remove_permission_group(group_name)
    return JSONResponse({"code": 200, "error": None})


@app.get("/users/permissions/create_perm_group", response_class=HTMLResponse)
async def create_perm_group_page(request: Request):
    side_bar = SideBarManager().get_sidebar_dump()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            for child in bar.get("children", []):
                if child["name"] == "权限管理":
                    child["active"] = True
            break

    return TemplatesManager().TemplateResponse(
        "create_perm_group.html",
        {
            "request": request,
            "sidebar_items": side_bar,
        },
    )


@app.get("/users/permissions/user/{user_id}", response_class=HTMLResponse)
async def user_permissions_page(request: Request, user_id: str):
    side_bar = SideBarManager().get_sidebar_dump()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            for child in bar.get("children", []):
                if child["name"] == "权限管理":
                    child["active"] = True
            break

    # 获取用户权限数据
    user_data = data_manager.get_user_data(user_id)
    perm = Permissions(user_data.permissions)
    permissions_str = perm.permissions_str

    return TemplatesManager().TemplateResponse(
        "user_permissions.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "user_id": user_id,
            "user_data": {
                "permissions": permissions_str,
                "permission_groups": user_data.permission_groups,
            },
        },
    )


@app.get("/users/permissions/group/{group_id}", response_class=HTMLResponse)
async def group_permissions_page(request: Request, group_id: str):
    side_bar = SideBarManager().get_sidebar_dump()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            for child in bar.get("children", []):
                if child["name"] == "权限管理":
                    child["active"] = True
            break

    # 获取群组权限数据
    group_data = data_manager.get_group_data(group_id)
    perm = Permissions(group_data.permissions)
    permissions_str = perm.permissions_str

    return TemplatesManager().TemplateResponse(
        "group_permissions.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "group_id": group_id,
            "group_data": {
                "permissions": permissions_str,
                "permission_groups": group_data.permission_groups,
            },
        },
    )


@app.get("/users/permissions/perm_group/{group_name}", response_class=HTMLResponse)
async def perm_group_permissions_page(request: Request, group_name: str):
    side_bar = SideBarManager().get_sidebar_dump()

    for bar in side_bar:
        if bar["name"] == "用户管理":
            bar["active"] = True
            for child in bar.get("children", []):
                if child["name"] == "权限管理":
                    child["active"] = True
            break

    # 获取权限组权限数据
    if not data_manager.get_permission_group_data(group_name):
        raise HTTPException(status_code=404, detail="权限组不存在")

    perm = Permissions()
    permission_groups_path = data_manager.permission_groups_path
    group_file_path = permission_groups_path / f"{group_name}.json"

    if group_file_path.exists():
        perm.load_from_json(str(group_file_path))

    permissions_str = perm.permissions_str

    return TemplatesManager().TemplateResponse(
        "perm_group_permissions.html",
        {
            "request": request,
            "sidebar_items": side_bar,
            "group_name": group_name,
            "permissions": permissions_str,
        },
    )


@app.post("/api/users/permissions/user/{user_id}")
async def update_user_permissions(user_id: str, permissions: str = Form(...)):
    try:
        user_data = data_manager.get_user_data(user_id)
        perm = Permissions()
        perm.from_perm_str(permissions)
        user_data.permissions = perm.dump_data()

        # 保存用户数据
        data_manager.save_user_data(user_id, user_data.model_dump())

        return {"success": True, "message": "用户权限已更新"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/users/permissions/group/{group_id}")
async def update_group_permissions(group_id: str, permissions: str = Form(...)):
    try:
        perm = Permissions()
        perm.from_perm_str(permissions)
        group_data = data_manager.get_group_data(group_id)
        group_data.permissions = perm.dump_data()

        # 保存群组数据
        data_manager.save_group_data(group_id, group_data.model_dump())

        return {"success": True, "message": "群组权限已更新"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/users/permissions/perm_group/{group_name}")
async def update_perm_group_permissions(group_name: str, permissions: str = Form(...)):
    try:
        perm = Permissions()
        perm.from_perm_str(permissions)
        permissions_data = perm.dump_data()

        data_manager.save_permission_group_data(group_name, permissions_data)

        return {"success": True, "message": "权限组权限已更新"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
