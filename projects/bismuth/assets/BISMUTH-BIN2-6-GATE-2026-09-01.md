# Bismuth Bin 2/6 gate

## Presentation purpose

Explain how Bismuth prevents incomplete or stale evidence from becoming a battery disposition,
what the recorded incidents prove, and where the end-to-end boundary still belongs to the BT2
station client. This deck must never imply that every Bin 2 or Bin 6 is false.

Prepared: 2026-09-01 KST  
Primary system: Bismuth, Louisville offline/failover node  
Evidence mode: saved reports, tests, configuration and work records; no new live query

## Problem

Two different incomplete-evidence paths can look like a battery failure:

1. **Checkout / Bin 2:** an empty HTTP 200 or no final aggregate reaches the station result-fetch
   path. The historical station contract converts an empty answer into retest/Bin 2. A 503
   `NOT_READY` makes the client retry, but the real client still has a finite timeout and may later
   call Bin 2 unless that timeout state is separated from battery grade.
2. **Grading / Bin 6:** missing CHG data, mixed attempts, or wrong final-result reconciliation can
   produce or preserve an incomplete Bin 6/Grade F even when intake evidence says the unit passed.

Legitimate Bin 2/6 results still exist. One bounded BT1 cohort contained one real Bin 6: a complete
station result with 4.17168195 V against a 4.049 V high-critical threshold. The gate must therefore
test **evidence completeness and finality**, not suppress a bin number.

## Solution performed

Bismuth uses a layered gate rather than one boolean:

- **Attempt identity/finality:** grade and checkout evidence must belong to the current EESN/side/
  attempt instead of a recent output timestamp from a prior tester or cycle.
- **Completeness gate:** observed sequence coverage and charge-cycle evidence must be complete before
  persistent RAD grading; a positive sequence gap holds the grade.
- **Checkout gate:** a known unit with incomplete/no final aggregate returns 503 `NOT_READY` with
  retry semantics rather than an empty 200 that silently becomes Bin 2.
- **Backstop and reconciliation:** after the last-side RAD, current source waits 5 minutes (measured
  cloud latency p50 1.8 min / p90 4.7 min; checkout is roughly 20 min), then re-verifies missing grades or
  suspect Bin 2/6. A five-minute normal-grader grace precedes up-sync. Only attempt-proven missing or
  strictly better results may advance cloud; equal Bin 1 is skipped, visual-reject Bin 3 is never
  overridden, and rejected writes remain unsynced for retry.

Current repository Compose declares `BISMUTH_CHECKOUT_GATE=true` and
`BISMUTH_COMPLETENESS_GATE=true`. That is configuration evidence, not a fresh runtime check.
`scripts/grade_backstop.py` is authoritative for the current five-minute default; older
`docs/CONTAINERIZE.md` text still says ten minutes and is stale.

Current release evidence checked 2026-09-01 06:41:44 KST records production PR #208 merged at
2026-08-31 18:23:02 KST. Its exact promotion source and resulting `origin/master` both contain the
Bin-6 correction implementation commit `d3c8f1f`. This proves the implementation is in the
production branch; the presentation did not perform a fresh Louisville container/runtime check.

## Recorded evidence

### Bin semantics — per-side events, 2026-04-27 through 2026-08-04

| Bin | Diagnostic/error evidence | Median BISoH | Interpretation |
|---|---:|---:|---|
| Bin 1 | reference cohort | 91.20 | normal/pass reference |
| Bin 2 | errors on 1,565 / 1,572 events (99.6%) | 91.09 | usually could not grade / incomplete evidence |
| Bin 6 | 256 / 293 events error-free (87.4%) | 69.45 | usually an algorithm-produced failing verdict |

Observed 2026-08-04 16:52 KST. These are population semantics, not a rule that labels every
individual event; the gate still inspects current-attempt evidence.

### Online parity baseline — 2026-07-10 through 2026-07-25, per side

| Metric | Recorded result |
|---|---:|
| Unique dry-run side grades | 662 |
| Comparable cloud side grades | 658 |
| Incomplete at RAD | 5 / 662 (1%) |
| Missing-CHG Bin 6 | 0 |
| False-incomplete Bin 6 vs cloud Bin 1 | 0 |
| Bin parity | 655 / 658 (99.5%) |
| Grade parity | 646 / 658 (98.2%) |
| Bin 2 vs cloud Bin 1 | 3 (information only; OCV timing) |

This is an online regression guard, not the decisive offline test. Ninety-one percent of samples
fall on July 22–24, when warehouse sync already kept inputs mostly complete.

### Checkout incident — Louisville day 2026-08-25

| Signal | Count | Grain / meaning |
|---|---:|---|
| `NO DATA` | 12 | checkout response rows; four named the exact incident EESN |
| `503 NOT_READY` | 56 | five requested EESNs; Bismuth withheld incomplete answers |
| station `calling bin 2` | 14 | timeout decisions, 13 unique EESNs; not 14 authoritative grades |

For `USETK262300657`, Bismuth served four empty 200s, then later withheld 19 incomplete answers for
the same unit at another tester. Tester 46 and tester 49 both eventually timed out and called Bin 2.
No current authoritative `result_bin_ets` row existed at the cutoff, so the evidence proves timeout
decisions and retest churn—not a final banked grade. The incident was not an internet outage.

### Bin 6 correction cohort — 2026-08-25

| Metric | Recorded result |
|---|---:|
| Distinct final cloud Bin 6 / Grade F units | 31 |
| Units with BT1 Bin 1, Hipot Bin 1, PASS intake | 31 / 31 |
| Preserved side inputs / SOS outputs / final outputs | 62 / 62 / 62 |
| Bismuth final outputs | all Bin 1 |
| Necessary original-timestamp side corrections appended | 58 / 58 |
| Sides already cloud Bin 1 and skipped | 4 |
| Post-correction cloud `v_bining` | Bin 1 for 31 / 31 units |

The correction closed the disposition mismatch, while the original cloud grader's exact input
transformation/image/snapshot remains an explicit Max-owned evidence boundary.

## Safe operating contract

| Situation | Bismuth action | Operator interpretation |
|---|---|---|
| known unit, current attempt incomplete | 503 `NOT_READY` + retry | availability state, not battery grade |
| current attempt has complete L/R final evidence | 200 with a real aggregate row | station may bank `max(L,R)` |
| observed sequence gap / missing charge cycle | hold persistent grade | do not manufacture Bin 6 |
| cloud grade missing after grace and local proof complete | send bounded correction | record attempt provenance |
| cloud already equal or better | skip | avoid duplicate/overwrite |
| insert rejected | remain unsynced and retry | never mark success on failure |

Acceptance guard: sample `n >= 100`, missing-CHG Bin 6 `= 0`, false-incomplete Bin 6 vs cloud Bin 1
`= 0`, bin parity `>= 98%`. Bin 2 vs cloud Bin 1 remains informational because OCV rest timing is a
separate checkout-grace issue.

## Remaining boundary and action

- Bind station result-fetch identity immutably to EESN/attempt across retries and slot reuse.
- Do not convert retrieval timeout/503 into a battery Bin 2 without a durable reason row.
- Add attempt IDs to station and Bismuth logs; do not reconstruct identity from millisecond timing.
- Complete a controlled offline/failover drill with a real designated station before claiming the
  false Bin 2/6 path is eliminated fleet-wide.
- Keep dashboard signals honest: empty checkout answers should be measured zero; unavailable source
  must remain `Not measured`.
- Runtime enablement/rollback requires normal deployment verification. Relevant flags:
  `BISMUTH_CHECKOUT_GATE`, `BISMUTH_COMPLETENESS_GATE`, `BISMUTH_PATCHED_RAD_GRADING`, and
  `BISMUTH_UPSYNC_GRADES`. A configuration change requires container recreation; code defaults do
  not prove running state.

## Slide sequence

1. The gate protects a decision, not a bin number.
2. Incomplete evidence has two failure paths: checkout Bin 2 and grading Bin 6.
3. Four layers keep availability separate from grade.
4. Online parity is strong, but the decisive proof is offline/failover.
5. Checkout withholding works; station timeout remains the open end-to-end boundary.
6. The Bin 6 cohort was corrected through attempt-proven reconciliation.
7. The operator contract is fail-closed, measured and reversible.
8. Decision: keep the gates; finish station identity/timeout semantics.

## Primary sources

- `/home/jade/repo/bismuth/SBS_2WAY_ACCEPTANCE.md`
- `/home/jade/repo/bismuth/docs/checkout_repoll_test_plan.md`
- `/home/jade/repo/bismuth/reports/BT2-LIVE-NO-DATA-CHECKOUT-FAILURE-2026-08-26.md`
- `/home/jade/repo/bismuth/docs/BT2-BIN6-BISMUTH-RESULT-CORRECTION-2026-08-26.md`
- `/home/jade/repo/bismuth/reports/BT2-BIN6-BT1-OCV-BISMUTH-COVERAGE-2026-08-26.md`
- `/home/jade/repo/bismuth/docker-compose.app.yml`
- `/home/jade/repo/bismuth/docs/CONTAINERIZE.md`
