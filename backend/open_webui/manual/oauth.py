"""Google OIDC via Authlib; subject binding only, never email-only account merge."""

import os
from urllib.parse import urlparse, parse_qs, urlencode
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from open_webui.manual.database import transaction, table
from open_webui.manual import security as auth
from open_webui.socket.main import disconnect_identity, notify_ownership

router = APIRouter()
oauth = OAuth()


def google():
    if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
        raise HTTPException(404, 'Google login is not configured')
    if not oauth.create_client('google'):
        oauth.register(
            name='google',
            client_id=os.environ['GOOGLE_CLIENT_ID'],
            client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
    return oauth.create_client('google')


@router.post('/api/v1/ldt/oauth/google/start')
async def start(request: Request):
    auth.check_csrf(request)
    with transaction() as conn:
        actor = auth.principal(conn, request, required=False)
        if actor and actor['kind'] == 'user':
            link = actor['session_hash']
        else:
            link = None
    redirect_uri = (
        os.getenv('GOOGLE_REDIRECT_URI')
        or os.getenv('PUBLIC_ORIGIN', 'http://127.0.0.1:5173').rstrip('/') + '/oauth/google/callback'
    )
    response = await google().authorize_redirect(request, redirect_uri, prompt='select_account')
    state = parse_qs(urlparse(response.headers['location']).query)['state'][0]
    request.session['ldt_' + state] = {
        'account': link,
        'guest': auth.digest(request.cookies.get(auth.COOKIE_GUEST, '')),
        'created': auth.now(),
    }
    return {'url': response.headers['location']}


@router.get('/oauth/google/callback')
async def callback(request: Request):
    try:
        state = request.query_params.get('state', '')
        binding = request.session.pop('ldt_' + state, None)
        if not binding or auth.now() - binding['created'] > 600:
            raise HTTPException(403, 'OAuth state expired; try signing in again')
        if binding['guest'] != auth.digest(request.cookies.get(auth.COOKIE_GUEST, '')):
            raise HTTPException(403, 'Guest session changed during Google login; try again')
        token = await google().authorize_access_token(request)
        info = token.get('userinfo')
        if not info or not info.get('sub') or info.get('email_verified') is not True:
            raise HTTPException(403, 'A verified Google identity is required')
        sub = str(info['sub'])
        with transaction() as conn:
            actor = auth.principal(conn, request, required=False)
            linked = next(
                (
                    dict(r)
                    for r in conn.execute(select(table('user'))).mappings()
                    if isinstance(r['oauth'], dict) and r['oauth'].get('google', {}).get('sub') == sub
                ),
                None,
            )
            if binding['account']:
                if not actor or actor.get('session_hash') != binding['account'] or actor['kind'] != 'user':
                    raise HTTPException(403, 'Sign in again before linking Google')
                if linked and linked['id'] != actor['id']:
                    raise HTTPException(409, 'This Google identity is already linked to another account')
                user = dict(auth.row(conn, 'user', table('user').c.id == actor['id']))
                data = dict(user['oauth'] or {})
                if data.get('google', {}).get('sub') not in (None, sub):
                    raise HTTPException(409, 'A different Google identity is already linked')
                data['google'] = {'sub': sub}
                conn.execute(update(table('user')).where(table('user').c.id == user['id']).values(oauth=data))
            elif linked:
                user = linked
                account = auth.row(conn, 'auth', table('auth').c.id == user['id'])
                if not account or not account['active']:
                    raise HTTPException(403, 'Account is unavailable')
                if account.get('mfa') and account['mfa'].get('secret'):
                    raise HTTPException(409, 'Existing MFA requires a reviewed migration before using this account.')
                auth.ensure_user_principal(conn, user)
                p = auth.row(conn, 'ldt_principal', table('ldt_principal').c.id == user['id'])
                if p['disabled']:
                    raise HTTPException(403, 'Account is unavailable')
            else:
                user = auth.create_user(
                    conn, info['email'], '', info.get('name') or info['email'], oauth={'google': {'sub': sub}}
                )
            merged = auth.merge_guest(conn, request, user)
            raw = auth.new_session(conn, user['id'])
        response = RedirectResponse('/', status_code=303)
        auth.cookie(response, auth.COOKIE_ACCOUNT, raw)
        if merged:
            response.delete_cookie(auth.COOKIE_GUEST, path='/')
            await disconnect_identity(merged)
            await notify_ownership(user['id'])
        return response
    except Exception as error:
        detail = (
            error.detail if isinstance(error, HTTPException) else 'Google login failed. Retry from the sign-in page.'
        )
        return RedirectResponse('/?' + urlencode({'error': detail}), status_code=303)
