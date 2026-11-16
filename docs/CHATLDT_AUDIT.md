# ChatLDT baseline and implementation audit

Baseline: Open WebUI package 0.13.3, commit
`b0e6098e940942281d9c83f3529ea117287a3a22` (no containing release tag).
Original branch `main`; clean worktree; origin `git@github.com:spyeic/ChatLDT.git`;
no upstream configured. No AGENTS.md was found in the repository or parent paths.
Development branch: `feature/manual-chat-ldt`. Do not commit/push/merge/rebase.

## License and branding

LICENSE condition 4 restricts altering/removing/obscuring/replacing Open WebUI
branding. Exceptions include <=50 natural-person end users in **any rolling
30-day period**, written permission, or an appropriate enterprise license.
Being a friends-only site is insufficient evidence for an exception. On 2026-11-16 the operator explicitly confirmed <=50 natural-person end users in every rolling 30-day period. Under condition 4(i), product names/icons now use ChatLDT. LICENSE, LICENSE_HISTORY, LICENSE_NOTICE and attribution remain. This does not imply endorsement by Open WebUI or OpenAI. If that exception ceases to apply, restore required branding or obtain permission. See CHATLDT_UI_POLISH.md for the incremental UI audit.

## Dependency and source map (before removal)

| Decision | Modules | Reason |
| --- | --- | --- |
| Reuse | SvelteKit static adapter, Tailwind theme/styles, shared icons, Markdown/KaTeX/highlight, i18next | Existing chat presentation and responsive layout |
| Reuse | `internal/db.py`, Alembic migration chain, `auth`/`user`/`chat`/`file` database schemas | Local persistence and compatibility; never drop historical tables |
| Extract | Password hashing/verification, authentication, Google OAuth, user preferences | Remove first-public-user-admin bootstrap and unsafe email-only linking |
| Modify | `socket/main.py`, `main.py`, chat/layout components and route registration | One application and Socket.IO server, scoped notifications, manual turns |
| Delete | Model/Ollama/completion proxy, RAG/retrieval/web search, tools/functions/pipelines/MCP, execution, speech, generation, templates, memory, suggestions/tags/summary, share/export | Outside ChatLDT scope; remove implementation and route registration |
| Delete | Docker/Compose/Kubernetes deployment, model/resource download scripts, feature-specific workflows/assets/dependencies | No Docker or inference services required |
| Retain temporarily if referenced | Historical migration schemas and helper types | Existing database upgrade paths must remain intact; no data destruction |

Review checked the original `Chat.chat` history tree and `ChatMessage` generation
records, first-user signup promotion in `routers/auths.py`, configurable OAuth
email merge/role mapping in `utils/oauth.py`, socket room authentication and
file metadata/storage routes. These must not remain alternative write paths.

## State model

An `ldt_conversation` augments the existing `chat` row. It stores owner,
`current_round_id`, `next_side`, `turn_version`, sequence and event revision,
separate read cursors, last successful message time, manual-title precedence and
a deletion tombstone. `ldt_round` stores sender, source message and
pending/completed/cancelled status. Each message stores its original author,
side, immutable attachment order, independent text version, cancelled and
locked flags. Linear parent/child history is projected into the original chat
JSON; it is never used to infer turn permissions or generate branches.

Every send closes the previous pending round (if any), locks its message,
creates one message and a new pending round pointing at the other side.
Cancellation is possible only for a user's pending message: lock and mark it,
cancel that round, clear current round and allow the user. Administrator-first
conversations can only target registered users. No empty chat is persisted.

Writes acquire SQLite's database write reservation **before** rechecking session,
ownership and state, so cancellation/reply, edit/reply, identity deletion/send
and guest migration are serialized across processes. Request fingerprints and
stored successful responses enforce actor-scoped idempotency. Text edits never
increment turn_version. Notifications contain invalidations, not message bodies;
the API remains the source of truth, including on reconnect and event reordering.

## Verification status

This audit is not an acceptance certificate. See README and the final verification
report for actual executed commands, failures and remaining limitations.
