"""Create an exclusive local backup; stop the application for file/DB consistency."""

import argparse
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from open_webui.env import DATA_DIR, DATABASE_URL, BASE_DIR


def backup(output):
    output = Path(output).resolve()
    if output.is_relative_to(DATA_DIR):
        raise RuntimeError('Backup destination must be outside DATA_DIR')
    if output.exists():
        raise RuntimeError('Backup already exists; refusing to overwrite')
    database = Path(DATABASE_URL.removeprefix('sqlite:///')).resolve()
    if not database.exists():
        raise RuntimeError('Database does not exist; run setup first')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chatldt-backup-') as temporary:
        target = Path(temporary)
        # Snapshot the DB using SQLite's backup API; copy attachment and key data.
        shutil.copytree(
            DATA_DIR,
            target / 'data',
            ignore=shutil.ignore_patterns('webui.db', 'webui.db-wal', 'webui.db-shm'),
            dirs_exist_ok=True,
        )
        with sqlite3.connect(database) as source, sqlite3.connect(target / 'data/webui.db') as destination:
            source.backup(destination)
        if (BASE_DIR / '.env').is_file():
            shutil.copy2(BASE_DIR / '.env', target / '.env')
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in target.rglob('*'):
                if path.is_file():
                    archive.write(path, path.relative_to(target))
    output.chmod(0o600)
    print(
        'Backup created. Protect it as a credential: it includes private conversations, hashes and server configuration.'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Stop ChatLDT before backup so images and SQLite are consistent.')
    parser.add_argument('output', help='New .zip path outside DATA_DIR')
    args = parser.parse_args()
    backup(args.output)
