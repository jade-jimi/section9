# Meeting Reports — 프로젝트 컨텍스트

> LLM·참여자의 단일 진입점 (DOC-20260824-001). 배경·용어·핵심 링크를 여기에 유지하라.
> 규약은 이 파일과 assets/ 둘뿐 — 그 외 하위 구조는 자유. 10MB+ 파일은 링크로 대체.

## 배경

Meeting Reports is the durable cross-project home for Jade's briefs, meeting reports, slide-source
notes, decisions, and follow-ups. Every report cites its contributing project, Jira evidence,
release state, and observation time instead of copying mutable status without provenance.

## 용어

- Template: `projects/meeting-reports/assets/MEETING-REPORT-TEMPLATE.md`
- PowerPoint: always use `/home/jade/EE the.thmx` and its actual master layouts.
- Publication: repository/dashboard first; Confluence publishing remains an explicit gated action.

## 핵심 링크

- 프로젝트 문서(메타·멤버·이력): vault/projects/meeting-reports.md
- 에셋(외부 파일): projects/meeting-reports/assets/
- Chief report staging: `/home/jade/chief/reports/`

## Calendar and briefing contract

- Chief Meetings route: `#chief/meetings` in the Section9 shell.
- Calendar authority: a sanitized read-only snapshot at `/home/jade/chief/calendar/snapshot.json`,
  written atomically by a T3 Claude session with the authenticated M365 connector. The Linux Chief
  backend does not call Microsoft Graph directly because Conditional Access blocks that host path.
- Freshness: current for 24 hours. Missing is shown as **not connected**, malformed/unreadable as
  **unreachable**, and an old snapshot as **stale**; none of these may be rendered as zero meetings.
- Durable per-meeting history: `/home/jade/chief/calendar/history/<event-key>.json` plus Markdown
  sources here under `assets/MEETING-BRIEF-<event-key>.md` and dashboard HTML under
  `/home/jade/chief/reports/MEETING-BRIEF-<event-key>.html`.
- Meeting preparation sessions may read Jira, releases, work orders, decisions, prior reports and
  session results. Calendar/Jira/repository/cloud/Confluence/Teams writes remain forbidden unless
  Jade separately authorizes them.
- Automatic preparation: `chief-meeting-prep.timer` checks every 10 minutes. At 60 minutes before
  a non-cancelled event it starts exactly one T3 Codex (`gpt-5.6-terra`, medium) session; an explicit
  terminal Codex failure permits one Claude fallback. Event-instance state is stored at
  `/home/jade/chief/calendar/automation-state.json`, and the required history JSON is the completion
  receipt. Active sessions and completed receipts suppress duplicates.
- Calendar freshness is maintained by at most one bounded T3 Claude refresh per 24 hours. The
  ten-minute timer does not query M365; it reads the saved snapshot only so it can dispatch at the
  60-minute boundary. Jade can use the explicit **Refresh calendar · Claude** action for an
  exceptional same-day schedule change.
- Ready notification: only after both `<event-key>.json` and its non-empty browser report exist,
  the watcher sends one personal ntfy message through `/home/jade/chief/bin/chief-notify` with the
  meeting title/time and `#chief/meetings` link. `notified_at` in automation state deduplicates it;
  a failed ntfy send remains unacknowledged and retries on a later timer tick. Teams is never used.

## Completed-work presentations

- Chief route: `#chief/presentations`.
- Eligibility is evidence-first: terminal work needs recorded Problem, Solution performed,
  Result/evidence, Remaining boundary, and a readable source/report before it is labelled
  **Presentation ready**. Everything else remains **Needs brief**.
- Generated Markdown: `assets/PRESENTATION-<work-key>.md`.
- Generated browser HTML: `/home/jade/chief/reports/PRESENTATION-<work-key>.html`.
- Discovery metadata: `/home/jade/chief/presentations/<work-key>.json` with exact problem,
  solution, result, remaining boundary, source and report references.
- Generation runs in the local `meeting-reports` T3 project with Jade's selected Codex/Claude model
  and is read/report-only. It never transitions Jira, merges PRs, deploys, publishes Confluence or
  sends Teams messages. PowerPoint is a later explicit action and must use `/home/jade/EE the.thmx`.
