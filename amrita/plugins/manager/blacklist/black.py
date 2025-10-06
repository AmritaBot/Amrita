from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from nonebot import logger, require
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

require("nonebot_plugin_orm")
from async_lru import alru_cache
from nonebot_plugin_orm import get_session

from .models import GroupBlacklist, PrivateBlacklist


@dataclass
class BL_Data:
    reason: str
    time: datetime


class BL_Manager:
    """
    黑名单管理器
    """

    @staticmethod
    def del_cache(
        which: Literal["private", "group", "all"] = "all", where: str = "all"
    ):
        to_cache_private = (
            BL_Manager.is_private_black,
            BL_Manager.get_private_blacklist,
        )
        to_cache_group = (
            BL_Manager.get_group_blacklist,
            BL_Manager.is_group_black,
        )
        if which in ["all", "private"]:
            for func in to_cache_private:
                if which == "all" or where == "all":
                    func.cache_clear()
                else:
                    func.cache_invalidate(where)

        if which in ["all", "group"]:
            for func in to_cache_group:
                if which == "all" or where == "all":
                    func.cache_clear()
                else:
                    func.cache_invalidate(where)

        BL_Manager.get_full_blacklist.cache_clear()

    @staticmethod
    async def private_append(user_id: str, reason: str = "违反使用规则！"):
        BL_Manager.del_cache("private", user_id)
        async with get_session() as session:
            stmt = insert(PrivateBlacklist).values(user_id=user_id, reason=reason)
            await session.execute(stmt)
            await session.commit()
        logger.info(f"添加黑名单用户：{user_id}")

    @staticmethod
    async def group_append(group_id: str, reason: str = "违反使用规则！"):
        BL_Manager.del_cache("group", group_id)
        async with get_session() as session:
            try:
                stmt = insert(GroupBlacklist).values(group_id=group_id, reason=reason)
                await session.execute(stmt)
                await session.commit()
            except IntegrityError:
                logger.warning(f"群组{group_id}已存在")
        logger.info(f"添加黑名单群组：{group_id}")

    @staticmethod
    async def private_remove(user_id: str):
        BL_Manager.del_cache("private", user_id)
        async with get_session() as session:
            stmt = delete(PrivateBlacklist).where(PrivateBlacklist.user_id == user_id)
            result = await session.execute(stmt)
            await session.commit()
            deleted_count = result.rowcount
            if deleted_count:
                logger.info(f"移除黑名单用户：{user_id}")
            else:
                logger.warning(f"用户{user_id}不在黑名单中")

    @staticmethod
    async def group_remove(group_id: str):
        BL_Manager.del_cache("group", group_id)
        async with get_session() as session:
            stmt = delete(GroupBlacklist).where(GroupBlacklist.group_id == group_id)
            result = await session.execute(stmt)
            await session.commit()
            deleted_count = result.rowcount
            if deleted_count:
                logger.info(f"移除黑名单群组：{group_id}")
            else:
                logger.warning(f"群组{group_id}不在黑名单中")

    @staticmethod
    @alru_cache(1024)
    async def is_private_black(user_id: str) -> bool:
        async with get_session() as session:
            stmt = (
                select(PrivateBlacklist)
                .where(PrivateBlacklist.user_id == user_id)
                .with_for_update()
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    @staticmethod
    @alru_cache(1024)
    async def is_group_black(group_id: str) -> bool:
        async with get_session() as session:
            stmt = (
                select(GroupBlacklist)
                .where(GroupBlacklist.group_id == group_id)
                .with_for_update()
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    @staticmethod
    @alru_cache(1024)
    async def get_private_blacklist() -> dict[str, str]:
        async with get_session() as session:
            stmt = select(PrivateBlacklist).with_for_update()
            result = await session.execute(stmt)
            records = result.scalars().all()
            return {record.user_id: record.reason for record in records}

    @staticmethod
    @alru_cache(1024)
    async def get_group_blacklist() -> dict[str, str]:
        async with get_session() as session:
            stmt = select(GroupBlacklist).with_for_update()
            result = await session.execute(stmt)
            records = result.scalars().all()
            return {record.group_id: record.reason for record in records}

    @staticmethod
    @alru_cache(1024)
    async def get_full_blacklist() -> dict[str, dict[str, BL_Data]]:
        async with get_session() as session:
            private_blacklist = (
                (await session.execute(select(PrivateBlacklist))).scalars().all()
            )
            session.add_all(private_blacklist)
            pri_bl = {
                record.user_id: BL_Data(record.reason, record.created_at)
                for record in private_blacklist
            }
            group_blacklist = (
                (await session.execute(select(GroupBlacklist))).scalars().all()
            )
            session.add_all(group_blacklist)
            grp_bl = {
                record.group_id: BL_Data(record.reason, record.created_at)
                for record in group_blacklist
            }
            return {"group": grp_bl, "private": pri_bl}


bl_manager = BL_Manager
