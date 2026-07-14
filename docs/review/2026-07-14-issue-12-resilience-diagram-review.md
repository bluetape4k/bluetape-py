# Issue #12 Resilience Diagram Review

Date: 2026-07-14

Result: **PASS** (`23/23` checklist rows per asset, `Blocked=0`)

## Scope and authorities

Reader question: How does last-added-first policy composition execute, retry,
classify outcomes, and unwind cleanup for synchronous and asynchronous calls?

Behavior authorities:

- `packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py`
- `packages/bluetape-resilience/tests/bluetape_resilience_tests/test_pipeline.py`
- `packages/bluetape-resilience/README.md`
- `packages/bluetape-resilience/README.ko.md`

Visual authorities inspected at original size:

- `/Users/debop/work/bluetape4k/bluetape4k-wiki/docs/diagrams/best-practices/assets/sequence-workflow-sample.png`
- `/Users/debop/work/bluetape4k/clinic-appointment/docs/images/readme-diagrams/appointment-api-sequence-01.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-01.png`

Related resilience4j assets scanned:

- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-diagram-01.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-02.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.md`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.ko.md`

Loaded diagram rules:

- `/Users/debop/.codex/skills/bluetape-diagram/SKILL.md`
- `/Users/debop/.codex/skills/bluetape-diagram/references/common.md`
- `/Users/debop/.codex/skills/bluetape-diagram/references/architecture.md` (inspected, then rejected because the reader question is chronological)
- `/Users/debop/.codex/skills/bluetape-diagram/references/sequence.md`

## Canonical assets

### Synchronous

- [SVG](../images/readme-diagrams/bluetape-resilience-sync-sequence.svg)
- [PNG](../images/readme-diagrams/bluetape-resilience-sync-sequence.png)
- Absolute SVG: `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg`
- Absolute PNG: `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png`
- SVG SHA-256: `da3f16c622909a120621c5e7b8e4e39d79165dabcf26f8402caade74a4526438`
- PNG SHA-256: `ac687b4b9549062b4d25210d700a781f9093847006feec331cf84f3ddd298a32`

### Asynchronous

- [SVG](../images/readme-diagrams/bluetape-resilience-async-sequence.svg)
- [PNG](../images/readme-diagrams/bluetape-resilience-async-sequence.png)
- Absolute SVG: `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg`
- Absolute PNG: `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-async-sequence.png`
- SVG SHA-256: `a02116cbfc936132b3584229c7fd62cb6655a7acc2de2af3bca91e228ac337b8`
- PNG SHA-256: `532302bfa5fcae0829239f3adbdf978e8809f4e1e4d04c3c85c526cb4540acd8`

## Final command evidence

Both assets passed XML parsing and were rendered only with the required CLI:

```bash
cairosvg docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg \
  -o docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png -s 2
cairosvg docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg \
  -o docs/images/readme-diagrams/bluetape-resilience-async-sequence.png -s 2
```

| Asset | XML | PNG dimensions | Connector audit | Geometry | Endpoint | Mixed corner | Sequence style |
|---|---:|---:|---|---|---|---|---|
| Sync | PASS | `3800x2360` | `markers=6 connectors=10 intrusions=0 crossings=0` | `failures=0` | PASS | `paths=10 q_bends=0 failures=0` | PASS |
| Async | PASS | `4200x2760` | `markers=6 connectors=14 intrusions=0 crossings=0` | `failures=0` | PASS | `paths=14 q_bends=0 failures=0` | PASS |

Targeted XPath fallback resolved the generic sequence connector audit's
non-applicable `cards=0` count:

| Asset | Participants | Lifelines | Activations | Messages | Markers | Loop/alt frames |
|---|---:|---:|---:|---:|---:|---:|
| Sync | 6 | 6 | 5 | 10 | 6 | 2 |
| Async | 7 | 7 | 6 | 14 | 6 | 2 |

README exposure checks found each shared PNG exactly once in each locale:
`README_EN_SYNC=1`, `README_EN_ASYNC=1`, `README_KO_SYNC=1`, and
`README_KO_ASYNC=1`. `git diff --check` returned no output.

## Synchronous checklist ledger

| Check | Result | Falsifiable evidence |
|---|---|---|
| DIA-01 | PASS | Canonical SVG/PNG and both target READMEs are listed above; source question maps to `_pipeline.py` wrapping order. Kind=`sequence`. |
| DIA-02 | PASS | Loaded `SKILL.md`, `common.md`, and `sequence.md`; `architecture.md` was inspected but its rules were rejected because the reader question is chronological. |
| DIA-03 | PASS | Sync asset alone completed SVG, render, audit, original-size inspection, and commit `f0f23a3` before async work began. Invariants: last-added-first, bounded retry, circuit classification, reverse permit cleanup, no sync timeout. |
| DIA-04 | PASS | `xmllint --noout` passed; exact CairoSVG command above produced `3800x2360`. |
| DIA-05 | PASS | Five audits passed; `connectors=10`, `markers=6`, `intrusions=0`, `crossings=0`, geometry/mixed failures `0`; XPath counts are nonzero above. |
| DIA-06 | PASS | Final `3800x2360` PNG was reopened at original detail after the last coordinate change. Labels 1-10, endpoints, solid heads, frames, spacing, fonts, footer, and margins were readable with no clipping. |
| DIA-07 | PASS | English and Korean READMEs each embed the sync PNG once; asset and review links resolve; `git diff --check` clean. |
| DIA-08 | PASS | This ledger records paths, hashes, commands, dimensions, audit counts, fallback counts, references, and visual notes. `X=23`, `Y=23`, `Blocked=0`. |
| DIA-COM-01 | PASS | Target prose, `_pipeline.py`, tests, both README locales, three visual authorities, and the resilience4j related set are enumerated above. |
| DIA-COM-02 | PASS | Original PNG shows `Architects Daughter` headings, `Comic Mono` technical text, six aligned participant peers, and readable 13px message text without evidence text inside the art. |
| DIA-COM-03 | N/A | Text-only policy participants require no infrastructure logos; SVG contains no `<image>` or icon symbols, so there is no invented or duplicate icon surface. |
| DIA-COM-04 | PASS | Six fixed per-color markers use `13x13`, `refX=9`, `refY=5`, `markerUnits=userSpaceOnUse`; PNG shows solid heads matching line/label colors. |
| DIA-COM-05 | PASS | Connector audit reports `connectors=10 intrusions=0 crossings=0`; geometry and endpoint audits report zero failures; every message is horizontal between lifelines/activations. |
| DIA-COM-06 | N/A | All 10 message routes are straight horizontal paths with no bent connector. Mixed-corner proof: `paths=10 q_bends=0 failures=0`. |
| DIA-COM-07 | PASS | Canvas remains `1900x1180` and PNG `3800x2360`; final inspection found participant lanes balanced, branch frames padded, and footer separated from lifelines. |
| DIA-COM-08 | PASS | XML, CairoSVG, dimensions, connector, geometry, endpoint, mixed-corner, sequence-style, XPath, README exposure, and diff checks all have concrete output above. |
| DIA-COM-09 | PASS | Review links above target the current worktree's canonical sync SVG/PNG; both files exist and README embeds the PNG once per locale. |
| DIA-SEQ-01 | PASS | Opened the best-practices sequence sample and nearest approved `appointment-api-sequence-01.png`; resilience4j sequence was a domain comparison, not the palette authority. |
| DIA-SEQ-02 | PASS | Counts: participants `6`, lifelines `6`, activations `5`, numbered messages `10`, frames `2`; original PNG shows chronological row spacing. |
| DIA-SEQ-03 | PASS | Muted blue/olive/amber/teal/red/purple roles match line, pill, badge, and explicit marker; style audit PASS and marker count `6`. |
| DIA-SEQ-04 | PASS | Visible labels are contiguous `1..10`, each above its own uninterrupted horizontal line; original inspection found no label-line overlap. |
| DIA-SEQ-05 | PASS | One transparent loop and one transparent alt frame are chronological, padded, dashed, and separated from the footer; branch-specific purple is confined to the operation branch. |
| DIA-SEQ-06 | PASS | Sequence-style audit reports `PASS sequence_files=1`; original PNG confirms participants, labels, markers, frames, and branch semantics. |

## Asynchronous checklist ledger

| Check | Result | Falsifiable evidence |
|---|---|---|
| DIA-01 | PASS | Canonical SVG/PNG and both target READMEs are listed above; source question maps to async wrapping, timeout, cancellation, and cleanup code. Kind=`sequence`. |
| DIA-02 | PASS | Loaded `SKILL.md`, `common.md`, and `sequence.md`; `architecture.md` was inspected but rejected, so only chronological sequence rules apply. |
| DIA-03 | PASS | Async work started only after sync commit `f0f23a3`; async SVG, render, audits, original inspection, and commit `62239d1` completed as one asset loop. Invariants: one task, cooperative timeout, own-expiry mapping, external cancellation identity, reverse cleanup. |
| DIA-04 | PASS | `xmllint --noout` passed; exact CairoSVG command above produced `4200x2760`. |
| DIA-05 | PASS | Five audits passed; `connectors=14`, `markers=6`, `intrusions=0`, `crossings=0`, geometry/mixed failures `0`; XPath counts are nonzero above. |
| DIA-06 | PASS | Final `4200x2760` PNG was reopened at original detail after the last activation/loop coordinate change. Labels 1-14, timeout branches, endpoints, solid heads, frames, fonts, footer, and whitespace were readable without clipping. |
| DIA-07 | PASS | English and Korean READMEs each embed the async PNG once; asset and review links resolve; `git diff --check` clean. |
| DIA-08 | PASS | This ledger records paths, hashes, commands, dimensions, audit counts, fallback counts, references, and visual notes. `X=23`, `Y=23`, `Blocked=0`. |
| DIA-COM-01 | PASS | `_pipeline.py`, timeout/retry/circuit/bulkhead behavior, tests, README prose, visual authorities, and related resilience4j assets are listed above. |
| DIA-COM-02 | PASS | Original PNG shows approved fonts, seven aligned participant peers, readable long async class names, and no clipped/crowded message text. |
| DIA-COM-03 | N/A | Text-only policy participants require no infrastructure logos; SVG contains no `<image>` or icon symbols, so no invented or duplicate icon exists. |
| DIA-COM-04 | PASS | Six fixed per-color markers use `13x13`, `refX=9`, `refY=5`, `markerUnits=userSpaceOnUse`; purple is dedicated to external cancellation in message paths. |
| DIA-COM-05 | PASS | Connector audit reports `connectors=14 intrusions=0 crossings=0`; geometry and endpoint audits report zero failures; every message terminates on a lifeline/activation. |
| DIA-COM-06 | N/A | All 14 message routes are straight horizontal paths. Mixed-corner proof: `paths=14 q_bends=0 failures=0`. |
| DIA-COM-07 | PASS | Canvas `2100x1380` renders to `4200x2760`; final inspection found seven lanes readable, inner loop compact, timeout alt branches padded, and footer isolated. |
| DIA-COM-08 | PASS | XML, CairoSVG, dimensions, connector, geometry, endpoint, mixed-corner, sequence-style, XPath, exposure, and diff checks all have concrete output above. |
| DIA-COM-09 | PASS | Review links above target the current worktree's canonical async SVG/PNG; both files exist and README embeds the PNG once per locale. |
| DIA-SEQ-01 | PASS | Opened best-practices sample and nearest approved appointment sequence at original size; resilience4j sequence supplied domain comparison only. |
| DIA-SEQ-02 | PASS | Counts: participants `7`, lifelines `7`, activations `6`, numbered messages `14`, frames `2`; original PNG shows chronological row height. |
| DIA-SEQ-03 | PASS | Muted role colors match lines, pills, badges, and six explicit markers; external `CancelledError` uses branch-only purple. |
| DIA-SEQ-04 | PASS | Visible labels are contiguous `1..14`, each above an uninterrupted horizontal message line; long labels 7, 8, 11, and 12 were widened and re-inspected. |
| DIA-SEQ-05 | PASS | Retry loop and three-way timeout/cancellation alt frame are transparent, padded, chronological, divided, and clear of the footer. Branches distinguish normal/failure, own expiry, and external cancellation. |
| DIA-SEQ-06 | PASS | Sequence-style audit reports `PASS sequence_files=1`; original PNG confirms labels, branch-specific color, activations, frames, and cleanup order. |
