"""Open WebUI application reduced to the ChatLDT manual-chat product."""

import asyncio
import contextlib
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware
from open_webui.manual.database import migrate, table
from open_webui.manual.security import secret
from open_webui.manual.jobs import worker
from open_webui.manual.oauth import router as oauth_router
from open_webui.routers.manual import router
from open_webui.socket.main import app as socket_app, revalidate_connections

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def lifespan(app):
    migrate()
    for name in (
        'user',
        'auth',
        'chat',
        'file',
        'ldt_admin',
        'ldt_principal',
        'ldt_session',
        'ldt_conversation',
        'ldt_message',
        'ldt_round',
        'ldt_request',
        'ldt_upload',
        'ldt_title_job',
        'ldt_gc',
    ):
        table(name)
    jobs = [asyncio.create_task(worker()), asyncio.create_task(revalidate_connections())]
    yield
    for job in jobs:
        job.cancel()
    for job in jobs:
        with contextlib.suppress(asyncio.CancelledError):
            await job


app = FastAPI(title='ChatLDT', lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=secret(),
    session_cookie='ldt_oauth',
    max_age=600,
    same_site='lax',
    https_only=os.getenv('ENV', 'dev') == 'prod',
)
app.include_router(router)
app.include_router(oauth_router)
app.mount('/ws', socket_app)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, error):
    return JSONResponse(
        {
            'detail': 'The database operation could not complete. Your existing data remains available. Reload and retry; retry uncertain sends with the same request key.'
        },
        status_code=503,
    )


@app.middleware('http')
async def headers(request: Request, call_next):
    if request.url.path.startswith(('/openai', '/ollama')) or (
        request.url.path.startswith('/api/') and not request.url.path.startswith('/api/v1/ldt/')
    ):
        return JSONResponse({'detail': 'Not found'}, status_code=404)
    length = request.headers.get('content-length', '0')
    if not length.isdigit() or int(length) > 42 * 1024 * 1024:
        return JSONResponse({'detail': 'Request is too large'}, status_code=413)
    if request.method in ('POST', 'PATCH', 'PUT', 'DELETE') and request.url.path.startswith('/api/v1/ldt/'):
        from open_webui.manual.security import check_csrf
        from open_webui.routers.manual import rate
        from fastapi import HTTPException

        try:
            check_csrf(request)
            rate(request, 'write', 120)
        except HTTPException as error:
            return JSONResponse({'detail': error.detail}, status_code=error.status_code)
        # Count actual received bytes as well, including chunked requests. Do not
        # trust Content-Length or allow multipart parsing to spool without a bound.
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 42 * 1024 * 1024:
                return JSONResponse({'detail': 'Request is too large'}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith(('/api/', '/oauth/')):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/health')
def health():
    return {'status': True, 'name': 'ChatLDT', 'upstream': 'Open WebUI'}


build = ROOT / 'build'
if not build.is_dir():
    build = Path(__file__).resolve().parent / 'frontend'
if build.is_dir():
    app.mount('/_app', StaticFiles(directory=build / '_app'), name='frontend')
    # Only frontend build assets are public. DATA_DIR is never mounted.
    for name in ('static', 'assets'):
        if (build / name).is_dir():
            app.mount('/' + name, StaticFiles(directory=build / name), name=name)

    @app.get('/{path:path}')
    def spa(path: str):
        if path.startswith(('api/', 'oauth/', 'openai', 'ollama')):
            return JSONResponse({'detail': 'Not found'}, status_code=404)
        candidate = (build / path).resolve()
        if candidate.is_relative_to(build.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(build / 'index.html')
