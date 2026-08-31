# Concurrent session execution

This is the durable concurrency policy for Chief-created AI work sessions. It applies to the lead
inside the session; it does not authorize extra production, publishing, notification, or other
external writes.

## Canonical session contract

Classify the work before editing. Size S or genuinely single-file work stays with the lead so
coordination overhead does not slow it down. For size M/L work with two or more independent tracks,
the lead must start the independent tracks concurrently with up to three bounded subagents (three
subagents plus the lead), while continuing useful lead work.

Give every subagent an explicit, non-overlapping file/component/evidence scope and a concrete
deliverable. Before edits, record lead and subagent ownership/claims in the authoritative
file-backed work order or Section9 REQ; append each returned result and evidence there as a
subagent note so the handoff survives chat loss.

Subagents must not independently deploy or write to production, merge, close or mutate Jira,
publish to Confluence, post to Teams, send notifications, or make any other external-state write.
The lead integrates the bounded results, resolves overlap, runs the final combined tests/evidence
checks, and owns the durable result and final report.

If a track needs its own branch/worktree/PR or must survive after the parent context ends, route it
to a separate T3 worker session with a durable work order instead of a subagent. Use subagents for
bounded investigation, evidence, review, and non-overlapping short implementation tracks. If the
harness has no subagent capability, record the limit and continue sequentially; never claim parallel
work that did not occur.

The executable canonical copy is `CONCURRENT_SESSION_EXECUTION` in
`/home/jade/chief/bin/session_jobs.py`, with the idempotent public wrapper
`with_concurrent_session_execution(text)`. Keep specialized launchers aligned with that copy
instead of inventing weaker variants.

## Required routing behavior

- Direct work: size S or a genuine single-file change remains with the lead.
- Parallel work: size M/L plus at least two independent tracks requires concurrent fan-out, capped
  at three active subagents plus the lead.
- Ownership: tracks must have non-overlapping file, component, or evidence boundaries and explicit
  deliverables.
- Durability: claims and returned evidence live in the authoritative work order or Section9 REQ,
  not only in chat context.
- Safety: production and external-state writes remain lead-controlled and continue through their
  existing human gates.
- Completion: the lead integrates all tracks, executes combined verification, and writes the final
  evidence-backed result.

## Entry-path coverage

`session_jobs._assignment()` injects the canonical contract exactly once. That shared boundary
covers work, release, and deep-detail sessions launched through `session_jobs.start()`, independent
of whether the selected T3 provider is Codex or Claude and whether execution is local or remote.

Entry paths that construct first-turn assignments without `session_jobs._assignment()` must append
the same canonical contract exactly once and test both its presence and idempotence. In particular,
Chief direct/project bootstrap, automatic meeting preparation, calendar refresh work, and
presentation generation need explicit coverage at their own assignment builders when they bypass
the shared boundary.

### Integration audit: 2026-08-31

- Already covered: `mobile/server.py::api_deep_detail_start()`,
  `api_work_session_start()`, and `_api_release_session_start_locked()` call
  `session_jobs.start()` and therefore receive the contract through `_assignment()`. This includes
  tracked remote runs because the wrapped request is written before remote staging.
- Chief direct: `api_chief_chat_message()` decorates the first actual user order and persists a
  `concurrency_contract_delivered` marker; subsequent turns remain ordinary steering messages.
- Project conversations: remote bootstrap envelopes are wrapped before staging. Local threads
  receive the contract on their first real dashboard order and persist the same exact-once marker.
  Existing pre-contract threads receive it on their next order without being recreated.
- Legacy card threads: `api_t3_session()` sends a context-only wrapped bootstrap assignment, so a
  session opened from the older card route also has the policy before Jade steers it.
- Meeting/presentation preparation: `prep_assignment()` and `refresh_assignment()` use the public
  idempotent wrapper. Presentation evidence, narrative/deck construction, and verification can run
  as independent tracks under that same meeting-prep lead.

If importing `session_jobs.py` from all of these paths becomes cyclic or too heavy, move only the
constant and idempotent wrapper to `core/session_contracts.py`, then import that dependency-light
module everywhere. Do not copy the literal into each launcher.

## Verification

Tests must prove:

1. every constructed assignment contains the canonical contract once;
2. applying the helper to an already-instrumented assignment is idempotent;
3. the text preserves the direct-work threshold, required M/L fan-out, three-subagent cap,
   non-overlap, durable claims/results, external-write boundary, and lead-owned integration/testing.
