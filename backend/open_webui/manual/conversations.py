"""The only writer of manual chats. Call inside database.transaction()."""

import json
import time
from fastapi import HTTPException
from sqlalchemy import select, insert, update, delete, func
from open_webui.manual.database import table
from open_webui.manual.security import row, uid, now, digest

MAX_TEXT = 32000
MAX_ATTACHMENTS = 8


def require_chat(conn, actor, chat_id):
    c = row(conn, 'ldt_conversation', table('ldt_conversation').c.id == chat_id)
    if not c or c['deleted']:
        raise HTTPException(404, 'Conversation no longer exists')
    if not actor['admin'] and c['owner_id'] != actor['id']:
        raise HTTPException(403, 'Conversation access denied')
    return dict(c)


def side(actor):
    return 'admin' if actor['admin'] else 'user'


def fingerprint(payload):
    return digest(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')))


def replay(conn, actor, key, payload):
    if not key or len(key) > 128:
        raise HTTPException(422, 'A request idempotency key is required (max 128 characters)')
    t = table('ldt_request')
    prior = row(conn, 'ldt_request', t.c.actor_id == actor['id'], t.c.key == key)
    if prior:
        if prior['fingerprint'] != fingerprint(payload):
            raise HTTPException(409, 'Idempotency key was already used with a different payload')
        require_chat(conn, actor, prior['chat_id'])
        return prior['result']
    return None


def remember(conn, actor, key, payload, chat_id, result):
    conn.execute(
        insert(table('ldt_request')).values(
            actor_id=actor['id'], key=key, fingerprint=fingerprint(payload), chat_id=chat_id, result=result
        )
    )
    return result


def messages(conn, chat_id):
    t = table('ldt_message')
    return [dict(r) for r in conn.execute(select(t).where(t.c.chat_id == chat_id).order_by(t.c.seq)).mappings()]


def unread(conn, c, actor):
    m = table('ldt_message')
    read = c['admin_read'] if actor['admin'] else c['user_read']
    return conn.scalar(
        select(func.count()).select_from(m).where(m.c.chat_id == c['id'], m.c.seq > read, m.c.side != side(actor))
    )


def summary(conn, c, actor):
    c = dict(c)
    chat = row(conn, 'chat', table('chat').c.id == c['id'])
    if not chat:
        raise HTTPException(404, 'Conversation no longer exists')
    owner = row(conn, 'ldt_principal', table('ldt_principal').c.id == c['owner_id'])
    return {
        **c,
        'title': chat['title'],
        'owner_name': owner['name'] if owner else '',
        'owner_kind': owner['kind'] if owner else 'user',
        'unread': unread(conn, c, actor),
        'can_send': c['next_side'] == side(actor),
    }


def snapshot(conn, actor, chat_id):
    c = require_chat(conn, actor, chat_id)
    return {**summary(conn, c, actor), 'messages': messages(conn, chat_id)}


def project_history(conn, chat_id):
    """Linear Open WebUI history only. No generation records or editable branches."""
    items = messages(conn, chat_id)
    history = {}
    for i, m in enumerate(items):
        history[m['id']] = {
            'id': m['id'],
            'role': 'assistant' if m['side'] == 'admin' else 'user',
            'content': m['content'],
            'parentId': items[i - 1]['id'] if i else None,
            'childrenIds': [items[i + 1]['id']] if i + 1 < len(items) else [],
            'files': [{'id': f, 'type': 'image', 'url': f'/api/v1/ldt/files/{f}'} for f in m['attachments']],
            'done': True,
            'timestamp': m['created_at'] // 1000,
            'ldt': {'locked': m['locked'], 'cancelled': m['cancelled'], 'text_version': m['text_version']},
        }
    current = items[-1]['id'] if items else None
    conn.execute(
        update(table('chat'))
        .where(table('chat').c.id == chat_id)
        .values(chat={'history': {'messages': history, 'currentId': current}, 'models': []}, current_message_id=current)
    )


def bump(conn, c, **values):
    c.update(values)
    c['revision'] += 1
    conn.execute(update(table('ldt_conversation')).where(table('ldt_conversation').c.id == c['id']).values(**c))


def validate_content(content, attachments):
    if len(content) > MAX_TEXT or '\x00' in content:
        raise HTTPException(422, f'Messages must be at most {MAX_TEXT} characters and contain no NUL')
    if not content.strip() and not attachments:
        raise HTTPException(422, 'A message needs text or an image')
    if len(attachments) > MAX_ATTACHMENTS or len(set(attachments)) != len(attachments):
        raise HTTPException(422, f'A message supports at most {MAX_ATTACHMENTS} distinct images')


def send(conn, actor, payload):
    prior = replay(conn, actor, payload['key'], {'op': 'send', **payload})
    if prior:
        return prior
    chat_id = payload['chat_id']
    text, files = payload['content'], payload['attachments']
    validate_content(text, files)
    if payload.get('initial_title') is not None and not payload['initial_title'].strip():
        raise HTTPException(422, 'Enter a title')
    c = row(conn, 'ldt_conversation', table('ldt_conversation').c.id == chat_id)
    if not c:
        if payload['round_id'] is not None or payload['turn_version'] != 0:
            raise HTTPException(409, 'An empty conversation has no round')
        owner_id = actor['id']
        if actor['admin']:
            owner_id = payload.get('target_user_id')
            target = row(conn, 'ldt_principal', table('ldt_principal').c.id == owner_id)
            if not target or target['kind'] != 'user' or target['disabled'] or owner_id == actor['id']:
                raise HTTPException(403, 'Choose an active registered user for a new conversation')
        elif payload.get('target_user_id'):
            raise HTTPException(403, 'Only the administrator may choose another conversation owner')
        # Do not overwrite a legacy upstream chat id, even if no LDT state exists.
        if row(conn, 'chat', table('chat').c.id == chat_id):
            raise HTTPException(409, 'Chat ID already exists')
        ts = int(time.time() * 1000)
        c = dict(
            id=chat_id,
            owner_id=owner_id,
            current_round_id=None,
            next_side=side(actor),
            turn_version=0,
            revision=0,
            seq=0,
            user_read=0,
            admin_read=0,
            last_message_at=ts,
            manual_title=bool(payload.get('initial_title')),
            deleted=False,
        )
        conn.execute(insert(table('ldt_conversation')).values(**c))
        title = (payload.get('initial_title') or '').strip() or (text.strip()[:40] if text.strip() else '图片对话')
        conn.execute(
            insert(table('chat')).values(
                id=chat_id,
                user_id=owner_id,
                title=title,
                chat={},
                created_at=ts // 1000,
                updated_at=ts // 1000,
                archived=False,
                pinned=False,
                meta={},
            )
        )
        if text.strip() and not c['manual_title']:
            conn.execute(
                insert(table('ldt_title_job')).values(
                    chat_id=chat_id, snapshot=text, attempts=0, due_at=now(), done=False
                )
            )
    c = require_chat(conn, actor, chat_id)
    if payload['round_id'] != c['current_round_id'] or payload['turn_version'] != c['turn_version']:
        raise HTTPException(409, 'The round changed. Review the conversation before sending again.')
    if c['next_side'] != side(actor):
        raise HTTPException(409, 'Wait for the other person to reply')
    if c['current_round_id']:
        rounds = table('ldt_round')
        r = row(conn, 'ldt_round', rounds.c.id == c['current_round_id'])
        if not r or r['status'] != 'pending' or r['sender_side'] == side(actor):
            raise HTTPException(409, 'The requested round is no longer pending')
        conn.execute(update(rounds).where(rounds.c.id == r['id']).values(status='completed'))
        m = table('ldt_message')
        conn.execute(update(m).where(m.c.id == r['message_id']).values(locked=True))
    mid, rid = uid(), uid()
    uploads = table('ldt_upload')
    for fid in files:
        f = row(conn, 'ldt_upload', uploads.c.id == fid)
        if not f or f['owner_id'] != actor['id'] or f['message_id'] or f['revoked'] or f['expires_at'] <= now():
            raise HTTPException(403, 'Image is expired, already used, or belongs to another identity')
    timestamp = max(int(time.time() * 1000), c['last_message_at'] + 1)
    conn.execute(
        insert(table('ldt_message')).values(
            id=mid,
            chat_id=chat_id,
            seq=c['seq'] + 1,
            author_id=actor['id'],
            side=side(actor),
            content=text,
            attachments=files,
            text_version=1,
            locked=False,
            cancelled=False,
            created_at=timestamp,
        )
    )
    for fid in files:
        conn.execute(update(uploads).where(uploads.c.id == fid).values(chat_id=chat_id, message_id=mid))
    conn.execute(
        insert(table('ldt_round')).values(
            id=rid, chat_id=chat_id, message_id=mid, sender_side=side(actor), status='pending'
        )
    )
    bump(
        conn,
        c,
        current_round_id=rid,
        next_side='user' if actor['admin'] else 'admin',
        turn_version=c['turn_version'] + 1,
        seq=c['seq'] + 1,
        last_message_at=timestamp,
    )
    conn.execute(update(table('chat')).where(table('chat').c.id == chat_id).values(updated_at=timestamp // 1000))
    project_history(conn, chat_id)
    return remember(conn, actor, payload['key'], {'op': 'send', **payload}, chat_id, snapshot(conn, actor, chat_id))


def cancel(conn, actor, chat_id, payload):
    data = {'op': 'cancel', 'chat_id': chat_id, **payload}
    prior = replay(conn, actor, payload['key'], data)
    if prior:
        return prior
    c = require_chat(conn, actor, chat_id)
    if actor['admin'] or c['current_round_id'] != payload['round_id'] or c['turn_version'] != payload['turn_version']:
        raise HTTPException(409, 'Only a user may cancel their current unanswered message')
    t = table('ldt_round')
    r = row(conn, 'ldt_round', t.c.id == c['current_round_id'])
    if not r or r['sender_side'] != 'user' or r['status'] != 'pending':
        raise HTTPException(409, 'This round cannot be cancelled')
    conn.execute(update(t).where(t.c.id == r['id']).values(status='cancelled'))
    m = table('ldt_message')
    conn.execute(update(m).where(m.c.id == r['message_id']).values(locked=True, cancelled=True))
    bump(conn, c, current_round_id=None, next_side='user', turn_version=c['turn_version'] + 1)
    project_history(conn, chat_id)
    return remember(conn, actor, payload['key'], data, chat_id, snapshot(conn, actor, chat_id))


def edit(conn, actor, chat_id, message_id, payload):
    data = {'op': 'edit', 'chat_id': chat_id, 'message_id': message_id, **payload}
    prior = replay(conn, actor, payload['key'], data)
    if prior:
        return prior
    c = require_chat(conn, actor, chat_id)
    m = table('ldt_message')
    msg = row(conn, 'ldt_message', m.c.id == message_id, m.c.chat_id == chat_id)
    if not msg or msg['side'] != side(actor) or msg['locked'] or msg['cancelled'] or msg['seq'] != c['seq']:
        raise HTTPException(409, 'Only your latest unanswered, uncancelled message can be edited')
    if msg['text_version'] != payload['text_version']:
        raise HTTPException(409, 'The text was edited elsewhere. Reload before editing again.')
    validate_content(payload['content'], msg['attachments'])
    conn.execute(
        update(m).where(m.c.id == message_id).values(content=payload['content'], text_version=msg['text_version'] + 1)
    )
    bump(conn, c)
    project_history(conn, chat_id)
    return remember(conn, actor, payload['key'], data, chat_id, snapshot(conn, actor, chat_id))


def revoke_files(conn, conditions):
    t = table('ldt_upload')
    for r in conn.execute(select(t).where(*conditions)).mappings():
        if not row(conn, 'ldt_gc', table('ldt_gc').c.file_id == r['id']):
            conn.execute(insert(table('ldt_gc')).values(file_id=r['id'], attempts=0, due_at=now()))
    conn.execute(update(t).where(*conditions).values(revoked=True))


def remove_chat(conn, actor, chat_id):
    c = require_chat(conn, actor, chat_id)
    revoke_files(conn, [table('ldt_upload').c.chat_id == chat_id])
    for name in ('ldt_message', 'ldt_round', 'ldt_request', 'ldt_title_job'):
        t = table(name)
        conn.execute(delete(t).where(t.c.chat_id == chat_id))
    conn.execute(delete(table('chat')).where(table('chat').c.id == chat_id))
    bump(conn, c, deleted=True, current_round_id=None, turn_version=c['turn_version'] + 1)
    return c


def list_chats(conn, actor, query=''):
    c = table('ldt_conversation')
    stmt = select(c).where(c.c.deleted == False)
    if not actor['admin']:
        stmt = stmt.where(c.c.owner_id == actor['id'])
    results = []
    needle = query.strip().casefold()[:200]
    for record in conn.execute(stmt.order_by(c.c.last_message_at.desc(), c.c.id)).mappings():
        s = summary(conn, record, actor)
        if needle:
            matches = [m['content'] for m in messages(conn, record['id']) if needle in m['content'].casefold()]
            if (
                needle not in s['title'].casefold()
                and not matches
                and not (actor['admin'] and needle in s['owner_name'].casefold())
            ):
                continue
            text = matches[0] if matches else s['title']
            index = text.casefold().find(needle)
            s['snippet'] = text[max(0, index - 40) : max(0, index - 40) + 180]
        results.append(s)
    return results
