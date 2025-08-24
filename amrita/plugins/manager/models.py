import asyncio
from datetime import datetime, timedelta
from functools import lru_cache

from nonebot_plugin_orm import AsyncSession, Model, get_session
from pydantic import BaseModel
from sqlalchemy import (
    BigInteger,
    Index,
    Integer,
    String,
    UniqueConstraint,
    delete,
    insert,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column


@lru_cache(1024)
def lock(*args, **kwargs):
    return asyncio.Lock()


class DailyUsage(Model):
    __tablename__ = "amrita_daily_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(
        String(64), default=lambda: datetime.now().strftime("%Y-%m-%d"), nullable=False
    )
    bot_id: Mapped[str] = mapped_column(String(255), nullable=False)
    msg_received: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    msg_sent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    __table_args__ = (
        # 添加索引
        Index("idx_bot_id", "bot_id"),
        Index("idx_created_at", "created_at"),
        UniqueConstraint("bot_id", "created_at", name="uq_bot_id_created_at"),
    )


class DailyUsagePydantic(BaseModel):
    id: int
    created_at: str
    bot_id: str
    msg_received: int
    msg_sent: int


async def expire_usage(session: AsyncSession):
    stmt = delete(DailyUsage).where(
        DailyUsage.created_at
        < (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    )
    await session.execute(stmt)


async def get_usage(bot_id: str) -> list[DailyUsagePydantic]:
    async with lock(bot_id):
        async with get_session() as session:
            await expire_usage(session)
            stmt = select(DailyUsage).where(DailyUsage.bot_id == bot_id)
            if not (result := (await session.execute(stmt)).scalars().all()):
                stmt = insert(DailyUsage).values(bot_id=bot_id)
                await session.execute(stmt)
                result = (await session.execute(stmt)).scalars().all()
            session.add_all(result)
            return [
                DailyUsagePydantic.model_validate(x, from_attributes=True)
                for x in result
            ]


async def add_usage(bot_id: str, msg_received: int, msg_sent: int):
    async with lock(bot_id):
        async with get_session() as session:
            await expire_usage(session)
            stmt = (
                select(DailyUsage)
                .where(
                    DailyUsage.bot_id == bot_id,
                    DailyUsage.created_at == datetime.now().strftime("%Y-%m-%d"),
                )
                .with_for_update()
            )
            if (result := (await session.execute(stmt)).scalar_one_or_none()) is None:
                stmt = insert(DailyUsage).values(
                    bot_id=bot_id,
                    msg_received=msg_received,
                    msg_sent=msg_sent,
                )
                await session.execute(stmt)
                await session.commit()
                return
            result.msg_received += msg_received
            result.msg_sent += msg_sent
            await session.commit()
