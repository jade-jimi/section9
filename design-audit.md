# Chief one-page flow — design audit

## Audit scope

- Current implementation: `state/curated-chief-brief.png` at 1600×1000.
- Selected visual truth: `/home/jade/.t3/userdata/attachments/5283a1d2-2efb-4735-be5d-e91e4a1df22d-b2983bf9-8743-4644-b7be-85d488532eba.png` at 1240×986.
- User goal: return after lost context, understand the next move and its surrounding flow on one page, then act without reconstructing work from raw messages.

## Strengths

1. The earlier Chief screen leads with a human re-entry moment, then one concrete next move.
2. Its warm ivory/forest palette, serif display face, generous spacing, and two-column rhythm make dense work feel calm.
3. Needs you, Working, and Recent done are progressive-disclosure summaries rather than separate destinations.
4. The current implementation preserves the functional Jira, release, report, and session controls.

## UX risks

1. **P1 — navigation replaced understanding.** The current first screen asks Jade to choose Brief/Work/Release/Reports/Relations/Sessions before it explains the work. The earlier screen gives the next move first.
2. **P1 — relationships disappeared from the primary flow.** Relations and sessions are separate pages, so request → Jira → work order → session → PR → release → next work cannot be read as one story.
3. **P1 — the strongest Section9 behavior is invisible.** Saved messages and work are exposed as inventories rather than distilled into what changed, why now, and the next derived item.
4. **P2 — project rail dominates the page.** Twenty project cards consume the key re-entry band even when Jade needs one answer.
5. **P2 — the page is visually sterile.** Flat white panels, small monospace metadata, and top navigation lose the earlier editorial hierarchy and warmth.
6. **P2 — excessive empty canvas.** The current Brief leaves most of the viewport blank while useful flow, release, and evidence are hidden elsewhere.

## Accessibility risks

1. Small muted monospace metadata has a likely contrast/readability risk at laptop and mobile zoom.
2. Horizontally scrolling project cards make keyboard and zoom navigation costly.
3. Status meaning relies heavily on color in several compact labels; text labels must remain explicit.

## Opportunity areas

1. Restore the earlier warm two-column Chief frame and editorial hierarchy.
2. Make one page read: greeting/context → next move → what changed → explicit work flow → needs/working/done → release/evidence/sessions.
3. Replace the project rail with one quiet scope control; keep the full project list in a drawer/menu.
4. Render a factual context trail for the selected next move: source ask → Jira → project/work order → T3 session → PR/dev → release → next/follow-up.
5. Show the latest saved-session/release changes as a short interpreted summary, with raw messages behind disclosure.
6. Keep Advanced as an escape hatch, not part of the daily reading path.

## Evidence limits

- Screenshot evidence confirms visual hierarchy and visible flow only; keyboard behavior and screen-reader semantics require implementation checks.
- The source screenshot predates the current Jira/release/session capabilities, so those must be integrated without changing its calm hierarchy.

## Recommendation

Use the earlier Chief screen as the visual truth, not merely a palette reference. Keep Section9 as the persistence and relationship layer underneath; the visible product should feel like Chief and reveal the complete work story on one page.
