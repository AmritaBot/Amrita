from abc import ABC
from asyncio import Lock
from collections import defaultdict
from typing import Any, Literal

from nonebot_plugin_orm import Model, get_session
from pydantic import BaseModel as B_Model
from sqlalchemy import JSON, Index, Integer, String, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column

from amrita.plugins.perm import nodelib

PERM_TYPE = Literal["group", "user"]


class PermissionGroup(Model):
    """
    权限组数据库模型

    用于在数据库中存储权限组信息。
    """

    __tablename__ = "lp_permission_group"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    permissions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    __table_args__ = (
        UniqueConstraint("group_name", name="uq_lp_permission_group_group_name"),
        Index("idx_lp_permission_group_group_name", "group_name"),
    )


class MemberPermission(Model):
    """
    成员权限数据库模型

    用于在数据库中存储成员（用户或群组）的权限信息。
    """

    __tablename__ = "lp_member_permission"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    any_id: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[PERM_TYPE] = mapped_column(String(255), nullable=False)
    permissions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    permission_groups: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    __table_args__ = (
        UniqueConstraint("any_id", "type", name="uq_lp_member_permission_any_id_type"),
        Index("idx_lp_member_permission_any_id_type", "any_id", "type"),
    )


class BaseModel(B_Model, ABC):
    """
    权限基础模型类

    所有权限相关模型的基类，提供权限数据的基本结构和转换方法。
    """

    permissions: dict[str, Any] | None

    def to_node(self):
        """
        将权限数据转换为Permissions节点对象

        Returns:
            nodelib.Permissions: 权限节点对象
        """
        return nodelib.Permissions(self.permissions)


class PermissionGroupPydantic(BaseModel):
    """
    权限组Pydantic模型

    用于表示权限组的基本信息。
    """

    group_name: str


class MemberPermissionPydantic(BaseModel):
    """
    成员权限Pydantic模型

    用于表示成员（用户或群组）的权限信息。
    """

    any_id: str
    type: PERM_TYPE
    permission_groups: list[str] | None


class PermissionStroage:
    """
    权限存储管理类

    该类负责管理权限组和成员权限的缓存和数据库操作，使用单例模式确保全局唯一实例。
    提供缓存机制以提高权限检查的性能，并保证数据一致性。
    """

    _instance = None
    _action_lock: defaultdict[str, Lock]
    _cached_permission_group_data: dict[str, PermissionGroupPydantic]
    _cached_any_permission_data: dict[tuple[str, PERM_TYPE], MemberPermissionPydantic]

    def __new__(cls, *args, **kwargs):
        """
        创建PermissionStroage单例实例

        Returns:
            PermissionStroage: 类的单例实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._cached_permission_group_data = {}
            cls._cached_any_permission_data = {}
            cls._action_lock = defaultdict(Lock)
        return cls._instance

    def _lock_maker(
        self, data: PermissionGroupPydantic | MemberPermissionPydantic
    ) -> Lock:
        """
        根据数据类型生成对应的锁

        Args:
            data (PermissionGroupPydantic | MemberPermissionPydantic): 权限数据对象

        Returns:
            Lock: 对应的锁对象

        Raises:
            ValueError: 当传入不支持的数据类型时
        """
        if isinstance(data, PermissionGroupPydantic):
            return self._action_lock[data.group_name]
        elif isinstance(data, MemberPermissionPydantic):
            return self._action_lock[str((data.any_id, data.type))]
        else:
            raise ValueError("Unsupported data type")

    async def expire_any_permission_cache(
        self,
        any_id: str,
        type: PERM_TYPE,
    ):
        """
        使指定成员权限缓存失效

        Args:
            any_id (str): 成员ID
            type (PERM_TYPE): 成员类型（"user" 或 "group"）
        """
        async with self._action_lock[str((any_id, type))]:
            self._cached_any_permission_data.pop((any_id, type), None)

    async def expire_permission_group_cache(
        self,
        group_name: str,
    ):
        """
        使指定权限组缓存失效

        Args:
            group_name (str): 权限组名称
        """
        async with self._action_lock[group_name]:
            self._cached_permission_group_data.pop(group_name, None)

    async def expire_any_permission_cache_all(
        self,
    ):
        """
        使所有成员权限缓存失效
        """
        self._cached_any_permission_data.clear()

    async def expire_permission_group_cache_all(
        self,
    ):
        """
        使所有权限组缓存失效
        """
        self._cached_permission_group_data.clear()

    async def expire_cache_all(self):
        """
        使所有缓存失效
        """
        await self.expire_any_permission_cache_all()
        await self.expire_permission_group_cache_all()

    async def permission_group_exists(self, group_name: str) -> bool:
        """
        判断权限组是否存在
        """
        if group_name in self._cached_permission_group_data:
            return True
        stmt = select(PermissionGroup).where(PermissionGroup.group_name == group_name)
        async with get_session() as session:
            return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def get_member_permission(
        self, any_id: str, type: PERM_TYPE, no_cache: bool = False
    ) -> MemberPermissionPydantic:
        """
        获取成员权限信息

        Args:
            any_id (str): 成员ID
            type (PERM_TYPE): 成员类型（"user" 或 "group"）
            no_cache (bool, optional): 是否跳过缓存直接从数据库获取. 默认为False

        Returns:
            MemberPermissionPydantic: 成员权限信息
        """
        async with self._action_lock[str((any_id, type))]:
            if (
                not no_cache
                and (data := self._cached_any_permission_data.get((any_id, type)))
                is not None
            ):
                return data
            async with get_session() as session:
                stmt = select(MemberPermission).where(
                    MemberPermission.any_id == any_id,
                    MemberPermission.type == type,
                )
                if (
                    result := (await session.execute(stmt)).scalar_one_or_none()
                ) is None:
                    result = MemberPermission(
                        any_id=any_id,
                        type=type,
                        permissions={},
                        permission_groups=[],
                    )
                    session.add(result)
                    await session.commit()
                    await session.refresh(result)
                data = MemberPermissionPydantic.model_validate(
                    result, from_attributes=True
                )
                if not no_cache:
                    self._cached_any_permission_data[(any_id, type)] = data
                return data

    async def get_permission_group(
        self, group_name: str, no_cache: bool = False
    ) -> PermissionGroupPydantic:
        """
        获取权限组信息，如果不存在会被隐式创建。

        Args:
            group_name (str): 权限组名称
            no_cache (bool, optional): 是否跳过缓存直接从数据库获取. 默认为False

        Returns:
            PermissionGroupPydantic: 权限组信息
        """
        async with self._action_lock[group_name]:
            if (
                not no_cache
                and (data := self._cached_permission_group_data.get(group_name))
                is not None
            ):
                return data
            async with get_session() as session:
                stmt = select(PermissionGroup).where(
                    PermissionGroup.group_name == group_name
                )
                result = (await session.execute(stmt)).scalar_one_or_none()
                if not result:
                    result = PermissionGroup(group_name=group_name, permissions={})
                    session.add(result)
                    await session.commit()
                    await session.refresh(result)
                data = PermissionGroupPydantic.model_validate(
                    result, from_attributes=True
                )
                if not no_cache:
                    self._cached_permission_group_data[group_name] = data
                return data

    async def refresh_member_permission(
        self, member_id: str, member_type: PERM_TYPE
    ) -> MemberPermissionPydantic:
        """
        刷新成员权限缓存

        Args:
            member_id (str): 成员ID
            member_type (PERM_TYPE): 成员类型

        Returns:
            MemberPermissionPydantic: 刷新后的成员权限信息

        Raises:
            ValueError: 当找不到指定成员时
        """
        async with self._action_lock[str((member_id, member_type))]:
            self._cached_any_permission_data.pop((member_id, member_type), None)
            async with get_session() as session:
                stmt = select(MemberPermission).where(
                    MemberPermission.any_id == member_id,
                    MemberPermission.type == member_type,
                )
                if (
                    result := (await session.execute(stmt)).scalar_one_or_none()
                ) is None:
                    raise ValueError(
                        f"Member `{member_id}` at `{member_type}` not found"
                    )
                data = MemberPermissionPydantic.model_validate(
                    result, from_attributes=True
                )
                self._cached_any_permission_data[(member_id, member_type)] = data
                return data

    async def refresh_permission_group(
        self, group_name: str
    ) -> PermissionGroupPydantic:
        """
        刷新权限组缓存

        Args:
            group_name (str): 权限组名称

        Returns:
            PermissionGroupPydantic: 刷新后的权限组信息

        Raises:
            ValueError: 当找不到指定权限组时
        """
        async with self._action_lock[group_name]:
            self._cached_permission_group_data.pop(group_name, None)
            async with get_session() as session:
                stmt = select(PermissionGroup).where(
                    PermissionGroup.group_name == group_name
                )
                permission_group = (await session.execute(stmt)).scalar_one_or_none()
                if not permission_group:
                    raise ValueError(f"Permission group `{group_name}` not found")
                data = PermissionGroupPydantic.model_validate(
                    permission_group, from_attributes=True
                )
                self._cached_permission_group_data[group_name] = data
                return data

    async def update_permission_group(self, data: PermissionGroupPydantic):
        """
        更新权限组信息

        Args:
            data (PermissionGroupPydantic): 权限组数据
        """
        async with self._lock_maker(data):
            async with get_session() as session:
                permission_group = (
                    await session.execute(
                        select(PermissionGroup)
                        .where(PermissionGroup.group_name == data.group_name)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if permission_group is None:
                    permission_group = PermissionGroup(
                        group_name=data.group_name,
                        permissions=data.permissions,
                    )
                    session.add(permission_group)
                else:
                    permission_group.permissions = data.permissions
                await session.commit()
            self._cached_permission_group_data[data.group_name] = data

    async def update_member_permission(self, data: MemberPermissionPydantic):
        """
        更新成员权限信息

        Args:
            data (MemberPermissionPydantic): 成员权限数据
        """
        async with self._lock_maker(data):
            async with get_session() as session:
                member_permission = (
                    await session.execute(
                        select(MemberPermission).where(
                            MemberPermission.any_id == data.any_id,
                            MemberPermission.type == data.type,
                        )
                    )
                ).scalar_one_or_none()
                if member_permission is None:
                    member_permission = MemberPermission(
                        any_id=data.any_id,
                        type=data.type,
                        permissions=data.permissions,
                        permission_groups=data.permission_groups,
                    )
                    session.add(member_permission)
                else:
                    member_permission.permissions = data.permissions
                    member_permission.permission_groups = data.permission_groups
                await session.commit()
            self._cached_any_permission_data[(data.any_id, data.type)] = data

    async def get_all_perm_groups(
        self, no_cache: bool = False
    ) -> list[PermissionGroupPydantic]:
        if no_cache:
            async with get_session() as session:
                stmt = select(PermissionGroup)
                result = (await session.execute(stmt)).scalars().all()
                return [
                    PermissionGroupPydantic.model_validate(it, from_attributes=True)
                    for it in result
                ]
        return list(self._cached_permission_group_data.values())

    async def get_all_member_permission(
        self, type: PERM_TYPE, no_cache: bool = False
    ) -> list[MemberPermissionPydantic]:
        if no_cache:
            async with get_session() as session:
                stmt = select(MemberPermission).where(MemberPermission.type == type)
                result = (await session.execute(stmt)).scalars().all()
                return [
                    MemberPermissionPydantic.model_validate(it, from_attributes=True)
                    for it in result
                ]
        return [v for k, v in self._cached_any_permission_data.items() if k[1] == type]

    async def init_cache_from_database(self):
        """
        从数据库初始化所有权限缓存
        """
        async with get_session() as session:
            permission_groups = await session.execute(select(PermissionGroup))
            for permission_group in permission_groups.scalars():
                name = permission_group.group_name
                async with self._action_lock[name]:
                    self._cached_permission_group_data[name] = (
                        PermissionGroupPydantic.model_validate(
                            permission_group, from_attributes=True
                        )
                    )
            del permission_groups
            members = await session.execute(select(MemberPermission))
            for member in members.scalars():
                mbid, mbtype = member.any_id, member.type
                async with self._action_lock[str((mbid, mbtype))]:
                    self._cached_any_permission_data[(mbid, mbtype)] = (
                        MemberPermissionPydantic.model_validate(
                            member, from_attributes=True
                        )
                    )
