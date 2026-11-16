"""Interactive, idempotent single-administrator setup and local password recovery."""

import argparse
import getpass
import sys
from sqlalchemy import select, insert, update
from fastapi import HTTPException
from open_webui.manual.database import migrate, transaction, table
from open_webui.manual import security as auth


def setup():
    migrate()
    with transaction() as conn:
        admins = list(conn.execute(select(table('user')).where(table('user').c.role == 'admin')).mappings())
        if len(admins) > 1:
            raise RuntimeError(
                'Existing database contains multiple administrators. Resolve this on a backup copy before setup; no roles were changed.'
            )
        singleton = auth.row(conn, 'ldt_admin', table('ldt_admin').c.singleton == 1)
        if singleton:
            if not admins or admins[0]['id'] != singleton['user_id']:
                raise RuntimeError('Administrator registry and user role disagree; no credentials were changed.')
            auth.ensure_user_principal(conn, admins[0])
            print('Existing admin account recognized; password unchanged.')
            return
        if admins:
            user = admins[0]
            auth.ensure_user_principal(conn, user)
            print('Existing administrator recognized; password unchanged.')
        else:
            # Both email and password are hidden as requested; never echo secrets.
            email = getpass.getpass('Administrator email (hidden): ').strip().lower()
            password = getpass.getpass('Administrator password (at least 12 characters): ')
            if password != getpass.getpass('Confirm password: '):
                raise RuntimeError('Passwords differ; no administrator created.')
            user = auth.create_user(conn, email, auth.hash_password(password), 'admin', admin=True)
        conn.execute(insert(table('ldt_admin')).values(singleton=1, user_id=user['id']))
    print('Administrator initialized.')


def reset():
    migrate()
    email = getpass.getpass('Existing local account email (hidden): ').strip().lower()
    password = getpass.getpass('New password (at least 12 characters): ')
    if password != getpass.getpass('Confirm new password: '):
        raise RuntimeError('Passwords differ; password unchanged.')
    hashed = auth.hash_password(password)
    with transaction() as conn:
        account = auth.row(conn, 'auth', table('auth').c.email == email)
        if not account or not account['active'] or not account['password']:
            raise RuntimeError(
                'No active local-password account found. Google-only accounts cannot receive a password through this command.'
            )
        conn.execute(
            update(table('auth'))
            .where(table('auth').c.id == account['id'])
            .values(password=hashed, session_stamp=auth.uid())
        )
        conn.execute(
            update(table('ldt_session'))
            .where(table('ldt_session').c.principal_id == account['id'])
            .values(revoked=True)
        )
    print(
        'Password reset. Old API/socket authorization revoked. Idle sockets close on the next authentication sweep (within 30 seconds).'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['setup', 'reset', 'migrate'], default='setup', nargs='?')
    args = parser.parse_args()
    try:
        {'setup': setup, 'reset': reset, 'migrate': migrate}[args.action]()
    except (RuntimeError, HTTPException) as error:
        print('Failed: ' + str(getattr(error, 'detail', error)), file=sys.stderr)
        sys.exit(1)
