from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    after_scheme = url.split("///", 1)[-1]
    if not after_scheme:
        return
    path = Path(after_scheme)
    parent = path.parent
    if str(parent) and str(parent) != ".":
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            pass


_ensure_sqlite_dir(settings.DATABASE_URL)

connect_args = (
    {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    future=True,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover
    """Pragmas pro frischer SQLite-Connection.

    - `foreign_keys=ON`: FK-Checks aktivieren (SQLite-Default ist OFF).
    - `journal_mode=WAL`: Reads blockieren Writes nicht. Erzeugt `.db-wal` /
      `.db-shm` neben der DB - Backups muessen alle drei Dateien mitnehmen.
    - `busy_timeout=5000`: 5 s warten statt sofort "database is locked".
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        # Grosszuegig warten statt sofort "database is locked" - der Sync und
        # interaktive Requests teilen sich eine SQLite-Datei.
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
    except Exception:
        pass


# expire_on_commit=False: bei haeufigen Commits (Sync committet pro Event) sollen
# ORM-Objekte ihre Werte behalten, statt bei jedem Zugriff neu zu laden.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
    future=True,
)


class Base(DeclarativeBase):
    pass
