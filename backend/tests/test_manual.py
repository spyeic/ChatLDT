import asyncio
import io
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from PIL import Image
from conftest import csrf, signup, guest
from open_webui.main import app
from open_webui.manual import security, jobs
from open_webui.manual.database import transaction, table
from open_webui.manual.security import row

BASE = '/api/v1/ldt'


def send(client, chat=None, content='hello', attachments=None, key=None, chat_id=None, target=None):
    payload = {
        'key': key or uuid4().hex,
        'chat_id': chat_id or (chat['id'] if chat else uuid4().hex),
        'round_id': chat['current_round_id'] if chat else None,
        'turn_version': chat['turn_version'] if chat else 0,
        'content': content,
        'attachments': attachments or [],
        'target_user_id': target,
    }
    return client.post(BASE + '/send', json=payload, headers=csrf(client)), payload


def cancel(client, chat):
    return client.post(
        BASE + '/chats/' + chat['id'] + '/cancel',
        json={'key': uuid4().hex, 'round_id': chat['current_round_id'], 'turn_version': chat['turn_version']},
        headers=csrf(client),
    )


def edit(client, chat, content):
    m = chat['messages'][-1]
    return client.patch(
        BASE + '/chats/' + chat['id'] + '/messages/' + m['id'],
        json={'key': uuid4().hex, 'text_version': m['text_version'], 'content': content},
        headers=csrf(client),
    )


def test_no_implicit_guest_or_public_admin(client):
    assert client.get(BASE + '/session').json()['identity'] is None
    assert send(client)[0].status_code == 401
    me = signup(client)
    assert not me['admin']
    with transaction() as conn:
        assert row(conn, 'user', table('user').c.id == me['id'])['role'] == 'user'
        assert not conn.scalar(select(table('ldt_admin').c.user_id))


def test_strict_turns_cancellation_and_old_reply(client, admin):
    guest(client)
    r, _ = send(client)
    assert r.status_code == 200
    c = r.json()
    assert not c['can_send']
    assert send(client, c)[0].status_code == 409
    assert edit(client, c, 'edited').status_code == 200
    stopped = cancel(client, c)
    assert stopped.status_code == 200
    locked = stopped.json()['messages'][-1]
    assert locked['content'] == 'edited' and locked['locked'] and locked['cancelled']
    assert edit(client, stopped.json(), 'again').status_code == 409
    assert send(admin, c)[0].status_code == 409
    next_result, _ = send(client, stopped.json(), 'next')
    assert next_result.status_code == 200
    c2 = next_result.json()
    assert [m['side'] for m in c2['messages']] == ['user', 'user']
    assert send(admin, c)[0].status_code == 409
    reply, _ = send(admin, c2, 'answer')
    assert reply.status_code == 200
    assert reply.json()['can_send'] is False
    assert send(admin, reply.json())[0].status_code == 409
    assert client.get(BASE + '/chats/' + c['id']).json()['can_send']


def test_text_version_separate_from_turn_and_locked_after_reply(client, admin):
    guest(client)
    c = send(client)[0].json()
    modified = edit(client, c, 'new wording')
    assert modified.status_code == 200
    assert modified.json()['turn_version'] == c['turn_version']
    assert edit(client, c, 'stale edit').status_code == 409
    reply, _ = send(admin, c, 'prewritten answer')
    assert reply.status_code == 200
    assert edit(client, modified.json(), 'too late').status_code == 409
    assert edit(client, c, '').status_code == 409


def test_idempotency_and_different_payload(client, admin):
    guest(client)
    r, payload = send(client, key='same-request')
    assert r.status_code == 200
    replay = client.post(BASE + '/send', json=payload, headers=csrf(client))
    assert replay.status_code == 200 and replay.json() == r.json()
    assert len(replay.json()['messages']) == 1
    payload['content'] = 'different'
    assert client.post(BASE + '/send', json=payload, headers=csrf(client)).status_code == 409
    send(admin, r.json())
    payload['content'] = 'hello'
    assert client.post(BASE + '/send', json=payload, headers=csrf(client)).json() == r.json()


def test_admin_first_only_registered_and_independent_chats(client, admin):
    g = guest(client)
    assert send(admin, target=g['id'])[0].status_code == 403
    other = TestClient(app)
    u = signup(other)
    c = send(admin, target=u['id'])[0].json()
    assert len(admin.get(BASE + '/chats').json()) == 1
    assert send(admin, c)[0].status_code == 409
    assert cancel(admin, c).status_code == 409
    assert edit(admin, c, 'edited opener').status_code == 200
    assert send(other, c)[0].status_code == 200
    fresh = send(client)[0]
    assert fresh.status_code == 200


def test_authorization_search_deletion_and_no_resurrection(client, admin):
    guest(client, 'Alice')
    c, payload = send(client, content='needle private')
    c = c.json()
    other = TestClient(app)
    guest(other, 'Alice')
    assert other.get(BASE + '/chats/' + c['id']).status_code == 403
    assert other.get(BASE + '/chats?q=needle').json() == []
    assert admin.get(BASE + '/chats?q=Alice').json()[0]['id'] == c['id']
    assert other.delete(BASE + '/chats/' + c['id'], headers=csrf(other)).status_code == 403
    assert admin.delete(BASE + '/chats/' + c['id'], headers=csrf(admin)).status_code == 200
    assert client.get(BASE + '/chats/' + c['id']).status_code == 404
    assert client.post(BASE + '/send', json=payload, headers=csrf(client)).status_code == 404
    assert admin.get(BASE + '/chats?q=needle').json() == []


def test_expiry_rolling_visit_and_no_push_renewal(client, admin, monkeypatch):
    clock = [1_800_000_000]
    monkeypatch.setattr(security, 'now', lambda: clock[0])
    guest(client)
    c = send(client)[0].json()
    clock[0] += 29 * 86400
    assert client.get(BASE + '/session').json()['identity']
    assert client.post(BASE + '/visit', headers=csrf(client)).status_code == 200
    clock[0] += 29 * 86400
    assert client.get(BASE + '/session').json()['identity']
    clock[0] += 86400
    assert client.get(BASE + '/session').json()['identity'] is None
    assert client.get(BASE + '/chats/' + c['id']).status_code == 401
    # An administrator's permissions outlive the guest; renew the admin test session
    # separately because account sessions share the deterministic test clock.
    with transaction() as conn:
        aid = conn.scalar(select(table('ldt_admin').c.user_id))
        conn.execute(
            update(table('ldt_session'))
            .where(table('ldt_session').c.principal_id == aid)
            .values(expires_at=clock[0] + 86400)
        )
    assert send(admin, c)[0].status_code == 200
    # Verify persisted state and that push does not touch any expiration value.
    with transaction() as conn:
        before = list(conn.execute(select(table('ldt_session').c.expires_at)))
    asyncio.run(__import__('open_webui.socket.main', fromlist=['publish']).publish(c['id']))
    with transaction() as conn:
        assert list(conn.execute(select(table('ldt_session').c.expires_at))) == before


def test_guest_merge_cookie_bound_and_revoked(client, admin):
    g = guest(client)
    c = send(client)[0].json()
    old_cookie = client.cookies.get('ldt_guest')
    u = signup(client)
    assert client.get(BASE + '/chats/' + c['id']).status_code == 200
    assert client.get(BASE + '/chats/' + c['id']).json()['owner_id'] == u['id']
    assert edit(client, c, 'edited after safe migration').status_code == 200
    stale = TestClient(app)
    stale.cookies.set('ldt_guest', old_cookie)
    assert stale.get(BASE + '/chats/' + c['id']).status_code == 401
    assert send(admin, c)[0].status_code == 200
    thief = TestClient(app)
    signup(thief, 'other@example.test')
    assert thief.get(BASE + '/chats/' + c['id']).status_code == 403
    with transaction() as conn:
        assert row(conn, 'ldt_principal', table('ldt_principal').c.id == g['id'])['merged_into'] == u['id']


def test_admin_login_does_not_merge_guest(client, admin):
    g = guest(client)
    c = send(client)[0].json()
    assert (
        client.post(
            BASE + '/signin',
            json={'email': 'duo@example.test', 'password': 'admin-test-password'},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.get(BASE + '/chats/' + c['id']).json()['owner_id'] == g['id']


def test_cancel_reply_race(client, admin):
    guest(client)
    c = send(client)[0].json()
    barrier = threading.Barrier(2)

    def stop():
        barrier.wait()
        return cancel(client, c).status_code

    def reply():
        barrier.wait()
        return send(admin, c)[0].status_code

    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(stop)
        b = pool.submit(reply)
        assert sorted([a.result(), b.result()]) == [200, 409]
    final = client.get(BASE + '/chats/' + c['id']).json()
    assert len(final['messages']) == (1 if final['messages'][0]['cancelled'] else 2)


def test_unread_and_sort_only_successful_send(client, admin):
    guest(client)
    c = send(client)[0].json()
    assert admin.get(BASE + '/chats').json()[0]['unread'] == 1
    stamp = c['last_message_at']
    changed = edit(client, c, 'different').json()
    assert changed['last_message_at'] == stamp
    assert cancel(client, c).json()['last_message_at'] == stamp
    assert admin.get(BASE + '/chats').json()[0]['unread'] == 1
    assert admin.post(BASE + '/chats/' + c['id'] + '/read', json={'seq': 1}, headers=csrf(admin)).status_code == 200
    assert admin.get(BASE + '/chats').json()[0]['unread'] == 0
    c = client.get(BASE + '/chats/' + c['id']).json()
    c = send(client, c)[0].json()
    c = send(admin, c)[0].json()
    assert client.get(BASE + '/chats').json()[0]['unread'] == 1
    assert admin.get(BASE + '/chats').json()[0]['unread'] == 1


def png():
    out = io.BytesIO()
    Image.new('RGB', (32, 32), 'red').save(out, 'PNG')
    return out.getvalue()


def test_attachments_private_immutable_and_gc(client, admin):
    guest(client)
    data = png()
    r = client.post(BASE + '/files', files={'file': ('test.png', data, 'image/png')}, headers=csrf(client))
    assert r.status_code == 200
    fid = r.json()['id']
    assert client.get(BASE + '/files/' + fid).content == data
    other = TestClient(app)
    guest(other)
    assert other.get(BASE + '/files/' + fid).status_code == 403
    assert send(other, attachments=[fid])[0].status_code == 403
    c = send(client, content='', attachments=[fid])[0].json()
    assert c['title'] == '图片对话'
    c = edit(client, c, 'caption').json()
    assert c['messages'][0]['attachments'] == [fid]
    assert edit(client, c, '').status_code == 200
    assert send(client, attachments=[fid])[0].status_code == 403
    assert admin.get(BASE + '/files/' + fid).status_code == 200
    assert client.delete(BASE + '/chats/' + c['id'], headers=csrf(client)).status_code == 200
    assert admin.get(BASE + '/files/' + fid).status_code == 404
    from open_webui.manual.files import directory

    assert (directory() / fid).exists()
    jobs.cleanup_once()
    assert not (directory() / fid).exists()


def test_invalid_image_and_large_compression(client):
    guest(client)
    assert (
        client.post(
            BASE + '/files', files={'file': ('x.png', b'<script>bad</script>', 'image/png')}, headers=csrf(client)
        ).status_code
        == 415
    )
    image = Image.frombytes('RGB', (2000, 2000), os.urandom(12_000_000))
    out = io.BytesIO()
    image.save(out, 'PNG', compress_level=0)
    assert len(out.getvalue()) > 10 * 1024 * 1024
    r = client.post(BASE + '/files', files={'file': ('large.png', out.getvalue(), 'image/png')}, headers=csrf(client))
    assert r.status_code == 200, r.text
    assert len(client.get(BASE + '/files/' + r.json()['id']).content) <= 10 * 1024 * 1024


def test_deleted_account_same_email_different_data(client, admin):
    me = signup(client)
    c = send(client)[0].json()
    assert admin.delete(BASE + '/users/' + me['id'], headers=csrf(admin)).status_code == 200
    assert send(client, c)[0].status_code == 401
    fresh = TestClient(app)
    new = signup(fresh)
    assert new['id'] != me['id']
    assert fresh.get(BASE + '/chats').json() == []
    duo = admin.get(BASE + '/session').json()['identity']
    assert admin.delete(BASE + '/users/' + duo['id'], headers=csrf(admin)).status_code == 403


def test_csrf_and_removed_apis(client):
    guest(client)
    assert (
        client.post(BASE + '/send', json={}).status_code == 403
        or client.post(BASE + '/send', json={}).status_code == 422
    )
    assert client.post(BASE + '/profile', json={}, headers={'Origin': 'https://attacker.example'}).status_code in (
        403,
        405,
    )
    for path in [
        '/api/chat/completions',
        '/api/v1/tasks/title/completions',
        '/api/v1/retrieval/query/doc',
        '/api/v1/images/generations',
        '/ollama/api/chat',
        '/openai/chat/completions',
        '/api/v1/chats/new',
        '/api/v1/chats/1/share',
    ]:
        assert client.post(path, json={}).status_code == 404, path
    assert client.get(BASE + '/session').json()['google'] is False
    assert client.post(BASE + '/oauth/google/start', headers=csrf(client)).status_code == 404


def test_title_snapshot_only_and_manual_priority(client, admin, monkeypatch):
    guest(client)
    c = send(client, content='first snapshot')[0].json()
    edit(client, c, 'changed later')
    cancel(client, c)
    captured = []

    class Fake:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            captured.append(kwargs['json'])
            client.patch(BASE + '/chats/' + c['id'] + '/title', json={'title': 'Manual'}, headers=csrf(client))
            return SimpleNamespace(
                raise_for_status=lambda: None, json=lambda: {'choices': [{'message': {'content': 'Automatic'}}]}
            )

    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    monkeypatch.setattr(jobs.httpx, 'AsyncClient', Fake)
    asyncio.run(jobs.title_once())
    assert captured[0]['messages'][1] == {'role': 'user', 'content': 'first snapshot'}
    assert client.get(BASE + '/chats/' + c['id']).json()['title'] == 'Manual'
    assert len(captured[0]['messages']) == 2
