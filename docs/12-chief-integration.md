# Chief integration

Section9 is Jade's primary browser shell. Chief remains the execution and reconciliation backend.
The integration deliberately does not copy active Chief requests into Section9's vault: Jira, PR,
release, report and session state would otherwise have two writable authorities.

## Runtime

```bash
S9_ROOT=/home/jade/repo/section9 \
S9_CHIEF_API=http://127.0.0.1:14098 \
  /home/jade/repo/section9/bin/s9 serve --supervise --host 127.0.0.1 --port 9909
```

The existing Chief backend remains on `127.0.0.1:14098`. The dashboard reverse proxy exposes
Section9 as `/app/chief-mobile/`; the old frontend remains reachable as `chief-classic` for rollback.

## Authority boundary

- Section9 owns its own vault, documents, graph, audit, streams, terminal and project membership.
- Chief owns `/home/jade/chief` REQs/work orders, Jira reconciliation, Bitbucket releases, reports,
  agent sessions and direct Chief/project conversations.
- Section9's Chief view is a live read model from Chief's loopback API.
- Mutations use Chief's existing validated endpoints. Section9 never writes Chief files directly.
- Production approval remains Jade's human gate.

## Automatic work boundary

The Chief view is not a passive mirror. Assigning Ready/In-progress work starts or reuses a durable
T3 session with an explicit contract to keep moving through implementation, safe same-scope repair,
tests, PR evidence and integration to `dev`. A session stops only on a named external dependency or
the dev-to-production human gate. Release actions use Chief's idempotent autopilot to verify/repair
and merge passing PRs to dev, prepare the production-review PR, and perform read-only live
acceptance. Section9 never grants an agent authority to merge production.

Needs-you work remains a human decision and Done opens evidence. Any post-production defect becomes
a new ticket/work item through Chief's existing lifecycle rather than reopening the released work.

## Fixed adapter routes

Read routes:

- `GET /api/chief/work`
- `GET /api/chief/now`
- `GET /api/chief/session/status?id=...|work_id=...`
- `GET /api/chief/chat/sessions`
- `GET /api/chief/chat/messages?session=...`
- `GET /api/chief/chat/chief-messages`
- `GET /api/chief/report?f=...`
- `GET /api/chief/session/report?id=...`

Write routes:

- `POST /api/chief/sync`
- `POST /api/chief/session/start`
- `POST /api/chief/work/complete`
- `POST /api/chief/work/investigate`
- `POST /api/chief/order`
- `POST /api/chief/chat/session`
- `POST /api/chief/chat/message`

There is no generic proxy route. `S9_CHIEF_API` must be loopback HTTP. Query keys are allowlisted,
and adapter failures are explicit `unreachable` responses rather than empty work.

When Section9 is reached through Chief's `/app/*` proxy, GETs stay under the application prefix.
That proxy is intentionally GET-only; browser writes use the existing same-origin Chief root routes
(`/sync`, `/work-session/start`, `/work/done`, `/work/investigate`, `/orders`,
`/chief-chat/session`, `/chief-chat/message`). Direct `:9909` access uses the adapter POST routes.

## Cutover and rollback

Cutover changes only `dashboard/apps.json`:

1. `chief-mobile` points to Section9 on `127.0.0.1:9909`.
2. `chief-classic` points to the previous frontend on `127.0.0.1:14098`.

Rollback is immediate and data-free: point `chief-mobile` back to `14098`. Chief's backend never
moves, so no work, Jira, PR, report or session state is migrated or lost.

## Verification

- `python3 tests/test_chief_adapter.py`
- full Section9 stdlib test suite
- direct `:9909` and proxied `/app/chief-mobile/` browser checks
- explicit unreachable-Chief fixture
- start-session test mode and report viewer check
- responsive desktop and phone capture
