"""ChatLDT API. All mutation authorization is rechecked inside the write transaction."""

import asyncio
import base64
import io
import os
import secrets
from collections import defaultdict, deque
from typing import Literal
from fastapi import APIRouter, Request, Response, HTTPException, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, insert, update, delete
from PIL import Image
from open_webui.manual.database import transaction, table
from open_webui.manual import security as auth, conversations as chats
from open_webui.manual.files import store, read, MAX_INPUT, normalize
from open_webui.socket.main import publish, disconnect_identity, notify_ownership

router = APIRouter(prefix='/api/v1/ldt')
_limits = defaultdict(deque)


def rate(request, action, limit=60, seconds=60):
    # One application worker; proxy forwarding must only trust the local proxy.
    key = (request.client.host if request.client else 'local', action)
    q = _limits[key]
    cutoff = auth.now() - seconds
    while q and q[0] <= cutoff:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, 'Too many requests; try again shortly')
    q.append(auth.now())
    if len(_limits) > 10000:
        for k in list(_limits):
            if not _limits[k] or _limits[k][-1] < auth.now() - 3600:
                del _limits[k]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Nickname(Strict):
    name: str = Field(min_length=1, max_length=80)


class Login(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class Signup(Login):
    name: str = Field(min_length=1, max_length=80)


class Send(Strict):
    key: str = Field(min_length=1, max_length=128)
    chat_id: str = Field(pattern=r'^[a-f0-9-]{32,36}$')
    round_id: str | None = None
    turn_version: int = Field(ge=0)
    content: str = Field(max_length=chats.MAX_TEXT)
    attachments: list[str] = Field(default_factory=list, max_length=chats.MAX_ATTACHMENTS)
    target_user_id: str | None = None
    initial_title: str | None = Field(default=None, min_length=1, max_length=80)


class Cancel(Strict):
    key: str = Field(min_length=1, max_length=128)
    round_id: str
    turn_version: int = Field(ge=0)


class Edit(Strict):
    key: str = Field(min_length=1, max_length=128)
    text_version: int = Field(ge=1)
    content: str = Field(max_length=chats.MAX_TEXT)


class Rename(Strict):
    title: str = Field(min_length=1, max_length=80)


class Read(Strict):
    seq: int = Field(ge=0)


class Preferences(Strict):
    name: str = Field(min_length=1, max_length=80)
    language: Literal['en-US', 'zh-CN']
    theme: Literal['light', 'dark', 'system']


class Password(Strict):
    old_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


@router.get('/session')
def session(request: Request, response: Response):
    with transaction() as conn:
        actor = auth.principal(conn, request, required=False)
    raw = auth.credential(request)
    if not raw:
        raw = secrets.token_urlsafe(48)
        auth.cookie(response, auth.COOKIE_VISITOR, raw)
    response.headers['Cache-Control'] = 'no-store'
    with transaction() as conn:
        p = table('ldt_principal')
        merged = list(conn.scalars(select(p.c.id).where(p.c.merged_into == actor['id']))) if actor else []
    return {
        'identity': auth.public(actor),
        'merged_guest_ids': merged,
        'csrf': auth.csrf_value(raw),
        'google': bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET')),
    }


@router.post('/visit')
def visit(request: Request, response: Response):
    auth.check_csrf(request)
    with transaction() as conn:
        actor = auth.principal(conn, request)
        conn.execute(
            update(table('ldt_session'))
            .where(table('ldt_session').c.token_hash == actor['session_hash'])
            .values(expires_at=auth.now() + auth.IDLE_SECONDS)
        )
    name = auth.COOKIE_ACCOUNT if actor['kind'] == 'user' else auth.COOKIE_GUEST
    auth.cookie(response, name, request.cookies[name])
    return {'ok': True}


@router.post('/guest')
def guest(form: Nickname, request: Request, response: Response):
    auth.check_csrf(request)
    rate(request, 'guest', 10, 3600)
    name = form.name.strip()
    if not name:
        raise HTTPException(422, 'Enter a nickname')
    with transaction() as conn:
        existing = auth.principal(conn, request, required=False)
        if existing:
            raise HTTPException(409, 'An identity is already active')
        pid = auth.uid()
        conn.execute(
            insert(table('ldt_principal')).values(
                id=pid, kind='guest', name=name, preferences={}, disabled=False, created_at=auth.now()
            )
        )
        raw = auth.new_session(conn, pid)
    auth.cookie(response, auth.COOKIE_GUEST, raw)
    response.delete_cookie(auth.COOKIE_ACCOUNT, path='/')
    return {'csrf': auth.csrf_value(raw)}


async def finish_login(request, response, form, signup=False):
    auth.check_csrf(request)
    rate(request, 'signup' if signup else 'login', 5 if signup else 12, 3600 if signup else 60)
    password_hash = await asyncio.to_thread(auth.hash_password, form.password) if signup else None
    with transaction() as conn:
        if signup:
            user = auth.create_user(conn, form.email, password_hash, form.name)
        else:
            t = table('auth')
            account = auth.row(conn, 'auth', t.c.email == form.email.strip().lower())
            if not account or not account['active'] or not auth.verify_password(form.password, account['password']):
                raise HTTPException(401, 'Email or password is incorrect')
            if account.get('mfa') and account['mfa'].get('secret'):
                raise HTTPException(
                    409, 'This existing MFA account requires a reviewed migration; configured MFA is not bypassed.'
                )
            user = auth.row(conn, 'user', table('user').c.id == account['id'])
            if not user:
                raise HTTPException(401, 'Account no longer exists')
            auth.ensure_user_principal(conn, user)
            p = auth.row(conn, 'ldt_principal', table('ldt_principal').c.id == user['id'])
            if p['disabled']:
                raise HTTPException(401, 'Account no longer exists')
        merged = auth.merge_guest(conn, request, user)
        raw = auth.new_session(conn, user['id'])
    auth.cookie(response, auth.COOKIE_ACCOUNT, raw)
    if merged:
        response.delete_cookie(auth.COOKIE_GUEST, path='/')
        await disconnect_identity(merged)
        await notify_ownership(user['id'])
    return {'csrf': auth.csrf_value(raw), 'merged_guest': merged, 'user_id': user['id']}


@router.post('/signup')
async def signup(form: Signup, request: Request, response: Response):
    return await finish_login(request, response, form, True)


@router.post('/signin')
async def signin(form: Login, request: Request, response: Response):
    return await finish_login(request, response, form)


@router.post('/signout')
async def signout(request: Request, response: Response):
    auth.check_csrf(request)
    with transaction() as conn:
        actor = auth.principal(conn, request)
        t = table('ldt_session')
        conn.execute(update(t).where(t.c.token_hash == actor['session_hash']).values(revoked=True))
    response.delete_cookie(auth.COOKIE_ACCOUNT if actor['kind'] == 'user' else auth.COOKIE_GUEST, path='/')
    await disconnect_identity(actor['id'])
    return {'ok': True}


@router.patch('/profile')
async def profile(form: Preferences, request: Request):
    auth.check_csrf(request)
    if not form.name.strip():
        raise HTTPException(422, 'Enter a nickname')
    with transaction() as conn:
        actor = auth.principal(conn, request)
        name = 'admin' if actor['admin'] else form.name.strip()
        conn.execute(
            update(table('ldt_principal'))
            .where(table('ldt_principal').c.id == actor['id'])
            .values(name=name, preferences={'language': form.language, 'theme': form.theme})
        )
        if actor['kind'] == 'user':
            conn.execute(update(table('user')).where(table('user').c.id == actor['id']).values(name=name))
    return {'ok': True}


@router.post('/password')
async def password(form: Password, request: Request, response: Response):
    auth.check_csrf(request)
    hashed = await asyncio.to_thread(auth.hash_password, form.new_password)
    with transaction() as conn:
        actor = auth.principal(conn, request)
        a = auth.row(conn, 'auth', table('auth').c.id == actor['id'])
        if not actor['local_password'] or not auth.verify_password(form.old_password, a['password']):
            raise HTTPException(403, 'Current local password is required')
        conn.execute(
            update(table('auth'))
            .where(table('auth').c.id == actor['id'])
            .values(password=hashed, session_stamp=auth.uid())
        )
        conn.execute(
            update(table('ldt_session')).where(table('ldt_session').c.principal_id == actor['id']).values(revoked=True)
        )
        raw = auth.new_session(conn, actor['id'])
    auth.cookie(response, auth.COOKIE_ACCOUNT, raw)
    await disconnect_identity(actor['id'])
    return {'csrf': auth.csrf_value(raw)}


@router.post('/avatar')
async def avatar(request: Request, file: UploadFile = File(...)):
    auth.check_csrf(request)
    data = await file.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(413, 'Avatar source must be at most 2 MB')
    content, _ = await asyncio.to_thread(normalize, data)
    image = Image.open(io.BytesIO(content)).convert('RGB')
    image.thumbnail((256, 256))
    out = io.BytesIO()
    image.save(out, 'JPEG', quality=85)
    url = 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()
    with transaction() as conn:
        actor = auth.principal(conn, request)
        if actor['kind'] != 'user':
            raise HTTPException(403, 'Register to set an avatar')
        conn.execute(update(table('user')).where(table('user').c.id == actor['id']).values(profile_image_url=url))
    return {'ok': True}


@router.get('/chats')
def list_chats(request: Request, q: str = ''):
    with transaction() as conn:
        actor = auth.principal(conn, request)
        return chats.list_chats(conn, actor, q)


@router.get('/chats/{chat_id}')
def get_chat(chat_id: str, request: Request):
    with transaction() as conn:
        return chats.snapshot(conn, auth.principal(conn, request), chat_id)


@router.post('/send')
async def send(form: Send, request: Request):
    auth.check_csrf(request)
    rate(request, 'send')
    with transaction() as conn:
        result = chats.send(conn, auth.principal(conn, request), form.model_dump())
    await publish(result['id'], 'message', result['messages'][-1]['id'])
    return result


@router.post('/chats/{chat_id}/cancel')
async def cancel(chat_id: str, form: Cancel, request: Request):
    auth.check_csrf(request)
    with transaction() as conn:
        result = chats.cancel(conn, auth.principal(conn, request), chat_id, form.model_dump())
    await publish(chat_id, 'cancel')
    return result


@router.patch('/chats/{chat_id}/messages/{message_id}')
async def edit(chat_id: str, message_id: str, form: Edit, request: Request):
    auth.check_csrf(request)
    with transaction() as conn:
        result = chats.edit(conn, auth.principal(conn, request), chat_id, message_id, form.model_dump())
    await publish(chat_id, 'edit')
    return result


@router.patch('/chats/{chat_id}/title')
async def rename(chat_id: str, form: Rename, request: Request):
    auth.check_csrf(request)
    if not form.title.strip():
        raise HTTPException(422, 'Enter a title')
    with transaction() as conn:
        actor = auth.principal(conn, request)
        c = chats.require_chat(conn, actor, chat_id)
        conn.execute(update(table('chat')).where(table('chat').c.id == chat_id).values(title=form.title.strip()))
        chats.bump(conn, c, manual_title=True)
    await publish(chat_id, 'title')
    return {'ok': True}


@router.post('/chats/{chat_id}/read')
async def mark_read(chat_id: str, form: Read, request: Request):
    auth.check_csrf(request)
    changed = False
    with transaction() as conn:
        actor = auth.principal(conn, request)
        c = chats.require_chat(conn, actor, chat_id)
        field = 'admin_read' if actor['admin'] else 'user_read'
        seq = max(c[field], min(form.seq, c['seq']))
        if seq != c[field]:
            chats.bump(conn, c, **{field: seq})
            changed = True
    if changed:
        await publish(chat_id, 'read')
    return {'ok': True}


@router.delete('/chats/{chat_id}')
async def remove_chat(chat_id: str, request: Request):
    auth.check_csrf(request)
    with transaction() as conn:
        chats.remove_chat(conn, auth.principal(conn, request), chat_id)
    await publish(chat_id, 'deleted')
    return {'ok': True}


@router.post('/files')
async def upload(request: Request, file: UploadFile = File(...)):
    auth.check_csrf(request)
    rate(request, 'upload', 20)
    # Verify before expensive processing, and again in the write transaction.
    with transaction() as conn:
        auth.principal(conn, request)
    data = await file.read(MAX_INPUT + 1)
    if len(data) > MAX_INPUT:
        raise HTTPException(413, 'Original image exceeds 40 MB')
    prepared = await asyncio.to_thread(normalize, data)
    with transaction() as conn:
        result = store(conn, auth.principal(conn, request), data, prepared=prepared)
    return result


@router.get('/files/{file_id}')
def image(file_id: str, request: Request):
    with transaction() as conn:
        content, mime = read(conn, auth.principal(conn, request), file_id)
    return Response(
        content,
        media_type=mime,
        headers={
            'Cache-Control': 'private, no-store',
            'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': 'inline',
        },
    )


@router.get('/users')
def users(request: Request):
    with transaction() as conn:
        actor = auth.principal(conn, request)
        if not actor['admin']:
            raise HTTPException(403, 'Administrator only')
        t = table('ldt_principal')
        return [
            dict(r)
            for r in conn.execute(
                select(t.c.id, t.c.name, t.c.kind).where(t.c.disabled == False, t.c.id != actor['id'])
            ).mappings()
        ]


@router.delete('/users/{user_id}')
async def remove_user(user_id: str, request: Request):
    auth.check_csrf(request)
    with transaction() as conn:
        actor = auth.principal(conn, request)
        if not actor['admin']:
            raise HTTPException(403, 'Administrator only')
        if auth.row(conn, 'ldt_admin', table('ldt_admin').c.user_id == user_id):
            raise HTTPException(403, 'The only administrator cannot be deleted')
        p = auth.row(conn, 'ldt_principal', table('ldt_principal').c.id == user_id)
        if not p or p['disabled']:
            raise HTTPException(404, 'Identity no longer exists')
        cs = table('ldt_conversation')
        ids = list(conn.scalars(select(cs.c.id).where(cs.c.owner_id == user_id, cs.c.deleted == False)))
        for cid in ids:
            chats.remove_chat(conn, actor, cid)
        chats.revoke_files(conn, [table('ldt_upload').c.owner_id == user_id])
        conn.execute(
            update(table('ldt_session')).where(table('ldt_session').c.principal_id == user_id).values(revoked=True)
        )
        conn.execute(
            update(table('ldt_principal'))
            .where((table('ldt_principal').c.id == user_id) | (table('ldt_principal').c.merged_into == user_id))
            .values(disabled=True, name='Deleted', preferences={})
        )
        if p['kind'] == 'user':
            conn.execute(delete(table('auth')).where(table('auth').c.id == user_id))
            conn.execute(delete(table('user')).where(table('user').c.id == user_id))
    await disconnect_identity(user_id)
    for cid in ids:
        await publish(cid, 'deleted')
    return {'ok': True}
