from datetime import datetime

from nonebot import require
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

require("nonebot_plugin_orm")
from nonebot_plugin_orm import Model


class GroupBlacklist(Model):
    group_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    __tablename__ = "group_blacklist"


class PrivateBlacklist(Model):
    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )

    __tablename__ = "private_blacklist"
