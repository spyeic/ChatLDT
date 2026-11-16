"""Use Open WebUI's engine and migration history; SQLite writes reserve first."""

from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import MetaData, Table
from alembic import command
from alembic.config import Config
from open_webui.internal.db import engine

_tables = {}


def migrate():
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / 'alembic.ini'))
    cfg.set_main_option('script_location', str(root / 'migrations'))
    database = Path(engine.url.database)
    creating = not database.exists()
    command.upgrade(cfg, 'head')
    if creating:
        for path in (database, Path(str(database) + '-wal'), Path(str(database) + '-shm')):
            if path.exists():
                path.chmod(0o600)


def table(name):
    if name not in _tables:
        _tables[name] = Table(name, MetaData(), autoload_with=engine)
    return _tables[name]


@contextmanager
def transaction():
    # A deferred SELECT followed by UPDATE is insufficient under SQLite/WAL.
    # Reserve the write lock before ALL authorization/state reads, across workers.
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('ChatLDT currently supports SQLite only; no untested concurrency fallback.')
    with engine.connect() as conn:
        conn.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
