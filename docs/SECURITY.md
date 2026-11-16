# ChatLDT security

This Fork is maintained independently. Report ChatLDT defects privately to your
instance administrator or the Fork maintainer. Do not send private transcripts,
cookies, credentials or database files to upstream issue trackers.

Sessions use random 384-bit credentials with only SHA-256 digests in SQLite.
Production cookies are HttpOnly, Secure and SameSite=Lax. All cookie write APIs
require a session-bound HMAC CSRF header and validate the browser Origin against
PUBLIC_ORIGIN. Use HTTPS and one application worker behind a trusted local proxy.

SQLite transactions reserve writes before authorization/state reads. Google
subjects bind only after verified OIDC state/nonce validation; a matching email
alone cannot bind an existing account. Public signup cannot create an admin.
Password recovery is an operator command, without SMTP or email-reset endpoints.

Uploads and previews require current identity and conversation authorization.
Temporary images expire after 24 hours. Database revocation is immediate; physical
cleanup retries with backoff. Unreferenced files in the dedicated `ldt-uploads`
directory are removed after a 24-hour grace period. Existing upstream upload
folders are never scanned by this garbage collector.

Only the title worker can contact OpenAI, using the immutable first-message text
snapshot; images and later history are never included. Google OIDC uses Google
endpoints only when configured and invoked. No analytics, notification service,
webhooks, model plugins, model proxies or code execution endpoints are registered.
