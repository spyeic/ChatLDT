# ChatLDT

A manual-chat customization of the existing Fork, based on Open WebUI 0.13.3,
commit `b0e6098e940942281d9c83f3529ea117287a3a22`. SvelteKit, FastAPI,
SQLAlchemy/Alembic, local SQLite, local attachments and Socket.IO remain in one
application. The administrator writes all replies. No Docker, model server, vector store or
hosted database is needed. The ChatLDT interface uses original icons under LICENSE condition 4(i), based on the operator’s explicit confirmation of <=50 natural-person users per rolling 30 days. Legal and attribution notices remain.

Use Node 22 and Python 3.11/3.12:

```sh
npm ci
npm run setup
# Terminal 1
npm run backend:dev
# Terminal 2
npm run dev
```

The private `.env` is currently configured for canonical `https://chat.eurse.me` and the `https://eurse.me` alias in production mode. For local HTTP development at `http://127.0.0.1:5173`, override `PUBLIC_ORIGIN`, `ENV=dev`, and the Google callback as described in [self-hosting](docs/SELF_HOSTING.md). Set `PUBLIC_ORIGIN` to the canonical URL and list additional exact browser origins in comma-separated `ALLOWED_ORIGINS`.
Setup checks dependencies, prepares `.venv`, installs backend requirements, migrates
the database, and prompts for the sole administrator email/password without echo.
It recognizes an existing administrator and never resets the password on rerun.
Public signup always creates a regular user.

Guests choose a nickname only on first send. Persistent HttpOnly cookies and
hashed database sessions expire after 30 days without user visits. Background
pushes do not renew them. Guest conversations migrate transactionally into a
regular account on signup/signin; old guest authorization is revoked. Administrator signin
does not absorb guest data.

Each conversation strictly alternates sides. User cancellation keeps and locks
the message while releasing the user's next send. The administrator cannot cancel waiting for
a user. Text-only edits are allowed until reply/cancellation; images are immutable.
Turn versions and text versions are independent. Server transactions arbitrate
races, and idempotency keys return the original successful send result.

Text limit: 32,000 characters. Up to eight still JPEG/PNG/WebP images per message.
Images <=10 MiB retain original bytes. Larger images are compressed server-side;
original input <=40 MiB, decoded pixels <=40 million, stored image <=10 MiB.
Temporary images expire after 24 hours. All previews/downloads are authenticated;
revocation precedes retryable physical cleanup. Draft text is identity/chat scoped
in localStorage; unsent image drafts are page-local.

Optional Google OIDC uses `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and
`GOOGLE_REDIRECT_URI` (development: `http://127.0.0.1:5173/oauth/google/callback`).
Configure a Google Cloud Web application client. Existing local accounts require
an authenticated Settings → Link Google account action; email matches never bind
accounts automatically. No Google credentials means no Google button.

Optional `OPENAI_API_KEY` and `OPENAI_TITLE_MODEL` name conversations using only the
immutable first sent text snapshot. Images/history are never sent. Missing key or
failure leaves a deterministic fallback. At most three 12-second attempts. Image-
only first messages never call AI. Manual names override delayed title results.

```sh
npm run check
npm run test:frontend
# Install test tools in .venv: python -m pip install pytest==8.4.2 ruff==0.15.18
npm run test:backend
npm run build
npm start
npm run password:reset
# Stop the server before a consistent attachment/database backup:
npm run backup -- /secure/backups/chatldt.zip
npm run db:migrate
```

Production requires `ENV=prod`, HTTPS, a persistent DATA_DIR/server key, the exact
PUBLIC_ORIGIN and one application worker. See [self-hosting](docs/SELF_HOSTING.md),
[cleanup](docs/CHATLDT_CLEANUP.md), [state machine](docs/CHATLDT_AUDIT.md) and
[verification/limitations](docs/CHATLDT_VERIFICATION.md). Windows and Linux runtime
execution, live Google login and live OpenAI billing calls must be verified in the
target environment; local tests do not certify those external integrations.

Retain LICENSE, LICENSE_HISTORY and LICENSE_NOTICE. Do not assume friends-only use
qualifies for branding exceptions. The selected license limits rebranding outside
its explicit <=50 natural-person users per rolling 30 days / written permission /
enterprise-license exceptions. The operator confirmed the <=50 exception on 2026-11-16; the interface now uses ChatLDT names and original icons without claiming official endorsement. Restore required upstream branding or obtain permission if this condition no longer applies. See [UI changes and verification](docs/CHATLDT_UI_POLISH.md). No Git commit/push/merge/rebase,
remote modification or deployment is performed.

Mobile layout measurements, screenshots, video and physical-iPhone limitations are documented in [mobile layout verification](docs/CHATLDT_MOBILE_LAYOUT.md).
