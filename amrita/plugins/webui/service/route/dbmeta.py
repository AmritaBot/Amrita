from dataclasses import asdict

from nonebot import logger
from nonebot_plugin_orm import get_session
from sqlalchemy import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from amrita.plugins.webui.API import PageContext, PageResponse, on_page
from amrita.utils.dbmetadata import AsyncDatabasePerformanceCollector, DatabaseType


def get_database_type(
    bind: Engine | Connection | AsyncSession | AsyncEngine,
) -> DatabaseType:
    if isinstance(bind, AsyncSession):
        bind = bind.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    name: str = bind.url.drivername
    if "postgresql" in name:
        return "postgresql"
    elif "mysql" in name:
        return "mysql"
    elif "mariadb" in name:
        return "mariadb"
    elif "sqlite" in name:
        return "sqlite"
    else:
        raise RuntimeError(f"Unsupported database type `{name}`")


@on_page("/bot/database", "数据库元信息", "系统信息")
async def db_metadata_page(ctx: PageContext) -> PageResponse:
    """数据库元信息页面"""
    try:
        session: AsyncSession = get_session()
        db_type = get_database_type(session)

        async with session:
            collector = AsyncDatabasePerformanceCollector(session, db_type)
            metrics = await collector.collect_performance_stats()

        return PageResponse(
            name="dbmetadata.html",
            context={
                "db_info": metrics.database_info,
                "connection_stats": asdict(metrics.connection_stats),
                "cache_efficiency": asdict(metrics.cache_efficiency),
                "table_activity": [
                    asdict(ta) for ta in metrics.table_activity[:10]
                ],  # 只显示前10个表
                "index_usage": [
                    asdict(iu) for iu in metrics.index_usage[:10]
                ],  # 只显示前10个索引
                "lock_info": [asdict(li) for li in metrics.lock_info],
                "query_stats": [
                    asdict(qs) for qs in metrics.query_stats[:10]
                ],  # 只显示前10个查询
                "collection_timestamp": metrics.collection_timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "db_type": metrics.db_type,
            },
        )

    except Exception as e:
        logger.error(f"获取数据库元信息失败: {e}")
        return PageResponse(
            name="dbmetadata.html",
            context={
                "error": f"获取数据库元信息失败: {e!s}",
                "db_info": {},
                "connection_stats": {},
                "cache_efficiency": {},
                "table_activity": [],
                "index_usage": [],
                "lock_info": [],
                "query_stats": [],
                "collection_timestamp": "",
                "db_type": "",
            },
        )
