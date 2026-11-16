"""Development URLs match Vite's loopback URL; origin and CSRF stay strict."""

import pytest
from conftest import csrf

BASE = '/api/v1/ldt'
LOGIN = {'email': 'duo@example.test', 'password': 'admin-test-password'}


@pytest.fixture(autouse=True)
def isolated_origins(monkeypatch):
    monkeypatch.delenv('ALLOWED_ORIGINS', raising=False)


def test_default_vite_origin_can_sign_in(admin, monkeypatch):
    monkeypatch.delenv('PUBLIC_ORIGIN', raising=False)
    headers = {**csrf(admin), 'Origin': 'http://127.0.0.1:5173'}
    response = admin.post(BASE + '/signin', json=LOGIN, headers=headers)
    assert response.status_code == 200
    assert admin.get(BASE + '/session').json()['identity']['admin']


@pytest.mark.parametrize(
    'origin',
    [
        'http://localhost:5173',
        'http://127.0.0.1:5174',
        'https://attacker.example',
        'null',
    ],
)
def test_other_origins_are_rejected(admin, monkeypatch, origin):
    monkeypatch.delenv('PUBLIC_ORIGIN', raising=False)
    response = admin.post(BASE + '/signin', json=LOGIN, headers={**csrf(admin), 'Origin': origin})
    assert response.status_code == 403
    assert response.json()['detail'] == 'Invalid request origin.'


@pytest.mark.parametrize('public_origin', ['https://chat.example.test', 'https://eurse.me'])
def test_production_requires_configured_origin_and_csrf(admin, monkeypatch, public_origin):
    monkeypatch.setenv('ENV', 'prod')
    monkeypatch.setenv('PUBLIC_ORIGIN', public_origin)
    headers = csrf(admin)
    for origin in ['http://127.0.0.1:5173', 'http://localhost:5173', 'https://attacker.example']:
        assert admin.post(BASE + '/signin', json=LOGIN, headers={**headers, 'Origin': origin}).status_code == 403
    assert admin.post(BASE + '/signin', json=LOGIN, headers={'Origin': public_origin}).status_code == 403
    response = admin.post(BASE + '/signin', json=LOGIN, headers={**headers, 'Origin': public_origin})
    assert response.status_code == 200
    assert 'secure' in response.headers['set-cookie'].lower()
    assert 'httponly' in response.headers['set-cookie'].lower()


@pytest.mark.parametrize('origin', ['https://eurse.me', 'https://chat.eurse.me'])
def test_multiple_trusted_domains_can_sign_in(admin, monkeypatch, origin):
    # Even an old PUBLIC_ORIGIN in the service environment must not reject chat.
    monkeypatch.setenv('PUBLIC_ORIGIN', 'https://eurse.me')
    monkeypatch.setenv('ALLOWED_ORIGINS', ' https://chat.eurse.me/, https://eurse.me ')
    headers = {**csrf(admin), 'Origin': origin}
    response = admin.post(BASE + '/signin', json=LOGIN, headers=headers)
    assert response.status_code == 200


def test_trusted_domain_does_not_bypass_csrf(admin, monkeypatch):
    monkeypatch.setenv('ALLOWED_ORIGINS', 'https://chat.eurse.me')
    response = admin.post(BASE + '/signin', json=LOGIN, headers={'Origin': 'https://chat.eurse.me'})
    assert response.status_code == 403
    assert 'security token' in response.json()['detail']


@pytest.mark.parametrize(
    'origin',
    [
        'https://chat.eurse.me.attacker.example',
        'http://chat.eurse.me',
        'https://chat.eurse.me:444',
        'null',
    ],
)
def test_domain_alias_is_an_exact_origin(admin, monkeypatch, origin):
    monkeypatch.setenv('PUBLIC_ORIGIN', 'https://chat.eurse.me')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'https://eurse.me')
    response = admin.post(BASE + '/signin', json=LOGIN, headers={**csrf(admin), 'Origin': origin})
    assert response.status_code == 403
