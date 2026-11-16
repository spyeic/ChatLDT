"""Administrator display is a role projection, never a nickname-based grant."""

from conftest import csrf, signup
from open_webui.manual import setup
from open_webui.manual.database import table, transaction
from sqlalchemy import select, update

BASE = '/api/v1/ldt'


def test_existing_admin_display_preserves_credentials_and_stored_name(admin):
    identity = admin.get(BASE + '/session').json()['identity']
    with transaction() as conn:
        conn.execute(update(table('user')).where(table('user').c.id == identity['id']).values(name='Duo'))
        conn.execute(
            update(table('ldt_principal')).where(table('ldt_principal').c.id == identity['id']).values(name='Duo')
        )
        account = dict(conn.execute(select(table('auth')).where(table('auth').c.id == identity['id'])).mappings().one())
    for _ in range(2):
        shown = admin.get(BASE + '/session').json()['identity']
        assert shown['name'] == 'admin' and shown['admin'] is True and shown['id'] == identity['id']
    admin.post(BASE + '/signout', headers=csrf(admin)).raise_for_status()
    admin.post(
        BASE + '/signin', json={'email': account['email'], 'password': 'admin-test-password'}, headers=csrf(admin)
    ).raise_for_status()
    assert admin.get(BASE + '/session').json()['identity']['name'] == 'admin'
    with transaction() as conn:
        assert (
            dict(conn.execute(select(table('auth')).where(table('auth').c.id == identity['id'])).mappings().one())
            == account
        )
        assert conn.scalar(select(table('user').c.name).where(table('user').c.id == identity['id'])) == 'Duo'


def test_regular_nickname_does_not_grant_admin(client, admin):
    user = signup(client, name='Duo')
    assert user['name'] == 'Duo' and user['admin'] is False
    result = client.patch(
        BASE + '/profile', headers=csrf(client), json={'name': 'admin', 'language': 'en-US', 'theme': 'dark'}
    )
    assert result.status_code == 200
    shown = client.get(BASE + '/session').json()['identity']
    assert shown['name'] == 'admin' and shown['admin'] is False
    assert client.get(BASE + '/users').status_code == 403
    result = admin.patch(
        BASE + '/profile', headers=csrf(admin), json={'name': 'Anything', 'language': 'zh-CN', 'theme': 'light'}
    )
    assert result.status_code == 200
    shown = admin.get(BASE + '/session').json()['identity']
    assert shown['name'] == 'admin' and shown['preferences']['language'] == 'zh-CN'


def test_setup_new_admin_defaults_to_admin_without_rerun_password_change(client, monkeypatch):
    answers = iter(['administrator@example.test', 'test-setup-password', 'test-setup-password'])
    monkeypatch.setattr(setup.getpass, 'getpass', lambda _prompt: next(answers))
    setup.setup()
    with transaction() as conn:
        user = conn.execute(select(table('user'))).mappings().one()
        assert user['name'] == 'admin' and user['role'] == 'admin'
        password = conn.scalar(select(table('auth').c.password))
    setup.setup()
    with transaction() as conn:
        assert conn.scalar(select(table('auth').c.password)) == password
