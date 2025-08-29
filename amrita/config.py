"""Amrita核心配置模块

该模块定义了Amrita机器人的核心配置模型和获取配置的方法。
"""

from typing import Literal

from nonebot import get_plugin_config, logger
from pydantic import BaseModel, model_validator


class AmritaConfig(BaseModel):
    """Amrita核心配置模型"""

    # 日志目录
    log_dir: str = "logs"

    max_event_record: int = 1000

    # 管理员群组ID
    admin_group: int = -1

    # 禁用的内置插件列表
    disabled_builtin_plugins: list[Literal["chat", "manager", "perm", "menu"]] = []

    # Amrita日志级别
    amrita_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        "WARNING"
    )

    # 公开群组ID（Bot对外展示）
    public_group: int = 0

    # 机器人名称
    bot_name: str = "Amrita"

    # 请求速率限制（间隔秒）
    rate_limit: int = 5

    # 是否禁用内置菜单
    disable_builtin_menu: bool = False

    @model_validator(mode="after")
    def _vali(self):
        if not self.admin_group > 0:
            logger.error("Amrita config 'admin_group' must be set as a real group ID")
            raise ValueError(
                "Amrita config 'admin_group' must be set as a real group ID"
            )
        return self


def get_amrita_config() -> AmritaConfig:
    """获取Amrita配置

    Returns:
        AmritaConfig: Amrita配置对象
    """
    return get_plugin_config(AmritaConfig)
