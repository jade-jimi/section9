# Calendar & Meeting-Source Inventory — Chief Meetings page

- req: REQ-20260831-021-wfow (parent REQ-20260831-020-wfow)
- written: 2026-08-31 15:34:10 KST (inventory session, read-only; verification events 15:33:05–15:33:40 KST same session)
- scope: what calendar data Chief can read now, existing durable meeting/history sources, and a minimal honest adapter contract. No application code, cloud state, Jira, calendar, Confluence, or Teams was changed.

## 1. Calendar access: CONNECTED — but only through a claude.ai M365 connector session, not through Chief's backend

**Verified connected (event 2026-08-31 15:33:05–15:33:40 KST):** the claude.ai
Microsoft 365 MCP connector in this Claude session authenticated as
`jade@elementenergy.com` (get_me → displayName "Jade Kwon", jobTitle "Staff MTS") and a
live `outlook_calendar_search` for 2026-08-31 → 2026-09-05 returned **6 real events**
(UL1974/BT2 biweekly Sep 1 08:00 KST; Cloud Team Sprint Sep 1 09:00; canceled Inertia
Sep 2; Company Dinner Sep 2; Raun:Jade 1:1 Sep 3 08:30; Spencer/Cloud Sync Sep 4
09:00). Events carry subject, organizer, full attendee list, start/end with named
timeZone (`Korea Standard Time`), location, body summary, importance, showAs,
isCancelled, recurrence, webLink, and a `calendar:///events/...` URI for full detail.

**NOT connected at the Chief backend.** Three independent pieces of evidence:

1. `/home/jade/chief/mobile/server.py` (the loopback API on 127.0.0.1:14098 that the
   Chief dashboard reads) has **no calendar or meeting endpoint** — its record builders
   cover work, releases, Jira snapshot, reqs, sessions/chat, reports, decisions only.
   `grep -i 'meeting\|calendar'` over the file returns nothing.
2. Direct Microsoft Graph from this host is **Conditional-Access-blocked
   (AADSTS530003)** — stated in the header of `~/chief/bin/m365-notify`, which exists
   precisely as the fallback: it polls jade's self-hosted ntfy (`ntfy.eeclb.com`) for
   pings pushed by Power Automate flows ("new mail / meeting soon / Teams mention").
   Notification-grade only: title+body pings, not structured events.
3. `~/chief/bin/mail-check` / `mail-bridge` are the mail-side fallback (Gmail IMAP on
   the forwarded `jade@clbcloud.com` box, headers only). No calendar equivalent exists.

**Consequence:** any "live calendar" feature runs *inside a Claude session that has the
connector*, or on data such a session snapshots to disk. Chief's Python backend cannot
poll the calendar itself under current CA policy, and no local ICS/feed file was found
anywhere under `~/chief` or `~/section9-chief`.

## 2. Existing durable meeting/history sources

Meeting-specific:

| Source | What it is | Freshness |
|---|---|---|
| `~/chief/.claude/skills/meeting-prep/SKILL.md` | The proven prep workflow (attendees → THE ONE THING → per-person asks → numbers with n/source/verdict → what-not-to-say) | process doc, stable |
| `~/chief/share/to-mac/MEETING-PREP-<date>.md` | Delivered prep docs (e.g. 2026-08-18 Max+Spencer BDA-2830) | written per meeting |
| `~/chief/prep/` | Meeting artifacts (UL1974 2026-08-04 show-and-tell md/html/scrap) | per meeting |
| `~/chief/share/to-mac/` decks, `WEEK-*.html`, `TOMORROW-*.md` | Delivered slides and daily/weekly briefs | per delivery |
| `projects/meeting-reports/assets/MEETING-REPORT-TEMPLATE.md` | Report template with `meeting/date/audience/projects/jira/releases/prepared_at/evidence_as_of` frontmatter | template |

Cross-project history a Meetings page can join against (all local, all durable):

- **Releases**: `~/chief/releases/*-live.json` — per-repo records with `id, project, repo, status, batch_state, target, promotion_target, updated, open_pr_count, prs, blockers, promotion`; also served by `server.py` `_release_records`.
- **Jira**: `~/chief/jira-work-sync.json` (`version/events/updated_at`) + `bin/jira`, `bin/jira-context.py`, `bin/jira-work-sync.py`; served as `_jira_snapshot`.
- **Work/decisions**: `LEDGER.md`/`ledger.db`, `decisions.json` + `decisions.log.jsonl`, `blockers.json` (incl. `src:external` = blocked ON a person), `reqs/active/`, `work.jsonl`, `work-runs/`, per-repo `work-orders/WO-*.md`.
- **Facts/corrections**: `facts.jsonl`, `bin/recall`, `bin/fact` — where retracted numbers live (meeting-prep hard requirement).
- **Sessions**: `~/chief/chat.db` (served by `api_chat_sessions`/`api_chat_messages`); section9 `vault/sessions/2026/...` SES docs.
- **Section9 vault**: `vault/requests/**/REQ-*.md` (goal/status/history per request), `projects/*/CONTEXT.md`, project docs in `vault/projects/`.
- **Reports**: `~/chief/reports/` staging, `library/REPORTS.md`, published HTML via `bin/publish-*-report*.py`.

## 3. Proposed read-only calendar adapter contract

Honest boundary: the adapter is a **snapshot file written by a connector-bearing Claude
session**, read (never written) by the Chief/Section9 UI. The backend renders only what
the snapshot contains and always shows its age.

Proposed snapshot: `~/chief/calendar/snapshot.json` (or `state/calendar-snapshot.json`):

```json
{
  "fetched_at": "2026-08-31T15:33:40+09:00",
  "fetched_by": "claude-session <id> via claude.ai M365 connector",
  "account": "jade@elementenergy.com",
  "window": {"after": "...", "before": "..."},
  "events": [{
    "id": "...outlook event id...",
    "uri": "calendar:///events/...",
    "subject": "UL1974 / BT2",
    "organizer": "corrado@elementenergy.com",
    "attendees": ["..."],
    "start": {"dateTime": "2026-09-01T08:00:00", "timeZone": "Korea Standard Time"},
    "end":   {"dateTime": "2026-09-01T09:00:00", "timeZone": "Korea Standard Time"},
    "location": "Microsoft Teams Meeting; mtr-bellagio",
    "is_cancelled": false, "is_all_day": false, "show_as": "busy",
    "importance": "normal", "recurrence": null,
    "web_link": "https://outlook.office365.com/..."
  }]
}
```

Field rules (all available today from `outlook_calendar_search`, verified above):
- **Keep**: subject, organizer, attendees, start/end **with named timeZone rendered as-is** (never re-interpret as UTC), location, isCancelled, showAs, importance, recurrence, webLink, event id/uri.
- **Drop**: body/summary text beyond the first line (contains Teams passcodes/dial-ins — treat as sensitive; the webLink suffices), and never store tokens or connector internals.
- **Freshness semantics**: the page always displays `fetched_at` age ("as of 15:33 KST, 2h ago"). A snapshot older than a threshold (suggest 24h) renders as **STALE — not current calendar**, never silently as truth. A missing/unreadable snapshot renders "calendar not connected", never an empty week ("empty" ≠ "failed read"). `fetched_by` makes provenance auditable.
- **Refresh path**: an interactive chief session (or a scheduled connector-bearing Claude session) re-runs the search and rewrites the snapshot atomically. Chief's backend never calls Graph itself (CA-blocked, and the block is a policy fact, not a bug to route around).

### Snapshot result (REQ-20260831-021-wfow)

First snapshot written: `/home/jade/chief/calendar/snapshot.json` (atomic tmp-then-rename,
JSON-validated). **43 events**, window 2026-08-01 → 2026-09-30 KST inclusive (query
`afterDateTime 2026-08-01T00:00:00+09:00`, `beforeDateTime 2026-10-01T00:00:00+09:00`,
connector `totalResultCount` 43, both pages fetched). Observation time (fetched_at)
**2026-08-31 15:39:48 KST**; fetch events 15:37:39–15:39:48 KST same session;
`fetched_by: "T3 Claude calendar snapshot 88c60a58"`. Includes 1 cancelled event
(`Canceled: Inertia` 2026-09-02, `is_cancelled: true`). Body/summary text, Teams join
URLs/passcodes/dial-ins, tokens, and connector internals excluded (grep for
passcode/join-URL/dial-in over the file: 0 hits). No calendar, Jira, cloud, Confluence,
or Teams state was changed.

## 4. Linking per-meeting history to work state

Join key is **meeting identity**, resolved in two layers:

1. **Stable series key**: normalized subject + organizer (e.g. `ul1974-bt2 / corrado@`) identifies the recurring series; the Outlook event `id` identifies the instance. Store both on every meeting-derived artifact.
2. **Frontmatter linkage** (the template already has the slots): every prep doc / meeting report carries `meeting:` (series key), `date:`, `projects:`, `jira:` (ticket keys), `releases:` (release record `id`s), `evidence_as_of:`. That makes linkage greppable without a database.

Per-meeting history assembly (all read-only joins):
- **projects**: attendee ∩ project membership + explicit `projects:` frontmatter; Chief `projects.json` / section9 `vault/projects/*.md`.
- **Jira**: `jira:` keys → `jira-work-sync.json` events for status-at-meeting-time vs now.
- **releases**: `releases:` ids → `~/chief/releases/*-live.json` (`updated` gives the state as-of comparison).
- **reports**: prior artifacts for the same series key under `share/to-mac/`, `prep/`, `reports/`, meeting-reports project.
- **decisions/follow-ups**: `decisions.log.jsonl` and section9 REQ docs whose notes cite the series key; follow-ups are ordinary REQs tagged with the meeting series so the next prep can list "what we promised last time".
- **people**: `blockers.json` `src:external` filtered by attendee — the "which blocker names two attendees" test from meeting-prep.

The convention that makes this work: **new artifacts must cite the series key + event id at write time.** Nothing else needs schema changes.

## 5. Gaps and safe next step

Exact gaps:
1. No calendar snapshot file exists yet anywhere — every calendar read today is ephemeral, inside a connector session.
2. Chief backend/UI has no Meetings surface (no endpoint, no route).
3. Existing meeting artifacts (`MEETING-PREP-2026-08-18.md`, `prep/UL1974-*`) carry no machine-readable meeting key, so past history is join-by-filename only.
4. No scheduled refresh path; `m365-notify` gives "meeting soon" pings but no structured events.
5. Historical meetings older than ~1 year are outside the connector's default search window (max 5 years with explicit dates).

Safe next step (fully read-only on external systems): have a connector-bearing chief session write the first `~/chief/calendar/snapshot.json` for a ±14-day window using the §3 contract, then build the Meetings page against that file with the staleness rendering rules. No cloud, Jira, calendar, Confluence, or Teams state changes; the only write is one local JSON file.
