"""Open WebUI Socket.IO transport, reduced to authenticated invalidations."""

import asyncio
import logging
from functools import wraps
from http.cookies import SimpleCookie
from types import SimpleNamespace
import socketio
from open_webui.manual.database import transaction, table
from open_webui.manual.security import principal, csrf_value, credential
from sqlalchemy import select

log = logging.getLogger(__name__)


def best_effort(function):
    @wraps(function)
    async def wrapped(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except Exception:
            # The database commit already succeeded. Delivery failure must not
            # turn it into an apparent failed write or lose a login Set-Cookie.
            log.exception('Socket invalidation delivery failed; API/reconnect remains authoritative')

    return wrapped


sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[], logger=False, engineio_logger=False)
app = socketio.ASGIApp(sio, socketio_path='/ws/socket.io')


def request_from_environ(environ):
    parsed = SimpleCookie()
    parsed.load(environ.get('HTTP_COOKIE', ''))
    return SimpleNamespace(cookies={k: v.value for k, v in parsed.items()})


@sio.event
async def connect(sid, environ, auth):
    request = request_from_environ(environ)
    if not auth or auth.get('csrf') != csrf_value(credential(request)):
        return False
    try:
        with transaction() as conn:
            actor = principal(conn, request)
        await sio.save_session(sid, {'request': request, 'principal_id': actor['id']})
        await sio.enter_room(sid, f'identity:{actor["id"]}')
    except Exception:
        return False


@best_effort
async def disconnect_identity(principal_id):
    participants = list(sio.manager.get_participants('/', f'identity:{principal_id}'))
    for sid, _ in participants:
        await sio.disconnect(sid)


@best_effort
async def publish(chat_id, event='changed', message_id=None):
    # No content in socket payloads; even notifications are restricted to owner/Duo.
    with transaction() as conn:
        c = (
            conn.execute(select(table('ldt_conversation')).where(table('ldt_conversation').c.id == chat_id))
            .mappings()
            .first()
        )
        admin = conn.execute(select(table('ldt_admin'))).mappings().first()
        if not c:
            return
        targets = {c['owner_id']}
        if admin:
            targets.add(admin['user_id'])
        data = {'chat_id': chat_id, 'revision': c['revision'], 'event': event, 'message_id': message_id}
    for target in targets:
        # A CLI reset can revoke credentials in a different process. Revalidate
        # every recipient before any notification, rather than trusting rooms.
        for sid, _ in list(sio.manager.get_participants('/', f'identity:{target}')):
            try:
                session = await sio.get_session(sid)
                with transaction() as conn:
                    actor = principal(conn, session['request'])
                if actor['id'] != target:
                    raise ValueError('Identity changed')
            except Exception:
                await sio.disconnect(sid)
            else:
                await sio.emit('ldt:changed', data, to=sid)


async def revalidate_connections():
    while True:
        await asyncio.sleep(30)
        for sid in list(sio.manager.rooms.get('/', {}).get(None, {})):
            try:
                session = await sio.get_session(sid)
                with transaction() as conn:
                    principal(conn, session['request'])
            except Exception:
                await sio.disconnect(sid)


@best_effort
async def notify_ownership(principal_id):
    with transaction() as conn:
        c = table('ldt_conversation')
        ids = list(conn.scalars(select(c.c.id).where(c.c.owner_id == principal_id, c.c.deleted == False)))
    for cid in ids:
        await publish(cid, 'identity')
