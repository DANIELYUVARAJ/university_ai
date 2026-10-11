"""
University DataShield - Migration Runner
Phase 12: Production Database Migrations

Provides deterministic, versioned, transactional migrations with checksum validation
and safe status reporting.
"""

import hashlib
import importlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import aiosqlite

try:
    from database import DB_PATH
except ImportError:
    from backend.database import DB_PATH

logger = logging.getLogger("datashield.migrations")


async def ensure_migration_table(conn: aiosqlite.Connection) -> None:
    """Create schema_migrations tracking table if missing."""
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            checksum   TEXT NOT NULL
        );
        """
    )
    await conn.commit()


def get_available_migrations() -> List[Dict[str, Any]]:
    """Scan and return all migration definitions in numerical order."""
    migrations = []
    migrations_dir = Path(__file__).parent
    migration_files = sorted(migrations_dir.glob("m[0-9]*_*.py"))

    for f in migration_files:
        try:
            mod = importlib.import_module(f"migrations.{f.stem}")
        except ModuleNotFoundError:
            mod = importlib.import_module(f"backend.migrations.{f.stem}")
            content = f.read_bytes()
            chk = hashlib.sha256(content).hexdigest()[:16]
            migrations.append({
                "version": getattr(mod, "VERSION", f.stem.split("_")[0][1:]),
                "name": getattr(mod, "NAME", f.stem),
                "module": mod,
                "file_path": str(f),
                "checksum": chk
            })
        except Exception as exc:
            logger.error("Failed to load migration %s: %s", mod_name, exc)
            raise

    # Sort strictly by version
    migrations.sort(key=lambda m: m["version"])
    return migrations


async def get_applied_migrations(conn: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Query schema_migrations table."""
    await ensure_migration_table(conn)
    cursor = await conn.execute(
        "SELECT version, name, applied_at, checksum FROM schema_migrations ORDER BY version ASC"
    )
    rows = await cursor.fetchall()
    return [
        {
            "version": r[0],
            "name": r[1],
            "applied_at": r[2],
            "checksum": r[3]
        }
        for r in rows
    ]


async def run_migrations(target_db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute all pending migrations sequentially within transactions.
    Safe and idempotent.
    """
    db_file = target_db_path or str(DB_PATH)
    available = get_available_migrations()
    applied_now = []

    async with aiosqlite.connect(db_file) as conn:
        conn.row_factory = aiosqlite.Row
        await ensure_migration_table(conn)
        applied = await get_applied_migrations(conn)
        applied_versions = {m["version"] for m in applied}

        for mig in available:
            ver = mig["version"]
            if ver not in applied_versions:
                logger.info("Applying migration %s: %s...", ver, mig["name"])
                # Transactional execution
                try:
                    await conn.execute("BEGIN TRANSACTION;")
                    await mig["module"].up(conn)
                    now_str = datetime.now(timezone.utc).isoformat()
                    await conn.execute(
                        """
                        INSERT INTO schema_migrations (version, name, applied_at, checksum)
                        VALUES (?, ?, ?, ?);
                        """,
                        (ver, mig["name"], now_str, mig["checksum"])
                    )
                    await conn.commit()
                    applied_now.append(ver)
                    logger.info("Successfully applied migration %s", ver)
                except Exception as exc:
                    await conn.execute("ROLLBACK;")
                    logger.critical("Failed migration %s: %s", ver, exc)
                    raise RuntimeError(f"Migration {ver} failed: {exc}") from exc

    status = await get_migration_status(db_file)
    return {
        "applied_now": applied_now,
        "current_version": status["latest_version"],
        "is_up_to_date": status["is_up_to_date"]
    }


async def get_migration_status(target_db_path: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve current migration state."""
    db_file = target_db_path or str(DB_PATH)
    available = get_available_migrations()

    try:
        async with aiosqlite.connect(db_file) as conn:
            applied = await get_applied_migrations(conn)
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "is_up_to_date": False,
            "latest_version": None,
            "applied_count": 0,
            "total_available": len(available)
        }

    applied_versions = {m["version"] for m in applied}
    pending = [m["version"] for m in available if m["version"] not in applied_versions]
    latest = applied[-1]["version"] if applied else None

    return {
        "status": "up_to_date" if not pending else "pending",
        "is_up_to_date": len(pending) == 0,
        "latest_version": latest,
        "applied_count": len(applied),
        "total_available": len(available),
        "applied": applied,
        "pending": pending
    }
