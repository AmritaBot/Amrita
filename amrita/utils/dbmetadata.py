from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from nonebot import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.engine import AsyncConnection, AsyncEngine

# 定义支持的数据库类型
DatabaseType = Literal["sqlite", "mysql", "mariadb", "postgresql"]


# 枚举定义
class LockMode(str, Enum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"
    UPDATE = "update"
    ACCESS_SHARE = "access_share"
    ROW_SHARE = "row_share"
    ROW_EXCLUSIVE = "row_exclusive"


# 定义返回的dataclasses
@dataclass
class ConnectionStats:
    """连接统计信息"""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    max_allowed_connections: int | None = None
    connection_utilization_percent: float | None = None
    longest_query_seconds: float | None = None
    waiting_connections: int | None = None


@dataclass
class CacheEfficiency:
    """缓存效率统计"""

    buffer_pool_hit_ratio: float | None = None
    heap_hit_ratio: float | None = None
    index_hit_ratio: float | None = None
    logical_reads: int | None = None
    physical_reads: int | None = None
    cache_size_mb: float | None = None
    cache_used_percent: float | None = None


@dataclass
class TableActivity:
    """表活动统计"""

    table_name: str
    schema_name: str | None = None
    full_scans: int | None = None
    rows_scanned: int | None = None
    rows_inserted: int | None = None
    rows_updated: int | None = None
    rows_deleted: int | None = None
    live_rows: int | None = None
    dead_rows: int | None = None
    total_size_mb: float | None = None
    index_size_mb: float | None = None
    last_vacuum: datetime | None = None
    last_analyze: datetime | None = None


@dataclass
class IndexUsage:
    """索引使用情况"""

    index_name: str
    table_name: str
    schema_name: str | None = None
    scan_count: int | None = None
    rows_fetched: int | None = None
    cardinality: int | None = None
    unique: bool | None = None
    size_mb: float | None = None
    definition: str | None = None
    last_used: datetime | None = None


@dataclass
class LockInfo:
    """锁信息"""

    lock_type: str
    lock_mode: str
    lock_count: int = 1
    waiting_count: int | None = None
    blocked_pids: list[int] | None = None
    blocked_queries: list[str] | None = None


@dataclass
class QueryStats:
    """查询统计"""

    query_hash: str | None = None
    query_text: str | None = None
    total_executions: int | None = None
    total_time_ms: float | None = None
    avg_time_ms: float | None = None
    min_time_ms: float | None = None
    max_time_ms: float | None = None
    rows_returned: int | None = None
    shared_blks_hit: int | None = None
    shared_blks_read: int | None = None


@dataclass
class PerformanceMetrics:
    """性能指标汇总"""

    database_info: dict[str, Any]
    connection_stats: ConnectionStats
    cache_efficiency: CacheEfficiency
    table_activity: list[TableActivity]
    index_usage: list[IndexUsage]
    lock_info: list[LockInfo]
    query_stats: list[QueryStats]
    collection_timestamp: datetime
    db_type: DatabaseType

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)


# 主函数
class AsyncDatabasePerformanceCollector:
    """异步数据库性能收集器"""

    def __init__(self, session: AsyncSession, db_type: DatabaseType):
        """
        初始化收集器

        Args:
            session: SQLAlchemy异步会话
            db_type: 数据库类型
        """
        self.session: AsyncSession = session
        self.db_type: DatabaseType = db_type
        self.engine: AsyncEngine | AsyncConnection = session.bind

    async def collect_performance_stats(self) -> PerformanceMetrics:
        """
        收集完整的性能统计信息

        Returns:
            PerformanceMetrics对象
        """
        try:
            # 并行收集所有统计信息
            db_info = await self._get_database_info()
            conn_stats = await self._get_connection_stats()
            cache_stats = await self._get_cache_efficiency()
            table_activity = await self._get_table_activity()
            index_usage = await self._get_index_usage()
            lock_info = await self._get_lock_info()
            query_stats = await self._get_query_stats()

            return PerformanceMetrics(
                database_info=db_info,
                connection_stats=conn_stats,
                cache_efficiency=cache_stats,
                table_activity=table_activity,
                index_usage=index_usage,
                lock_info=lock_info,
                query_stats=query_stats,
                collection_timestamp=datetime.now(),
                db_type=self.db_type,
            )

        except Exception as e:
            logger.error(f"收集性能统计信息失败: {e}")
            raise

    async def _get_database_info(self) -> dict[str, Any]:
        """获取数据库基本信息"""
        try:
            if self.db_type in ("mysql", "mariadb"):
                result = await self.session.execute(
                    text(
                        "SELECT VERSION() as version, DATABASE() as db_name, "
                        + "USER() as current_user, @@hostname as server_host, "
                        + "@@version_comment as version_comment"
                    )
                )
                row = result.fetchone()
                return dict(row._mapping) if row else {}

            elif self.db_type == "postgresql":
                result = await self.session.execute(
                    text(
                        "SELECT version(), current_database(), current_user, "
                        "inet_server_addr(), pg_postmaster_start_time()"
                    )
                )
                row = result.fetchone()
                if row:
                    return {
                        "version": row[0],
                        "database_name": row[1],
                        "current_user": row[2],
                        "server_ip": row[3],
                        "start_time": row[4],
                    }

            elif self.db_type == "sqlite":
                result = await self.session.execute(text("SELECT sqlite_version()"))
                version = result.scalar()
                return {
                    "version": version,
                    "database_name": "sqlite_db",
                    "current_user": "sqlite",
                    "server_ip": "embedded",
                }

            return {}

        except Exception as e:
            logger.warning(f"获取数据库信息失败: {e}")
            return {}

    async def _get_connection_stats(self) -> ConnectionStats:
        """获取连接统计"""
        try:
            if self.db_type == "postgresql":
                result = await self.session.execute(
                    text("""
                    SELECT
                        COUNT(*) as total_connections,
                        COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                        COUNT(*) FILTER (WHERE state = 'idle') as idle_connections,
                        COUNT(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                        MAX(EXTRACT(EPOCH FROM (now() - query_start))) as longest_query_seconds,
                        COUNT(*) FILTER (WHERE wait_event IS NOT NULL) as waiting_connections,
                        current_setting('max_connections')::int as max_connections
                    FROM pg_stat_activity
                    WHERE pid <> pg_backend_pid()
                """)
                )
                row = result.fetchone()
                if row:
                    total = row.total_connections
                    max_conn = row.max_connections
                    utilization = (total / max_conn * 100) if max_conn else None

                    return ConnectionStats(
                        total_connections=total,
                        active_connections=row.active_connections,
                        idle_connections=row.idle_connections,
                        max_allowed_connections=max_conn,
                        connection_utilization_percent=utilization,
                        longest_query_seconds=float(row.longest_query_seconds)
                        if row.longest_query_seconds
                        else None,
                        waiting_connections=row.waiting_connections,
                    )

            elif self.db_type in ("mysql", "mariadb"):
                # 获取连接状态
                result = await self.session.execute(
                    text("""
                    SHOW STATUS WHERE Variable_name IN (
                        'Threads_connected', 'Threads_running',
                        'Threads_created', 'Threads_cached',
                        'Max_used_connections'
                    )
                """)
                )
                status_rows = result.fetchall()
                status_dict = {row.Variable_name: int(row.Value) for row in status_rows}

                # 获取变量
                result = await self.session.execute(
                    text("SHOW VARIABLES LIKE 'max_connections'")
                )
                var_row = result.fetchone()
                max_conn = int(var_row.Value) if var_row else None

                threads_connected = status_dict.get("Threads_connected", 0)
                utilization = (threads_connected / max_conn * 100) if max_conn else None

                return ConnectionStats(
                    total_connections=threads_connected,
                    active_connections=status_dict.get("Threads_running", 0),
                    idle_connections=threads_connected
                    - status_dict.get("Threads_running", 0),
                    max_allowed_connections=max_conn,
                    connection_utilization_percent=utilization,
                    waiting_connections=None,  # MySQL需要查询PROCESSLIST中的'Locked'状态
                )

            elif self.db_type == "sqlite":
                return ConnectionStats(
                    total_connections=1,
                    active_connections=1,
                    idle_connections=0,
                    max_allowed_connections=1,
                )

        except Exception as e:
            logger.warning(f"获取连接统计失败: {e}")

        return ConnectionStats()

    async def _get_cache_efficiency(self) -> CacheEfficiency:
        """获取缓存效率"""
        try:
            if self.db_type == "postgresql":
                result = await self.session.execute(
                    text("""
                    WITH cache_stats AS (
                        SELECT
                            sum(heap_blks_hit) as heap_hit,
                            sum(heap_blks_read) as heap_read,
                            sum(idx_blks_hit) as idx_hit,
                            sum(idx_blks_read) as idx_read
                        FROM pg_statio_user_tables
                    )
                    SELECT
                        CASE WHEN heap_hit + heap_read > 0
                            THEN heap_hit::float / (heap_hit + heap_read) * 100
                            ELSE 0 END as heap_hit_ratio,
                        CASE WHEN idx_hit + idx_read > 0
                            THEN idx_hit::float / (idx_hit + idx_read) * 100
                            ELSE 0 END as idx_hit_ratio,
                        heap_hit + idx_hit as logical_reads,
                        heap_read + idx_read as physical_reads
                    FROM cache_stats
                """)
                )
                row = result.fetchone()
                if row:
                    return CacheEfficiency(
                        heap_hit_ratio=float(row.heap_hit_ratio),
                        index_hit_ratio=float(row.idx_hit_ratio),
                        logical_reads=row.logical_reads,
                        physical_reads=row.physical_reads,
                    )

            elif self.db_type in ("mysql", "mariadb"):
                # InnoDB缓冲池统计
                result = await self.session.execute(
                    text("""
                    SHOW STATUS WHERE Variable_name LIKE 'Innodb_buffer_pool%'
                """)
                )
                rows = result.fetchall()
                stats = {row.Variable_name: int(row.Value) for row in rows}

                read_requests = stats.get("Innodb_buffer_pool_read_requests", 0)
                reads = stats.get("Innodb_buffer_pool_reads", 0)

                hit_ratio = 0
                if read_requests > 0:
                    hit_ratio = (1 - reads / read_requests) * 100

                # 缓冲池大小
                result = await self.session.execute(
                    text("SHOW VARIABLES LIKE 'innodb_buffer_pool_size'")
                )
                var_row = result.fetchone()
                pool_size_bytes = int(var_row.Value) if var_row else None

                # 缓冲池使用情况
                result = await self.session.execute(
                    text(
                        "SELECT @@innodb_buffer_pool_size as pool_size, "
                        "@@innodb_buffer_pool_pages_total as total_pages, "
                        "@@innodb_buffer_pool_pages_free as free_pages"
                    )
                )
                pool_row = result.fetchone()

                cache_used = None
                if pool_row and pool_row.total_pages > 0:
                    cache_used = (1 - pool_row.free_pages / pool_row.total_pages) * 100

                return CacheEfficiency(
                    buffer_pool_hit_ratio=hit_ratio,
                    logical_reads=read_requests,
                    physical_reads=reads,
                    cache_size_mb=pool_size_bytes / (1024 * 1024)
                    if pool_size_bytes
                    else None,
                    cache_used_percent=cache_used,
                )

            elif self.db_type == "sqlite":
                result = await self.session.execute(text("PRAGMA cache_size"))
                cache_pages = result.scalar()

                result = await self.session.execute(text("PRAGMA page_size"))
                page_size = result.scalar()

                cache_size = None
                if cache_pages and page_size:
                    cache_size = (cache_pages * page_size) / (1024 * 1024)

                return CacheEfficiency(cache_size_mb=cache_size)

        except Exception as e:
            logger.warning(f"获取缓存效率失败: {e}")

        return CacheEfficiency()

    async def _get_table_activity(self) -> list[TableActivity]:
        """获取表活动统计"""
        tables: list[TableActivity] = []

        try:
            if self.db_type == "postgresql":
                result = await self.session.execute(
                    text("""
                    SELECT
                        schemaname,
                        relname,
                        seq_scan,
                        seq_tup_read,
                        n_tup_ins,
                        n_tup_upd,
                        n_tup_del,
                        n_live_tup,
                        n_dead_tup,
                        pg_total_relation_size(quote_ident(schemaname) || '.' || quote_ident(relname)) as total_bytes,
                        pg_indexes_size(quote_ident(schemaname) || '.' || quote_ident(relname)) as index_bytes,
                        last_vacuum,
                        last_analyze
                    FROM pg_stat_user_tables
                    ORDER BY seq_scan DESC
                    LIMIT 20
                """)
                )

                for row in result:
                    total_mb = (
                        row.total_bytes / (1024 * 1024) if row.total_bytes else None
                    )
                    index_mb = (
                        row.index_bytes / (1024 * 1024) if row.index_bytes else None
                    )

                    tables.append(
                        TableActivity(
                            table_name=row.relname,
                            schema_name=row.schemaname,
                            full_scans=row.seq_scan,
                            rows_scanned=row.seq_tup_read,
                            rows_inserted=row.n_tup_ins,
                            rows_updated=row.n_tup_upd,
                            rows_deleted=row.n_tup_del,
                            live_rows=row.n_live_tup,
                            dead_rows=row.n_dead_tup,
                            total_size_mb=total_mb,
                            index_size_mb=index_mb,
                            last_vacuum=row.last_vacuum,
                            last_analyze=row.last_analyze,
                        )
                    )

            elif self.db_type in ("mysql", "mariadb"):
                # 获取当前数据库名
                db_result = await self.session.execute(text("SELECT DATABASE()"))
                db_name = db_result.scalar()

                if db_name:
                    result = await self.session.execute(
                        text("""
                        SELECT
                            TABLE_NAME,
                            TABLE_ROWS,
                            AVG_ROW_LENGTH,
                            DATA_LENGTH,
                            INDEX_LENGTH,
                            DATA_FREE,
                            AUTO_INCREMENT,
                            UPDATE_TIME
                        FROM information_schema.TABLES
                        WHERE TABLE_SCHEMA = :db_name
                        ORDER BY DATA_LENGTH + INDEX_LENGTH DESC
                        LIMIT 20
                    """),
                        {"db_name": db_name},
                    )

                    for row in result:
                        index_mb = (
                            row.INDEX_LENGTH / (1024 * 1024)
                            if row.INDEX_LENGTH
                            else None
                        )
                        total_mb = (
                            (row.DATA_LENGTH or 0) + (row.INDEX_LENGTH or 0)
                        ) / (1024 * 1024)

                        tables.append(
                            TableActivity(
                                table_name=row.TABLE_NAME,
                                schema_name=db_name,
                                live_rows=row.TABLE_ROWS,
                                total_size_mb=total_mb,
                                index_size_mb=index_mb,
                            )
                        )

            elif self.db_type == "sqlite":
                # 获取所有表名
                result = await self.session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                )
                table_names = [row[0] for row in result.fetchall()]

                for table_name in table_names[:20]:  # 限制前20个表
                    # 获取行数
                    count_result = await self.session.execute(
                        text(f'SELECT COUNT(*) FROM "{table_name}"')
                    )
                    row_count = count_result.scalar()

                    tables.append(
                        TableActivity(table_name=table_name, live_rows=row_count)
                    )

        except Exception as e:
            logger.warning(f"获取表活动统计失败: {e}")

        return tables

    async def _get_index_usage(self) -> list[IndexUsage]:
        """获取索引使用情况"""
        indexes: list[IndexUsage] = []

        try:
            if self.db_type == "postgresql":
                result = await self.session.execute(
                    text("""
                    SELECT
                        schemaname,
                        tablename,
                        indexname,
                        idx_scan,
                        idx_tup_read,
                        idx_tup_fetch,
                        pg_relation_size(quote_ident(schemaname) || '.' || quote_ident(indexname)) as index_size
                    FROM pg_stat_user_indexes
                    ORDER BY idx_scan ASC
                    LIMIT 20
                """)
                )

                for row in result:
                    size_mb = row.index_size / (1024 * 1024) if row.index_size else None

                    indexes.append(
                        IndexUsage(
                            index_name=row.indexname,
                            table_name=row.tablename,
                            schema_name=row.schemaname,
                            scan_count=row.idx_scan,
                            rows_fetched=row.idx_tup_fetch,
                            size_mb=size_mb,
                        )
                    )

            elif self.db_type in ("mysql", "mariadb"):
                # 获取当前数据库名
                db_result = await self.session.execute(text("SELECT DATABASE()"))
                db_name = db_result.scalar()

                if db_name:
                    result = await self.session.execute(
                        text("""
                        SELECT
                            TABLE_NAME,
                            INDEX_NAME,
                            NON_UNIQUE,
                            SEQ_IN_INDEX,
                            CARDINALITY,
                            INDEX_TYPE,
                            SUB_PART,
                            PACKED,
                            NULLABLE,
                            INDEX_COMMENT
                        FROM information_schema.STATISTICS
                        WHERE TABLE_SCHEMA = :db_name
                        ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
                        LIMIT 50
                    """),
                        {"db_name": db_name},
                    )

                    # 按索引名分组，获取每个索引的第一列信息
                    index_map: dict[str, dict] = {}

                    for row in result:
                        index_key = f"{row.TABLE_NAME}.{row.INDEX_NAME}"
                        if index_key not in index_map:
                            index_map[index_key] = {
                                "table_name": row.TABLE_NAME,
                                "index_name": row.INDEX_NAME,
                                "unique": row.NON_UNIQUE == 0,
                                "cardinality": row.CARDINALITY,
                                "type": row.INDEX_TYPE,
                            }

                        indexes = [
                            IndexUsage(
                                index_name=idx_info["index_name"],
                                table_name=idx_info["table_name"],
                                schema_name=db_name,
                                cardinality=idx_info["cardinality"],
                                unique=idx_info["unique"],
                            )
                            for idx_info in index_map.values()
                        ]

            elif self.db_type == "sqlite":
                result = await self.session.execute(
                    text(
                        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'index'"
                    )
                )

                indexes = [
                    IndexUsage(
                        index_name=row.name,
                        table_name=row.tbl_name,
                        definition=row.sql,
                    )
                    for row in result
                ]

        except Exception as e:
            logger.warning(f"获取索引使用情况失败: {e}")

        return indexes

    async def _get_lock_info(self) -> list[LockInfo]:
        """获取锁信息"""
        locks: list[LockInfo] = []

        try:
            if self.db_type == "postgresql":
                result = await self.session.execute(
                    text("""
                    SELECT
                        locktype,
                        mode,
                        COUNT(*) as lock_count,
                        COUNT(*) FILTER (WHERE granted = false) as waiting_count,
                        ARRAY_AGG(DISTINCT pid) as pids
                    FROM pg_locks
                    WHERE pid <> pg_backend_pid()
                    GROUP BY locktype, mode
                    HAVING COUNT(*) > 0
                    ORDER BY lock_count DESC
                """)
                )

                for row in result:
                    # 获取被阻塞的查询（如果有等待的锁）
                    blocked_queries = []
                    if row.waiting_count and row.waiting_count > 0:
                        query_result = await self.session.execute(
                            text("""
                            SELECT query FROM pg_stat_activity
                            WHERE pid = ANY(:pids) AND wait_event_type = 'Lock'
                        """),
                            {"pids": list(row.pids) if row.pids else []},
                        )
                        blocked_queries = [q[0] for q in query_result.fetchall()]

                    locks.append(
                        LockInfo(
                            lock_type=row.locktype,
                            lock_mode=row.mode,
                            lock_count=row.lock_count,
                            waiting_count=row.waiting_count,
                            blocked_pids=list(row.pids) if row.pids else None,
                            blocked_queries=blocked_queries
                            if blocked_queries
                            else None,
                        )
                    )

            elif self.db_type in ("mysql", "mariadb"):
                # 使用InnoDB锁信息
                result = await self.session.execute(
                    text("""
                    SELECT
                        r.trx_id AS waiting_trx_id,
                        r.trx_mysql_thread_id AS waiting_thread,
                        r.trx_query AS waiting_query,
                        b.trx_id AS blocking_trx_id,
                        b.trx_mysql_thread_id AS blocking_thread,
                        b.trx_query AS blocking_query
                    FROM information_schema.INNODB_LOCK_WAITS w
                    INNER JOIN information_schema.INNODB_TRX b ON b.trx_id = w.blocking_trx_id
                    INNER JOIN information_schema.INNODB_TRX r ON r.trx_id = w.requesting_trx_id
                """)
                )

                # 按锁类型分组
                lock_groups: dict[str, LockInfo] = {}

                for row in result:
                    lock_key = (
                        f"waiting:{row.waiting_trx_id}:blocking:{row.blocking_trx_id}"
                    )

                    if lock_key not in lock_groups:
                        lock_groups[lock_key] = LockInfo(
                            lock_type="row_lock",  # InnoDB主要是行锁
                            lock_mode="exclusive",  # 阻塞的锁通常是排他锁
                            lock_count=1,
                            waiting_count=1,
                            blocked_pids=[row.waiting_thread],
                            blocked_queries=[row.waiting_query],
                        )
                    else:
                        lock_groups[lock_key].lock_count += 1

                locks = list(lock_groups.values())

        except Exception as e:
            logger.warning(f"获取锁信息失败: {e}")

        return locks

    async def _get_query_stats(self) -> list[QueryStats]:
        """获取查询统计"""
        queries: list[QueryStats] = []

        try:
            if self.db_type == "postgresql":
                # 检查pg_stat_statements扩展是否启用
                result = await self.session.execute(
                    text(
                        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_stat_statements'"
                    )
                )
                extension_exists = (result.scalar() or 0) > 0

                if extension_exists:
                    result = await self.session.execute(
                        text("""
                        SELECT
                            queryid,
                            query,
                            calls,
                            total_exec_time,
                            mean_exec_time,
                            min_exec_time,
                            max_exec_time,
                            rows,
                            shared_blks_hit,
                            shared_blks_read
                        FROM pg_stat_statements
                        ORDER BY total_exec_time DESC
                        LIMIT 10
                    """)
                    )
                    queries = [
                        QueryStats(
                            query_hash=str(row.queryid),
                            query_text=row.query[:500]
                            if row.query
                            else None,  # 截断长查询
                            total_executions=row.calls,
                            total_time_ms=row.total_exec_time,
                            avg_time_ms=row.mean_exec_time,
                            min_time_ms=row.min_exec_time,
                            max_time_ms=row.max_exec_time,
                            rows_returned=row.rows,
                            shared_blks_hit=row.shared_blks_hit,
                            shared_blks_read=row.shared_blks_read,
                        )
                        for row in result
                    ]

            elif self.db_type in ("mysql", "mariadb"):
                # 检查performance_schema是否启用
                result = await self.session.execute(
                    text("SHOW VARIABLES LIKE 'performance_schema'")
                )
                perf_schema_row = result.fetchone()
                perf_schema_enabled = perf_schema_row and perf_schema_row.Value == "ON"

                if perf_schema_enabled:
                    result = await self.session.execute(
                        text("""
                        SELECT
                            DIGEST_TEXT,
                            COUNT_STAR,
                            SUM_TIMER_WAIT / 1000000000 as total_time_seconds,
                            AVG_TIMER_WAIT / 1000000000 as avg_time_seconds,
                            MIN_TIMER_WAIT / 1000000000 as min_time_seconds,
                            MAX_TIMER_WAIT / 1000000000 as max_time_seconds,
                            SUM_ROWS_SENT,
                            SUM_ROWS_EXAMINED
                        FROM performance_schema.events_statements_summary_by_digest
                        WHERE DIGEST_TEXT IS NOT NULL
                        ORDER BY SUM_TIMER_WAIT DESC
                        LIMIT 10
                    """)
                    )

                    for row in result:
                        queries.append(
                            QueryStats(
                                query_text=row.DIGEST_TEXT[:500]
                                if row.DIGEST_TEXT
                                else None,
                                total_executions=row.COUNT_STAR,
                                total_time_ms=row.total_time_seconds * 1000,
                                avg_time_ms=row.avg_time_seconds * 1000,
                                min_time_ms=row.min_time_seconds * 1000,
                                max_time_ms=row.max_time_seconds * 1000,
                                rows_returned=row.SUM_ROWS_SENT,
                            )
                        )
                else:
                    # 尝试从慢查询日志获取
                    result = await self.session.execute(
                        text("SHOW GLOBAL STATUS LIKE 'Slow_queries'")
                    )
                    slow_queries_row = result.fetchone()
                    if slow_queries_row:
                        queries.append(
                            QueryStats(
                                query_text="慢查询统计",
                                total_executions=int(slow_queries_row.Value),
                            )
                        )

        except Exception as e:
            logger.warning(f"获取查询统计失败: {e}")

        return queries


# 使用示例
async def collect_database_performance(
    session: AsyncSession, db_type: DatabaseType
) -> PerformanceMetrics:
    """
    主函数：收集数据库性能统计

    Args:
        session: SQLAlchemy异步会话
        db_type: 数据库类型

    Returns:
        PerformanceMetrics对象
    """
    collector = AsyncDatabasePerformanceCollector(session, db_type)
    return await collector.collect_performance_stats()
