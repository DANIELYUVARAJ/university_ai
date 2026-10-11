"""
University DataShield - Database Abstraction Adapter
Phase 11: Production Security & Scalability

Provides an abstracted repository/database interface layer.
Supports:
- SQLite (local development and prototyping)
- PostgreSQL compatible interface specification
- Connection pooling abstraction
- Safe parameterized query execution (anti-SQL injection)
- Migration readiness
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional, AsyncIterator
import aiosqlite
import logging
try:
    from config import get_settings
except ImportError:
    from backend.config import get_settings

logger = logging.getLogger("datashield.db")


class DatabaseAdapter(ABC):
    """Abstract Database Adapter."""

    @abstractmethod
    async def connect(self):
        """Establish connection or connection pool."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Close connection or connection pool."""
        pass

    @abstractmethod
    async def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute parameterized query."""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch single row as dictionary."""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Verify database responsiveness."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Any]:
        """Context manager providing an atomic transaction."""
        pass


class SQLiteDatabaseAdapter(DatabaseAdapter):
    """SQLite implementation using aiosqlite with WAL mode and transaction support."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        return True

    async def disconnect(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL;")
            cursor = await conn.execute(query, params or ())
            await conn.commit()
            return cursor.lastrowid

    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params or ())
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params or ())
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    async def ping(self) -> bool:
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute("SELECT 1")
                row = await cursor.fetchone()
                return bool(row and row[0] == 1)
        except Exception as e:
            logger.error(f"SQLite ping failed: {e}")
            return False

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """Provide atomic transaction boundary."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        await conn.execute("BEGIN TRANSACTION;")
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            await conn.close()


class DatabaseUnavailableError(RuntimeError):
    """Raised when the requested database or connection pool is unavailable."""
    pass


class PostgresDatabaseAdapter(DatabaseAdapter):
    """
    PostgreSQL adapter specification for enterprise production deployment.
    Uses asyncpg pooling abstraction when configured and available.
    Fails closed with typed DatabaseUnavailableError when offline or unconfigured.
    """

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self._pool = None

    @staticmethod
    def _convert_placeholders(query: str) -> str:
        """Convert '?' style placeholders to PostgreSQL '$1', '$2', ..."""
        if "?" not in query:
            return query
        parts = query.split("?")
        result = []
        for i, part in enumerate(parts[:-1], start=1):
            result.append(f"{part}${i}")
        result.append(parts[-1])
        return "".join(result)

    async def connect(self) -> bool:
        """Attempt to establish asyncpg connection pool if driver and credentials exist."""
        try:
            import asyncpg  # type: ignore
        except ImportError:
            logger.warning("PostgreSQL driver (asyncpg) is not installed in the active environment.")
            self._pool = None
            return False

        try:
            # Clean connection attempt without logging credentials
            self._pool = await asyncpg.create_pool(
                self.connection_url,
                min_size=2,
                max_size=10,
                timeout=5.0,
            )
            logger.info("PostgreSQL connection pool successfully established.")
            return True
        except Exception as exc:
            logger.error("PostgreSQL connection pool failed: %s", type(exc).__name__)
            self._pool = None
            raise DatabaseUnavailableError(f"PostgreSQL connection failed: {type(exc).__name__}") from exc

    async def disconnect(self):
        """Close connection pool gracefully."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL connection pool closed.")

    async def ping(self) -> bool:
        """Verify database responsiveness without leaking credentials."""
        if not self._pool:
            return False
        try:
            async with self._pool.acquire() as conn:
                val = await conn.fetchval("SELECT 1")
                return val == 1
        except Exception as exc:
            logger.error("PostgreSQL ping failed: %s", type(exc).__name__)
            return False

    async def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        if not self._pool:
            raise DatabaseUnavailableError("PostgreSQL adapter: database pool is not connected.")
        conv = self._convert_placeholders(query)
        async with self._pool.acquire() as conn:
            return await conn.execute(conv, *(params or ()))

    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        if not self._pool:
            raise DatabaseUnavailableError("PostgreSQL adapter: database pool is not connected.")
        conv = self._convert_placeholders(query)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(conv, *(params or ()))
            return dict(row) if row else None

    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        if not self._pool:
            raise DatabaseUnavailableError("PostgreSQL adapter: database pool is not connected.")
        conv = self._convert_placeholders(query)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(conv, *(params or ()))
            return [dict(r) for r in rows]

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[Any]:
        if not self._pool:
            raise DatabaseUnavailableError("PostgreSQL adapter: database pool is not connected.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn


def get_database_adapter() -> DatabaseAdapter:
    """Factory creating appropriate database adapter according to settings."""
    settings = get_settings()
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
        return PostgresDatabaseAdapter(db_url)
    else:
        try:
            from database import DB_PATH
        except ImportError:
            from backend.database import DB_PATH
        return SQLiteDatabaseAdapter(str(DB_PATH))

