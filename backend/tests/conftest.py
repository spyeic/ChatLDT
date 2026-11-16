import os
import sys
import tempfile
from pathlib import Path

os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='chatldt-tests-')
os.environ['PUBLIC_ORIGIN'] = 'http://testserver'
os.environ['WEBUI_SECRET_KEY'] = 'test-only-key-not-a-deployment-secret'
os.environ['OPENAI_API_KEY'] = ''
os.environ['GOOGLE_CLIENT_ID'] = ''
os.environ['GOOGLE_CLIENT_SECRET'] = ''
os.environ['ENV'] = 'dev'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert
from open_webui.main import app
from open_webui.manual.database import migrate, transaction, table
from open_webui.manual.security import create_user, hash_password
from open_webui.routers.manual import _limits

migrate()


@pytest.fixture(autouse=True)
def clean():
    _limits.clear()
    with transaction() as conn:
        for name in [
            'ldt_request',
            'ldt_round',
            'ldt_message',
            'ldt_conversation',
            'ldt_upload',
            'ldt_title_job',
            'ldt_gc',
            'ldt_session',
            'ldt_admin',
            'ldt_principal',
            'auth',
            'user',
            'chat',
            'file',
        ]:
            conn.execute(delete(table(name)))
    yield


@pytest.fixture
def client():
    return TestClient(app)


def csrf(client):
    return {'x-ldt-csrf': client.get('/api/v1/ldt/session').json()['csrf']}


def signup(client, email='friend@example.test', name='Friend'):
    r = client.post(
        '/api/v1/ldt/signup', json={'email': email, 'name': name, 'password': 'test-password-123'}, headers=csrf(client)
    )
    assert r.status_code == 200, r.text
    return client.get('/api/v1/ldt/session').json()['identity']


def guest(client, name='Guest'):
    r = client.post('/api/v1/ldt/guest', json={'name': name}, headers=csrf(client))
    assert r.status_code == 200, r.text
    return client.get('/api/v1/ldt/session').json()['identity']


@pytest.fixture
def admin():
    with transaction() as conn:
        user = create_user(conn, 'duo@example.test', hash_password('admin-test-password'), 'Duo', admin=True)
        conn.execute(insert(table('ldt_admin')).values(singleton=1, user_id=user['id']))
    client = TestClient(app)
    r = client.post(
        '/api/v1/ldt/signin',
        json={'email': 'duo@example.test', 'password': 'admin-test-password'},
        headers=csrf(client),
    )
    assert r.status_code == 200, r.text
    return client
