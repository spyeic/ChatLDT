"""Create disposable UI test data; never open the application's configured DATA_DIR."""

import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

fixture_root = Path(tempfile.mkdtemp(prefix='chatldt-ui-fixture-')).resolve()
os.environ.update(
    DATA_DIR=str(fixture_root / 'data'),
    ENV='dev',
    PUBLIC_ORIGIN='http://127.0.0.1:8091',
    OPENAI_API_KEY='',
    GOOGLE_CLIENT_ID='',
    GOOGLE_CLIENT_SECRET='',
    WEBUI_SECRET_KEY=secrets.token_urlsafe(48),
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from open_webui.manual.database import migrate, table, transaction  # noqa: E402
from open_webui.manual.security import create_user, hash_password  # noqa: E402
from sqlalchemy import insert, update  # noqa: E402

migrate()
credentials = {
    'email': 'admin@example.test',
    'password': secrets.token_urlsafe(24),
    'user_email': 'friend@example.test',
    'user_password': secrets.token_urlsafe(24),
}
with transaction() as conn:
    admin = create_user(conn, credentials['email'], hash_password(credentials['password']), 'admin', admin=True)
    conn.execute(insert(table('ldt_admin')).values(singleton=1, user_id=admin['id']))
    # Verify that an already existing first-version name is only projected by role.
    conn.execute(update(table('user')).where(table('user').c.id == admin['id']).values(name='Duo'))
    conn.execute(update(table('ldt_principal')).where(table('ldt_principal').c.id == admin['id']).values(name='Duo'))
    create_user(conn, credentials['user_email'], hash_password(credentials['user_password']), 'E')
path = fixture_root / 'credentials.json'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    json.dump(credentials, output)
print(f'Isolated UI fixture: {fixture_root}')
print('Credentials are stored privately in credentials.json; no application data was opened.')
