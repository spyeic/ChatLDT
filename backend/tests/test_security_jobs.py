from uuid import uuid4
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from conftest import csrf, signup, guest
from test_manual import send, png, BASE, edit
from open_webui.main import app
from open_webui.manual import jobs, setup, security
from open_webui.manual.database import transaction, table
from open_webui.manual.security import row


def test_setup_repeat_and_password_reset_revokes_sessions(client, admin, monkeypatch):
    signup(client)
    with transaction() as conn:
        before = conn.scalar(select(table('auth').c.password).where(table('auth').c.email == 'duo@example.test'))
    monkeypatch.setattr(
        setup.getpass, 'getpass', lambda prompt: (_ for _ in ()).throw(AssertionError('must not prompt on setup rerun'))
    )
    setup.setup()
    with transaction() as conn:
        assert (
            conn.scalar(select(table('auth').c.password).where(table('auth').c.email == 'duo@example.test')) == before
        )
    answers = iter(['friend@example.test', 'replacement-password', 'replacement-password'])
    monkeypatch.setattr(setup.getpass, 'getpass', lambda prompt: next(answers))
    setup.reset()
    assert client.get(BASE + '/chats').status_code == 401
    assert (
        client.post(
            BASE + '/signin',
            json={'email': 'friend@example.test', 'password': 'replacement-password'},
            headers=csrf(client),
        ).status_code
        == 200
    )


def test_guest_concurrent_migration_moves_once(client, admin):
    g = guest(client)
    c = send(client)[0].json()
    account_a = TestClient(app)
    signup(account_a, 'one@example.test')
    account_b = TestClient(app)
    signup(account_b, 'two@example.test')
    cookie = client.cookies.get('ldt_guest')
    a = TestClient(app)
    b = TestClient(app)
    a.cookies.set('ldt_guest', cookie)
    b.cookies.set('ldt_guest', cookie)

    def login(c, email):
        return c.post(BASE + '/signin', json={'email': email, 'password': 'test-password-123'}, headers=csrf(c))

    with ThreadPoolExecutor(2) as pool:
        r1 = pool.submit(login, a, 'one@example.test')
        r2 = pool.submit(login, b, 'two@example.test')
        assert r1.result().status_code == r2.result().status_code == 200
    with transaction() as conn:
        merged = row(conn, 'ldt_principal', table('ldt_principal').c.id == g['id'])['merged_into']
        assert row(conn, 'ldt_conversation', table('ldt_conversation').c.id == c['id'])['owner_id'] == merged
    views = [a.get(BASE + '/chats').json(), b.get(BASE + '/chats').json()]
    assert sorted(map(len, views)) == [0, 1]


def test_google_email_collision_requires_authenticated_link(client, monkeypatch):
    signup(client)
    original = __import__('open_webui.manual.oauth', fromlist=['google'])

    class Fake:
        async def authorize_redirect(self, request, uri, **kwargs):
            return SimpleNamespace(headers={'location': 'https://accounts.google.com/authorize?state=test-state'})

        async def authorize_access_token(self, request):
            return {
                'userinfo': {
                    'sub': 'verified-provider-subject',
                    'email': 'friend@example.test',
                    'email_verified': True,
                    'name': 'Google Friend',
                }
            }

    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test-secret')
    monkeypatch.setattr(original, 'google', lambda: Fake())
    other = TestClient(app)
    other.post(BASE + '/oauth/google/start', headers=csrf(other))
    result = other.get('/oauth/google/callback?state=test-state', follow_redirects=False)
    assert result.status_code == 303 and 'Email+already+registered' in result.headers['location']
    assert other.get(BASE + '/session').json()['identity'] is None
    # Explicitly start from the authenticated existing local account.
    client.post(BASE + '/oauth/google/start', headers=csrf(client))
    assert client.get('/oauth/google/callback?state=test-state', follow_redirects=False).headers['location'] == '/'
    with transaction() as conn:
        user = (
            conn.execute(select(table('user')).where(table('user').c.email == 'friend@example.test')).mappings().one()
        )
        assert user['oauth']['google']['sub'] == 'verified-provider-subject'
    assert (
        other.get('/oauth/google/callback?state=test-state', follow_redirects=False)
        .headers['location']
        .startswith('/?error=')
    )


def test_title_no_text_no_ai_and_deleted_job_cannot_restore(client, monkeypatch):
    guest(client)
    fid = client.post(BASE + '/files', files={'file': ('p.png', png(), 'image/png')}, headers=csrf(client)).json()['id']
    c = send(client, content='', attachments=[fid])[0].json()
    edit(client, c, 'caption later')
    with transaction() as conn:
        assert not conn.scalar(select(table('ldt_title_job').c.chat_id))
    c = send(client, content='title snapshot')[0].json()

    class Fake:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            client.delete(BASE + '/chats/' + c['id'], headers=csrf(client))
            return SimpleNamespace(
                raise_for_status=lambda: None, json=lambda: {'choices': [{'message': {'content': 'late title'}}]}
            )

    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setattr(jobs.httpx, 'AsyncClient', Fake)
    asyncio.run(jobs.title_once())
    assert client.get(BASE + '/chats/' + c['id']).status_code == 404


def test_temporary_file_cleanup_retry_and_empty_text(client, monkeypatch):
    guest(client)
    assert send(client, content='')[0].status_code == 422
    fid = client.post(BASE + '/files', files={'file': ('p.png', png(), 'image/png')}, headers=csrf(client)).json()['id']
    with transaction() as conn:
        conn.execute(update(table('ldt_upload')).where(table('ldt_upload').c.id == fid).values(expires_at=0))
    from pathlib import Path

    original = Path.unlink
    monkeypatch.setattr(
        Path, 'unlink', lambda *args, **kwargs: (_ for _ in ()).throw(OSError('simulated locked filesystem'))
    )
    jobs.cleanup_once()
    assert (
        client.get(BASE + '/files/' + fid).status_code == 403 or client.get(BASE + '/files/' + fid).status_code == 404
    )
    with transaction() as conn:
        assert row(conn, 'ldt_gc', table('ldt_gc').c.file_id == fid)['attempts'] == 1
        conn.execute(update(table('ldt_gc')).where(table('ldt_gc').c.file_id == fid).values(due_at=0))
    monkeypatch.setattr(Path, 'unlink', original)
    jobs.cleanup_once()
    with transaction() as conn:
        assert not row(conn, 'ldt_gc', table('ldt_gc').c.file_id == fid)


def test_edit_reply_race_and_deleted_sender(client, admin):
    signup(client)
    c = send(client)[0].json()

    def change():
        return edit(client, c, 'concurrent edit')

    def reply():
        return send(admin, c, 'reply')[0]

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(change)
        b = pool.submit(reply)
        changed, answered = a.result(), b.result()
    assert answered.status_code == 200 and changed.status_code in (200, 409)
    final = client.get(BASE + '/chats/' + c['id']).json()
    assert final['messages'][0]['locked']
    assert final['messages'][0]['content'] == ('concurrent edit' if changed.status_code == 200 else 'hello')

    # Chat deletion and a permitted send serialize; neither ordering may resurrect it.
    def remove():
        return admin.delete(BASE + '/chats/' + c['id'], headers=csrf(admin))

    def followup():
        return send(client, final, 'new message')[0]

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(remove)
        b = pool.submit(followup)
        removed, sent = a.result(), b.result()
    assert removed.status_code == 200 and sent.status_code in (200, 404)
    assert client.get(BASE + '/chats/' + c['id']).status_code == 404


def test_manual_title_on_atomic_first_send(client):
    guest(client)
    payload = {
        'key': uuid4().hex,
        'chat_id': uuid4().hex,
        'round_id': None,
        'turn_version': 0,
        'content': 'first text',
        'attachments': [],
        'initial_title': 'Chosen before sending',
    }
    result = client.post(BASE + '/send', json=payload, headers=csrf(client))
    assert result.status_code == 200 and result.json()['title'] == 'Chosen before sending'
    with transaction() as conn:
        assert not conn.scalar(select(table('ldt_title_job').c.chat_id))


def test_guest_migration_failure_rolls_back_and_remains_recoverable(client, monkeypatch):
    from sqlalchemy.exc import OperationalError

    g = guest(client)
    c = send(client)[0].json()

    def fail(*args):
        raise OperationalError('test simulated DB failure', {}, Exception('test'))

    monkeypatch.setattr(security, 'new_session', fail)
    r = client.post(
        BASE + '/signup',
        json={'email': 'recover@example.test', 'name': 'Recover', 'password': 'recovery-test-password'},
        headers=csrf(client),
    )
    assert r.status_code == 503 and 'Reload and retry' in r.json()['detail']
    assert client.get(BASE + '/chats/' + c['id']).json()['owner_id'] == g['id']
    with transaction() as conn:
        assert not conn.scalar(select(table('user').c.id).where(table('user').c.email == 'recover@example.test'))
        assert not row(conn, 'ldt_principal', table('ldt_principal').c.id == g['id'])['disabled']


def test_concurrent_idempotent_send_edits_and_account_delete(client, admin):
    from threading import Barrier

    me = signup(client)
    payload = {
        'key': uuid4().hex,
        'chat_id': uuid4().hex,
        'round_id': None,
        'turn_version': 0,
        'content': 'one',
        'attachments': [],
    }
    headers = csrf(client)

    def duplicate():
        return client.post(BASE + '/send', json=payload, headers=headers)

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(duplicate)
        b = pool.submit(duplicate)
        a, b = a.result(), b.result()
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    c = a.json()
    barrier = Barrier(2)

    def change(value):
        barrier.wait()
        return edit(client, c, value)

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(change, 'A')
        b = pool.submit(change, 'B')
        assert sorted([a.result().status_code, b.result().status_code]) == [200, 409]
    c = send(admin, c)[0].json()

    def remove():
        return admin.delete(BASE + '/users/' + me['id'], headers=csrf(admin))

    def followup():
        return send(client, c, 'account race')[0]

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(remove)
        b = pool.submit(followup)
        a, b = a.result(), b.result()
    assert a.status_code == 200 and b.status_code in (200, 401, 404)
    assert client.get(BASE + '/chats').status_code == 401
    assert admin.get(BASE + '/chats').json() == []


def test_guest_cookie_loss_and_text_only_edit_validation(client, admin):
    original = guest(client, 'Same name')
    c = send(client)[0].json()
    assert edit(client, c, '').status_code == 422
    mid = c['messages'][0]['id']
    invalid = {'key': uuid4().hex, 'text_version': 1, 'content': 'valid', 'attachments': []}
    assert (
        client.patch(BASE + '/chats/' + c['id'] + '/messages/' + mid, json=invalid, headers=csrf(client)).status_code
        == 422
    )
    assert client.delete(BASE + '/chats/' + c['id'] + '/messages/' + mid, headers=csrf(client)).status_code == 405
    assert edit(admin, c, 'not mine').status_code == 409
    client.cookies.clear()
    assert client.get(BASE + '/session').json()['identity'] is None
    replacement = guest(client, 'Same name')
    assert replacement['id'] != original['id']
    assert client.get(BASE + '/chats/' + c['id']).status_code == 403
    assert admin.get(BASE + '/chats/' + c['id']).status_code == 200


def test_title_retry_is_bounded(client, monkeypatch):
    guest(client)
    c = send(client, content='fallback snapshot')[0].json()
    calls = []

    class Failing:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            calls.append(kwargs['json'])
            raise TimeoutError('test timeout')

    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setattr(jobs.httpx, 'AsyncClient', Failing)
    for _ in range(6):
        with transaction() as conn:
            conn.execute(update(table('ldt_title_job')).values(due_at=0))
        asyncio.run(jobs.title_once())
    assert len(calls) == 3
    assert client.get(BASE + '/chats/' + c['id']).json()['title'] == 'fallback snapshot'
    with transaction() as conn:
        assert row(conn, 'ldt_title_job', table('ldt_title_job').c.chat_id == c['id'])['done']
