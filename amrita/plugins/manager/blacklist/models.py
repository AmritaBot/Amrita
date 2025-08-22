from nonebot import require
from sqlalchemy import String, Text
from sqlalchemy.orm import MappedColumn, mapped_column

require("nonebot_plugin_orm")
from nonebot_plugin_orm import Model


class GroupBlacklist(Model):
    group_id: MappedColumn[str] = mapped_column(String(50), primary_key=True)
    reason: MappedColumn[str] = mapped_column(Text)

    __tablename__ = "group_blacklist"


class PrivateBlacklist(Model):
    user_id: MappedColumn[str] = mapped_column(String(50), primary_key=True)
    reason: MappedColumn[str] = mapped_column(Text)

    __tablename__ = "private_blacklist"
