"""Upgrade an isolated copy of an upstream-head DB, preserving legacy payloads."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_existing_upstream_database_copy_migrates_without_data_loss(tmp_path):
    old = tmp_path / 'legacy'
    old.mkdir()
    env = {**os.environ, 'DATA_DIR': str(old), 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    env.pop('DATABASE_URL', None)
    script = """
from pathlib import Path
from alembic.config import Config
from alembic import command
from open_webui.env import OPEN_WEBUI_DIR
c=Config(str(OPEN_WEBUI_DIR/'alembic.ini'))
c.set_main_option('script_location',str(OPEN_WEBUI_DIR/'migrations'))
command.upgrade(c,'9f6c2a8d1b43')
"""
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    original = old / 'webui.db'
    copy = tmp_path / 'copy.db'
    with sqlite3.connect(original) as db:
        db.execute(
            "INSERT INTO user (id,email,role,name,oauth) VALUES ('legacy-user','old@example.test','user','Old',?)",
            ('{"google":{"sub":"legacy-sub"}}',),
        )
        db.execute(
            "INSERT INTO auth (id,email,password,active) VALUES ('legacy-user','old@example.test','existing-encoded-hash',1)"
        )
        tree = '{"history":{"messages":{"one":{"id":"one","childrenIds":["two","branch"],"content":"keep all branches"},"two":{"id":"two","parentId":"one"},"branch":{"id":"branch","parentId":"one"}},"currentId":"two"}}'
        db.execute(
            "INSERT INTO chat (id,user_id,title,chat,created_at,updated_at) VALUES ('legacy-chat','legacy-user','Old title',?,1,2)",
            (tree,),
        )
        db.execute(
            "INSERT INTO file (id,user_id,filename,path) VALUES ('legacy-file','legacy-user','image.png','/private/legacy/image.png')"
        )
        db.commit()
        before = {t: db.execute('SELECT * FROM ' + t).fetchall() for t in ['user', 'auth', 'chat', 'file']}
        with sqlite3.connect(copy) as target:
            db.backup(target)
    migrated = {**env, 'DATABASE_URL': 'sqlite:///' + str(copy)}
    result = subprocess.run(
        [sys.executable, '-m', 'open_webui.manual.setup', 'migrate'], env=migrated, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(copy) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'ldt001'
        for t in before:
            assert db.execute('SELECT * FROM ' + t).fetchall() == before[t]
        assert db.execute('SELECT count(*) FROM ldt_conversation').fetchone()[0] == 0
    with sqlite3.connect(original) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '9f6c2a8d1b43'
