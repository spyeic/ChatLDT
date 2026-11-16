"""Persistent cookie sessions over the existing auth/user tables."""

import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path
from fastapi import HTTPException
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
import bcrypt
from sqlalchemy import select, update, insert
from open_webui.manual.database import table

IDLE_SECONDS = 30 * 86400
COOKIE_ACCOUNT = 'ldt_account'
COOKIE_GUEST = 'ldt_guest'
COOKIE_VISITOR = 'ldt_visitor'


def now():
    return int(time.time())


def uid():
    return secrets.token_hex(16)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def secret():
    value = os.getenv('WEBUI_SECRET_KEY')
    if value:
        return value
    from open_webui.env import DATA_DIR

    path = Path(DATA_DIR) / '.webui_secret_key'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
    return path.read_text().strip()


def csrf_value(raw):
    return hmac.new(secret().encode(), raw.encode(), hashlib.sha256).hexdigest()


def credential(request):
    return (
        request.cookies.get(COOKIE_ACCOUNT)
        or request.cookies.get(COOKIE_GUEST)
        or request.cookies.get(COOKIE_VISITOR)
        or ''
    )


def allowed_origins():
    # PUBLIC_ORIGIN is the canonical URL, not a single-host access restriction.
    canonical = os.getenv('PUBLIC_ORIGIN', 'http://127.0.0.1:5173').rstrip('/')
    aliases = os.getenv('ALLOWED_ORIGINS', '').split(',')
    return {canonical, *(value.strip().rstrip('/') for value in aliases if value.strip())}


def check_csrf(request):
    raw = credential(request)
    token = request.headers.get('x-ldt-csrf', '')
    origin = request.headers.get('origin')
    if origin and origin not in allowed_origins():
        raise HTTPException(403, 'Invalid request origin.')
    if not raw or not hmac.compare_digest(token, csrf_value(raw)):
        raise HTTPException(403, 'Reload the page to refresh the security token')


def cookie(response, name, value, age=IDLE_SECONDS):
    secure = os.getenv('ENV', 'dev') == 'prod'
    response.set_cookie(name, value, max_age=age, httponly=True, secure=secure, samesite='lax', path='/')


def row(conn, name, *conditions):
    return conn.execute(select(table(name)).where(*conditions)).mappings().first()


def principal(conn, request, required=True):
    for name in (COOKIE_ACCOUNT, COOKIE_GUEST):
        raw = request.cookies.get(name)
        if not raw:
            continue
        sessions = table('ldt_session')
        session = row(conn, 'ldt_session', sessions.c.token_hash == digest(raw))
        if not session or session['revoked'] or session['expires_at'] <= now():
            continue
        p = row(conn, 'ldt_principal', table('ldt_principal').c.id == session['principal_id'])
        if not p or p['disabled']:
            continue
        p = dict(p)
        if p['kind'] == 'user':
            auth = row(conn, 'auth', table('auth').c.id == p['id'])
            user = row(conn, 'user', table('user').c.id == p['id'])
            if not auth or not auth['active'] or not user:
                continue
            p['name'] = user['name']
            p['email'] = user['email']
            p['avatar'] = user['profile_image_url'] or '/user.png'
            p['local_password'] = bool(auth['password'])
            admin = row(conn, 'ldt_admin', table('ldt_admin').c.singleton == 1)
            p['admin'] = bool(admin and admin['user_id'] == p['id'] and user['role'] == 'admin')
            if p['admin']:
                p['name'] = 'admin'
        else:
            p.update(admin=False, avatar='/user.png', local_password=False)
        p['session_hash'] = session['token_hash']
        return p
    if required:
        raise HTTPException(401, 'Session expired; sign in or choose a new guest nickname')
    return None


def public(p):
    if not p:
        return None
    return {
        k: p[k] for k in ('id', 'kind', 'name', 'preferences', 'admin', 'avatar', 'local_password', 'email') if k in p
    }


def new_session(conn, principal_id):
    raw = secrets.token_urlsafe(48)
    conn.execute(
        insert(table('ldt_session')).values(
            token_hash=digest(raw), principal_id=principal_id, expires_at=now() + IDLE_SECONDS, revoked=False
        )
    )
    return raw


def ensure_user_principal(conn, user):
    p = table('ldt_principal')
    if not row(conn, 'ldt_principal', p.c.id == user['id']):
        conn.execute(
            insert(p).values(
                id=user['id'], kind='user', name=user['name'], preferences={}, disabled=False, created_at=now()
            )
        )


def create_user(conn, email, password, name, *, admin=False, oauth=None):
    email = email.strip().lower()
    if len(email) > 254 or '@' not in email or not email.split('@')[-1].count('.'):
        raise HTTPException(422, 'Enter a valid email address')
    if not name.strip() or len(name.strip()) > 80:
        raise HTTPException(422, 'Nickname must be 1–80 characters')
    if row(conn, 'user', table('user').c.email == email):
        raise HTTPException(409, 'Email already registered. Sign in, then link Google from Settings.')
    user_id = uid()
    stamp = uid()
    conn.execute(
        insert(table('user')).values(
            id=user_id,
            email=email,
            role='admin' if admin else 'user',
            name='admin' if admin else name.strip(),
            profile_image_url='/user.png',
            settings={},
            oauth=oauth,
            created_at=now(),
            updated_at=now(),
            last_active_at=now(),
        )
    )
    conn.execute(
        insert(table('auth')).values(id=user_id, email=email, password=password, active=True, session_stamp=stamp)
    )
    user = row(conn, 'user', table('user').c.id == user_id)
    ensure_user_principal(conn, user)
    return dict(user)


def hash_password(password):
    if len(password) < 12 or len(password.encode()) > 1024:
        raise HTTPException(422, 'Password must contain at least 12 characters and at most 1024 bytes')
    # Same Argon2id algorithm/encoded hashes supported by Open WebUI.
    return PasswordHasher().hash(password)


def verify_password(password, hashed):
    if not hashed:
        return False
    if hashed.startswith('$argon2'):
        try:
            return PasswordHasher().verify(hashed, password)
        except (VerificationError, InvalidHashError):
            return False
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def merge_guest(conn, request, user):
    admin = row(conn, 'ldt_admin', table('ldt_admin').c.user_id == user['id'])
    if admin:
        return None
    raw = request.cookies.get(COOKIE_GUEST)
    if not raw:
        return None
    session = row(conn, 'ldt_session', table('ldt_session').c.token_hash == digest(raw))
    if not session or session['revoked'] or session['expires_at'] <= now():
        return None
    guests = table('ldt_principal')
    guest = row(conn, 'ldt_principal', guests.c.id == session['principal_id'])
    if not guest or guest['kind'] != 'guest' or guest['disabled'] or guest['merged_into']:
        return None
    target = row(conn, 'ldt_principal', guests.c.id == user['id'])
    if target and not target['preferences'] and guest['preferences']:
        conn.execute(update(guests).where(guests.c.id == user['id']).values(preferences=guest['preferences']))
    gid = guest['id']
    for name, column in [('ldt_conversation', 'owner_id'), ('ldt_upload', 'owner_id')]:
        t = table(name)
        conn.execute(update(t).where(t.c[column] == gid).values({column: user['id']}))
    chats = table('chat')
    conn.execute(update(chats).where(chats.c.user_id == gid).values(user_id=user['id']))
    files = table('file')
    conn.execute(update(files).where(files.c.user_id == gid).values(user_id=user['id']))
    conn.execute(update(guests).where(guests.c.id == gid).values(disabled=True, merged_into=user['id']))
    sessions = table('ldt_session')
    conn.execute(update(sessions).where(sessions.c.principal_id == gid).values(revoked=True))
    return gid
