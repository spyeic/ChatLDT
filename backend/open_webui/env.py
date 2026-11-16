"""Environment shared by Open WebUI's retained database/migration infrastructure."""

import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

OPEN_WEBUI_DIR = Path(__file__).resolve().parent
BACKEND_DIR = OPEN_WEBUI_DIR.parent
BASE_DIR = BACKEND_DIR.parent
load_dotenv(BASE_DIR / '.env')
DATA_DIR = Path(os.getenv('DATA_DIR', str(BACKEND_DIR / 'data'))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA_DIR}/webui.db')
if not DATABASE_URL.startswith('sqlite:///'):
    raise RuntimeError('ChatLDT supports local SQLite only. Use sqlite:/// followed by an absolute path.')
DATABASE_PASSWORD = None
DATABASE_SCHEMA = None
DATABASE_ENABLE_IAM_TOKEN_AUTH = False
DATABASE_ENABLE_SESSION_SHARING = False
DATABASE_ENABLE_SQLITE_WAL = True
DATABASE_POOL_SIZE = 8
DATABASE_POOL_MAX_OVERFLOW = 4
DATABASE_POOL_RECYCLE = 3600
DATABASE_POOL_TIMEOUT = 30
DATABASE_SQLITE_PRAGMA_SYNCHRONOUS = 'NORMAL'
DATABASE_SQLITE_PRAGMA_BUSY_TIMEOUT = '10000'
DATABASE_SQLITE_PRAGMA_CACHE_SIZE = '-8192'
DATABASE_SQLITE_PRAGMA_TEMP_STORE = 'MEMORY'
DATABASE_SQLITE_PRAGMA_MMAP_SIZE = '0'
DATABASE_SQLITE_PRAGMA_JOURNAL_SIZE_LIMIT = '67108864'
ENABLE_DB_MIGRATIONS = True
ENABLE_ORJSON = True
USE_SLIM = False
LOG_FORMAT = os.getenv('LOG_FORMAT', '')
VERSION = (
    json.loads((BASE_DIR / 'package.json').read_text()).get('version', '0.13.3')
    if (BASE_DIR / 'package.json').exists()
    else '0.13.3'
)


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({'level': record.levelname, 'message': record.getMessage()}, ensure_ascii=False)
