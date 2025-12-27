"""保留的旧权限系统"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from nonebot_plugin_localstore import get_plugin_config_dir, get_plugin_data_dir
from pydantic import BaseModel

plugin_data_dir = get_plugin_data_dir()
config_dir = get_plugin_config_dir()


class UserData(BaseModel):
    permission_groups: list[str] = []
    permissions: dict[str, str | dict | bool] = {}


class GroupData(BaseModel):
    permission_groups: list[str] = []
    permissions: dict[str, str | dict | bool] = {}


class PermissionGroupData(BaseModel):
    permissions: dict[str, str | dict | bool] = {}


@dataclass
class Data_Manager:
    plugin_data_dir: Path = plugin_data_dir
    group_data_path: Path = plugin_data_dir / "group_data"
    user_data_path: Path = plugin_data_dir / "user_data"
    permission_groups_path: Path = plugin_data_dir / "permission_groups"
    config_path: Path = config_dir / "config.toml"

    async def init(self):
        os.makedirs(self.group_data_path, exist_ok=True)
        os.makedirs(self.user_data_path, exist_ok=True)
        os.makedirs(self.permission_groups_path, exist_ok=True)

    def save_user_data(self, user_id: str, data: dict[str, str | dict | bool]):
        UserData.model_validate(data)
        data_path = self.user_data_path / f"{user_id}.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def save_group_data(self, group_name: str, data: dict[str, str | dict | bool]):
        GroupData.model_validate(data)
        data_path = self.group_data_path / f"{group_name}.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def save_permission_group_data(
        self, group_name: str, data: dict[str, str | dict | bool]
    ):
        PermissionGroupData.model_validate(data)
        data_path = self.permission_groups_path / f"{group_name}.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def get_group_data(self, group_id: str):
        data_path = self.group_data_path / f"{group_id}.json"
        if not data_path.exists():
            data = GroupData()
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data.model_dump(), f)
            return data
        with open(data_path, encoding="utf-8") as f:
            return GroupData(**json.load(f))

    def get_permission_group_data(
        self, group_name: str, new: bool = False
    ) -> PermissionGroupData | None:
        data_path = self.permission_groups_path / f"{group_name}.json"
        if not data_path.exists():
            if not new:
                return None
            else:
                data = PermissionGroupData()
                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump(data.model_dump(), f)
                return data
        with open(data_path, encoding="utf-8") as f:
            return PermissionGroupData(**json.load(f))

    def remove_permission_group(self, group: str):
        data_path = self.permission_groups_path / f"{group}.json"
        if data_path.exists():
            os.remove(data_path)

    def get_user_data(self, user_id: str):
        data_path = self.user_data_path / f"{user_id}.json"
        if not data_path.exists():
            data = UserData()
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(data.model_dump(), f)
            return data
        with open(data_path, encoding="utf-8") as f:
            return UserData(**json.load(f))
