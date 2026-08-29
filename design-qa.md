# Design QA — Chief one-page flow

final result: passed

## Comparison target

- Source visual truth: `/home/jade/.t3/userdata/attachments/5283a1d2-2efb-4735-be5d-e91e4a1df22d-b2983bf9-8743-4644-b7be-85d488532eba.png`
- Implementation: `state/one-page-chief-final-qa2.png`
- Same-view comparison: `state/design-qa-comparison-qa2.png`
- Full one-page flow: `state/one-page-chief-flow-tall-qa2.png`
- Viewport: 1240×986 CSS pixels for the matched comparison; 1240×1800 for below-fold flow inspection.
- Source pixels: 1239×978, normalized by northwest padding to 1240×986.
- Implementation pixels: 1240×986 at deviceScaleFactor 1.
- State: all-project Chief home, light/warm theme, Release open because dev actions are available.

## Full-view comparison

The implementation restores the source's warm ivory/forest palette, serif re-entry greeting,
two-column composition, quiet separators, next-move emphasis, and progressive disclosure. The
right column intentionally opens Release instead of Working because current data has actionable
feature-to-dev batches and release control is part of the revised product contract.

## Required fidelity surfaces

- **Fonts and typography:** serif display hierarchy, Open Sans body, small uppercase section caps,
  weights, wrapping, and line lengths match the source's editorial character. Live titles wrap
  because they are longer than the source fixture; no clipping occurs.
- **Spacing and layout rhythm:** two balanced columns, generous outer margins, section rules, calm
  vertical rhythm, and compact right-hand disclosures match the selected source. The tall capture
  confirms the complete context trail remains on the same page.
- **Colors and tokens:** warm ivory background, dark forest text, muted green state ink, and amber
  attention state closely match the source. State text remains explicit instead of color-only.
- **Image quality and assets:** the screen is information UI and uses no source photography or
  custom raster imagery. No placeholder imagery or recreated logo asset is present.
- **Copy and content:** the implementation uses current saved Jira/work/session/release facts rather
  than mock content. It adds the required release, relation, session, and document actions without
  exposing Section9 implementation language.

## Focused-region evidence

A separate crop was unnecessary: the 1240×986 comparison keeps all key typography, controls, and
status labels readable. The 1240×1800 capture was inspected for the context-trail numbering,
relation-map action, and below-fold layout.

## Interaction verification

- Jira-backed Add work route: dry-run produced a Jira key and durable REQ placeholder without writes.
- Release: T3 Codex merge-dev dry-run passed; visible CTA is `Check + merge feature PRs to dev`.
- Reports: release and agent reports remain visible when present.
- Relations: `Open full relation map` routes to native Section9 Graph and only focuses a real native node.
- Sessions: T3 transcript loads and steer dry-run passes; Open T3 Code appears only with a thread.
- Documents: a real project `CONTEXT.md` rendered as HTML through the in-page reader.
- JavaScript syntax, Python tests, adapter tests, and diff checks pass.

## Comparison history

### Pass 1 — blocked

- **P2:** Context trail displayed native ordered-list numbers and circular counters simultaneously.
- Fix: `.chief-trail` now uses `list-style:none;margin:0;padding:0`.

### Pass 2 — passed

- Post-fix evidence: `state/one-page-chief-flow-tall-qa2.png` shows one circular number per stage.
- No actionable P0, P1, or P2 visual differences remain.

## Follow-up polish

- P3: a future acknowledgement timestamp could make “since your last visit” exact instead of using
  the latest recorded changes. This does not block the current one-page flow.
