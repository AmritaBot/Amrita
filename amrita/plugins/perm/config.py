import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomli
import tomli_w
from nonebot_plugin_localstore import get_plugin_config_dir, get_plugin_data_dir
from pydantic import BaseModel, Field

plugin_data_dir = get_plugin_data_dir()
config_dir = get_plugin_config_dir()
os.makedirs(plugin_data_dir, exist_ok=True)
os.makedirs(config_dir, exist_ok=True)


class BasicDataModel(BaseModel, extra="allow"): ...


class UserData(BasicDataModel):
    permission_groups: list[str] = []
    permissions: dict[str, str | dict | bool] = {}


class GroupData(BasicDataModel):
    permission_groups: list[str] = []
    permissions: dict[str, str | dict | bool] = {}


class PermissionGroupData(BasicDataModel):
    permissions: dict[str, str | dict | bool] = {}


class Config(BasicDataModel):
    enable: bool = Field(default=True, description="是否启用插件")

    def save_to_toml(self, path: Path):
        """保存配置到 TOML 文件"""
        with path.open("w", encoding="utf-8") as f:
            f.write(tomli_w.dumps(self.model_dump()))

    @classmethod
    def load_from_toml(cls, path: Path) -> "Config":
        """从 TOML 文件加载配置"""
        if not path.exists():
            return cls()
        with path.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = tomli.loads(f.read())
        # 自动更新配置文件
        current_config = cls().model_dump()
        updated_config = {**current_config, **data}
        config_instance = cls(**updated_config)
        config_instance.model_validate(updated_config)  # 校验配置
        return config_instance


@dataclass
class Data_Manager:
    plugin_data_dir: Path = plugin_data_dir
    group_data_path: Path = plugin_data_dir / "group_data"
    user_data_path: Path = plugin_data_dir / "user_data"
    permission_groups_path: Path = plugin_data_dir / "permission_groups"
    config_path: Path = config_dir / "config.toml"
    # cmd_settings_path = plugin_data_dir / "command_settings.json"
    config: Config = field(default_factory=Config)

    def init(self):
        os.makedirs(self.group_data_path, exist_ok=True)
        os.makedirs(self.user_data_path, exist_ok=True)
        os.makedirs(self.permission_groups_path, exist_ok=True)

        if not self.config_path.exists():
            self.config = Config()
            self.config.save_to_toml(self.config_path)
        else:
            self.config = Config.load_from_toml(self.config_path)

        """
        if not self.cmd_settings_path.exists():
            cmd_settings = CommandConfig()
            with open(self.cmd_settings_path, "w") as f:
                json.dump(cmd_settings.model_dump(), f, indent=4)
        else:
            with open(self.cmd_settings_path) as f:
                self.cmd_settings = CommandConfig.model_validate_json(f.read())
"""

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


"""
    def get_command_settings(self):
        with open(self.cmd_settings_path) as f:
            return CommandConfig(**json.load(f))

    def save_command_settings(self, data: CommandConfig):
        with open(self.cmd_settings_path, "w") as f:
            json.dump(data.model_dump(), f)
"""

data_manager = Data_Manager()
