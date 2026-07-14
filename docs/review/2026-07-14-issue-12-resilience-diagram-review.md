# Issue #12 Resilience Diagram Review

Date: 2026-07-14

Result: **PASS** (sync sequence: Required checks 21/21, N/A 2, Blocked 0; async sequence: Required checks 21/21, N/A 2, Blocked 0; Circuit Breaker state: Required checks 16/16, N/A 1, Blocked 0)

## Scope and authorities

Reader question: How does last-added-first policy composition execute, retry,
classify outcomes, and unwind cleanup for synchronous and asynchronous calls?

Circuit Breaker state reader question: How do `CLOSED`, `OPEN`, and
`HALF_OPEN` transition; why is recovery lazy and admission-driven; and how are
probes bounded while pre-deadline and over-capacity admissions are rejected?

Behavior authorities:

- `packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py`
- `packages/bluetape-resilience/tests/bluetape_resilience_tests/test_pipeline.py`
- `packages/bluetape-resilience/README.md`
- `packages/bluetape-resilience/README.ko.md`

Circuit Breaker state behavior authorities:

- `packages/bluetape-resilience/src/bluetape/resilience/_circuit.py`
- `packages/bluetape-resilience/tests/bluetape_resilience_tests/test_circuit.py`
- Approved state design spec:
  `docs/superpowers/specs/2026-07-14-issue-12-circuit-breaker-state-design.md`

The generalized `failure_if=False` half-open slot-release path is source-proven:
both sync and async exception paths call `_CircuitData.ignore(admission)` when
classification returns false. It is not directly isolated by a dedicated test
in `test_circuit.py` (`return False` and a dedicated ignored-exception test are
both absent). The targeted state test file passed `19` tests, but neither that
result nor a broader `144 passed` package-suite result, if cited elsewhere, is
evidence that directly isolates this exact branch.

Visual authorities inspected at original size:

- `/Users/debop/work/bluetape4k/bluetape4k-wiki/docs/diagrams/best-practices/assets/sequence-workflow-sample.png`
- `/Users/debop/work/bluetape4k/clinic-appointment/docs/images/readme-diagrams/appointment-api-sequence-01.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-01.png`

Related resilience4j assets scanned:

- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-diagram-01.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-02.png`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.md`
- `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.ko.md`

Circuit Breaker state visual and standards authorities:

- `/Users/debop/.codex/skills/bluetape-diagram/SKILL.md`
- `/Users/debop/.codex/skills/bluetape-diagram/references/common.md`
- `/Users/debop/.codex/skills/fireworks-tech-graph/SKILL.md` for UML
  state-machine nodes, initial-state, transition, guard/action, and layout
  semantics
- `/Users/debop/.codex/skills/fireworks-tech-graph/references/style-1-flat-icon.md`
  as a style comparison; the approved Bluetape visual family remains the asset
  palette and typography authority
- The resilience4j module READMEs and three related assets listed above as an
  ecosystem behavior comparison, not as proof of Python implementation details

The state asset is not a sequence diagram. Participants, lifelines,
activations, numbered messages, and loop/alt frames are N/A, and no
sequence-style audit was run. Bluetape has no state-specific audit, so UML state
semantics are proved through targeted XPath counts and `_circuit.py` source
mapping instead.

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

### Circuit Breaker state

- [SVG](../images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg)
- [PNG](../images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png)
- Absolute SVG: `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg`
- Absolute PNG: `/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png`
- SVG SHA-256: `5c375e765555ba1b672771f70d4d27623af2b057d0a8a720b580b87fe5bca836`
- PNG SHA-256: `06d98046dac58bed971f28c24257799c46219d5a05227870d41b20687e1d0a77`

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

## Circuit Breaker state command and visual evidence

Evidence is bound to verified asset HEAD
`c6591d97c7f6cecf30ab44243c22b73fc554f0bf`; the authoritative source/design,
state SVG/PNG, and README exposure files have no difference from that commit.
The comparison base is `e6bf1e4a2503b6573f17882f0044781b8a4b4a6b`.
The canonical PNG was not mutated: CairoSVG wrote a temporary render, `cmp`
proved byte identity, and the temporary file was removed. This exact executable
block reproduces every recorded state count, hash, padding value, test result,
and scoped range diff check:

```bash
set -e
asset_head=c6591d97c7f6cecf30ab44243c22b73fc554f0bf
base=e6bf1e4a2503b6573f17882f0044781b8a4b4a6b
state_svg=docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
state_png=docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png
verify_png=/tmp/bluetape-resilience-circuit-breaker-state.verify.png

git diff --quiet "$asset_head" -- \
  "$state_svg" "$state_png" \
  packages/bluetape-resilience/README.md \
  packages/bluetape-resilience/README.ko.md \
  packages/bluetape-resilience/src/bluetape/resilience/_circuit.py \
  packages/bluetape-resilience/tests/bluetape_resilience_tests/test_circuit.py \
  docs/superpowers/specs/2026-07-14-issue-12-circuit-breaker-state-design.md
echo 'ASSET_SCOPE_MATCH=PASS'

rm -f "$verify_png"
xmllint --noout "$state_svg"
echo 'XML=PASS'
cairosvg "$state_svg" -o "$verify_png" -s 2
cmp -s "$verify_png" "$state_png"
echo 'RENDER_CMP=BYTE_IDENTICAL'
sips -g pixelWidth -g pixelHeight "$verify_png"

python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" "$state_svg"
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" --fail-diagonal "$state_svg"
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" "$state_svg"
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" "$state_svg"

printf 'state='; xmllint --xpath "count(//*[local-name()='g' and contains(concat(' ', normalize-space(@class), ' '), ' state-node ')])" "$state_svg"; echo
printf 'initial='; xmllint --xpath "count(//*[local-name()='g' and contains(concat(' ', normalize-space(@class), ' '), ' initial-node ')])" "$state_svg"; echo
printf 'transition='; xmllint --xpath "count(//*[local-name()='path' and contains(concat(' ', normalize-space(@class), ' '), ' state-transition ')])" "$state_svg"; echo
printf 'rejection='; xmllint --xpath "count(//*[local-name()='path' and contains(concat(' ', normalize-space(@class), ' '), ' rejection-decision ')])" "$state_svg"; echo
printf 'connector='; xmllint --xpath "count(//*[local-name()='path' and contains(concat(' ', normalize-space(@class), ' '), ' connector ')])" "$state_svg"; echo
printf 'marker='; xmllint --xpath "count(//*[local-name()='marker'])" "$state_svg"; echo
printf 'note='; xmllint --xpath "count(//*[local-name()='g' and contains(concat(' ', normalize-space(@class), ' '), ' invariant-note ')])" "$state_svg"; echo

printf 'primary_marker_contract='; xmllint --xpath "count(//*[local-name()='marker' and (@id='arrow-red' or @id='arrow-amber' or @id='arrow-olive') and @markerWidth='14' and @markerHeight='14' and @refX='9' and @refY='5' and @orient='auto' and @markerUnits='userSpaceOnUse'])" "$state_svg"; echo
printf 'neutral_marker_contract='; xmllint --xpath "count(//*[local-name()='marker' and @id='arrow-neutral' and @markerWidth='10' and @markerHeight='10' and @refX='9' and @refY='5' and @orient='auto' and @markerUnits='userSpaceOnUse'])" "$state_svg"; echo
printf 'red_marker_fill='; xmllint --xpath "count(//*[local-name()='marker' and @id='arrow-red']/*[local-name()='path' and @fill='#A95D61'])" "$state_svg"; echo
printf 'amber_marker_fill='; xmllint --xpath "count(//*[local-name()='marker' and @id='arrow-amber']/*[local-name()='path' and @fill='#A97924'])" "$state_svg"; echo
printf 'olive_marker_fill='; xmllint --xpath "count(//*[local-name()='marker' and @id='arrow-olive']/*[local-name()='path' and @fill='#64834A'])" "$state_svg"; echo
printf 'neutral_marker_fill='; xmllint --xpath "count(//*[local-name()='marker' and @id='arrow-neutral']/*[local-name()='path' and @fill='#41545D'])" "$state_svg"; echo
printf 'red_transition_bindings='; xmllint --xpath "count(//*[local-name()='path' and contains(concat(' ', normalize-space(@class), ' '), ' state-transition ') and @stroke='#A95D61' and @marker-end='url(#arrow-red)'])" "$state_svg"; echo
printf 'amber_transition_bindings='; xmllint --xpath "count(//*[local-name()='path' and contains(concat(' ', normalize-space(@class), ' '), ' state-transition ') and @stroke='#A97924' and @marker-end='url(#arrow-amber)'])" "$state_svg"; echo
printf 'olive_transition_bindings='; xmllint --xpath "count(//*[local-name()='path' and contains(concat(' ', normalize-space(@class), ' '), ' state-transition ') and @stroke='#64834A' and @marker-end='url(#arrow-olive)'])" "$state_svg"; echo
printf 'neutral_css_contract='; xmllint --xpath "count(//*[local-name()='style' and contains(., '.rejection-decision') and contains(., '.initial-transition') and contains(., 'marker-end: url(#arrow-neutral)')])" "$state_svg"; echo
printf 'neutral_connector_bindings='; xmllint --xpath "count(//*[local-name()='path' and (contains(concat(' ', normalize-space(@class), ' '), ' rejection-decision ') or contains(concat(' ', normalize-space(@class), ' '), ' initial-transition '))])" "$state_svg"; echo
printf 'marker_fill_paths='; xmllint --xpath "count(//*[local-name()='marker']/*[local-name()='path' and @fill])" "$state_svg"; echo

printf 'canvas_root='; xmllint --xpath "count(/*[local-name()='svg' and @width='1900' and @height='1100' and @viewBox='0 0 1900 1100'])" "$state_svg"; echo
printf 'canvas_background='; xmllint --xpath "count(/*[local-name()='svg']/*[local-name()='rect' and @width='1900' and @height='1100' and @fill='#FFFFFF'])" "$state_svg"; echo
printf 'canvas_frame='; xmllint --xpath "count(/*[local-name()='svg']/*[local-name()='rect' and @x='38' and @y='30' and @width='1824' and @height='1040'])" "$state_svg"; echo
printf 'external_images='; xmllint --xpath "count(//*[local-name()='image'])" "$state_svg"; echo
printf 'icon_symbols='; xmllint --xpath "count(//*[local-name()='symbol'])" "$state_svg"; echo

shasum -a 256 "$state_svg" "$state_png"
printf 'README_EN_STATE='; rg -c 'bluetape-resilience-circuit-breaker-state\.png' packages/bluetape-resilience/README.md
printf 'README_KO_STATE='; rg -c 'bluetape-resilience-circuit-breaker-state\.png' packages/bluetape-resilience/README.ko.md

STATE_PNG="$state_png" python3 - <<'PY'
import os
from PIL import Image

image = Image.open(os.environ["STATE_PNG"]).convert("RGB")
fill = (248, 252, 254)
boxes = [
    ("closed-open", 742, 342, 332, 70),
    ("open-half-open", 820, 497, 444, 106),
    ("half-open-closed", 350, 748, 440, 82),
    ("half-open-open", 1542, 500, 278, 104),
    ("reject-open", 1020, 144, 400, 58),
    ("reject-half-open", 1118, 930, 452, 92),
]
minimum = float("inf")
for name, x, y, width, height in boxes:
    left, top = 2 * (x + 8), 2 * (y + 8)
    right, bottom = 2 * (x + width - 8), 2 * (y + height - 8)
    points = [
        (px, py)
        for py in range(top, bottom)
        for px in range(left, right)
        if max(abs(channel - fill[index]) for index, channel in enumerate(image.getpixel((px, py)))) >= 28
    ]
    min_x = min(px for px, _ in points) / 2
    max_x = max(px for px, _ in points) / 2
    padding = min(min_x - x, x + width - max_x)
    minimum = min(minimum, padding)
    print(f"{name}_min_horizontal_padding={padding:.1f}")
print(f"label_padding_min={minimum:.1f}")
assert minimum > 24
PY

uv run pytest packages/bluetape-resilience/tests/bluetape_resilience_tests/test_circuit.py -q
git diff --check "$base..$asset_head"
rm -f "$verify_png"
```

Fresh results were `ASSET_SCOPE_MATCH=PASS`, `xmllint=PASS`,
`cmp=BYTE_IDENTICAL`, and `3800x2200` before temporary-file removal.

| Check | Fresh result |
|---|---|
| Connector audit | `PASS markers=4 connectors=7 cards=3 intrusions=0 crossings=0` |
| Geometry `--fail-diagonal` | `geometry_failures=0` |
| Endpoint | `PASS files=1` |
| Mixed corner | `PASS files=1 paths=7 q_bends=9 failures=0` |
| Marker roles | `primary_marker_contract=3` at `14x14`; `neutral_marker_contract=1` at `10x10`; exact red/amber/olive/neutral fills=`1/1/1/1`; bindings red/amber/olive=`2/1/1`, neutral=`3` |
| Canvas and icon contracts | root/background/frame=`1/1/1`; external images/symbols=`0/0` |
| README exposure | `README_EN_STATE=1`, `README_KO_STATE=1` |
| Targeted circuit tests | `19 passed` (latest run: `0.01s`) |
| Diff hygiene | `git diff --check e6bf1e4a2503b6573f17882f0044781b8a4b4a6b..c6591d97c7f6cecf30ab44243c22b73fc554f0bf` returned no output |

Targeted XPath replaced the unavailable Bluetape state-specific audit:

| State nodes | Initial | State transitions | Rejections | Connectors | Markers | Invariant notes |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 1 | 4 | 2 | 7 | 4 | 1 |

The marker-role XPath found three primary `14x14` state-transition markers
(red, amber, olive) and one secondary `10x10` neutral marker for the initial and
two state-unchanged rejection connectors. All four use `refX=9`, `refY=5`,
`orient=auto`, `markerUnits=userSpaceOnUse`, and explicit color-matched fill
paths. Canvas contracts were `canvas_root=1` (`1900x1100`, matching viewBox),
`canvas_background=1`, and `canvas_frame=1`; external `<image>` and `<symbol>`
counts were both zero.

State claims map directly to current behavior:

| Diagram claim | Source/test mapping |
|---|---|
| Initial `CLOSED`; classified failures open at threshold | `_CircuitData.__init__`, `fail`, and `test_circuit_opens_rejects_and_lazily_recovers` |
| Pre-`open_until` admission is rejected without a transition | `_CircuitData.admit` returns `(None, None)`; the lazy-recovery test asserts `CircuitOpenError` while open |
| First admission at/after `open_until` lazily enters `HALF_OPEN` | `_CircuitData.admit` performs the transition; no timer/worker exists; the lazy-recovery test advances `FakeClock` before admission |
| `HALF_OPEN` success threshold closes; classified probe failure reopens | `_CircuitData.succeed` and `fail`; the lazy-recovery and stale-completion tests exercise the state-changing outcomes |
| Probe capacity is bounded and extra admission is rejected unchanged | `_CircuitData.admit` checks `half_open_max_calls`; `test_half_open_probe_limit_rejects_concurrent_probe` observes one in-flight probe and a rejection |
| Ignored/cancelled outcomes release slots; stale generations cannot mutate current state | `_CircuitData.ignore`, async cancellation reconciliation, and the cancellation/stale-completion tests; the generalized `failure_if=False` branch remains source-only evidence as disclosed above |

The canonical PNG was opened at original detail. Its subtitle is exactly
“Sync and async breakers share admission-driven recovery; no timer changes
state.” `CLOSED`, `OPEN`, `HALF_OPEN`, all connector labels, and the invariant
note are readable. The image visibly contains four solid state-changing
transitions with the larger primary heads and two dashed `state unchanged`
rejection routes with the smaller neutral head. All heads are solid,
color-matched, and correctly directed. Inspection found no clipping, text
overflow, overlap, connector/card intrusion, or connector crossing; outer and
inter-card whitespace are balanced. An independent PNG
pixel-bound check used the 2x canonical render, excluded an eight-SVG-unit
border inset, and masked pixels at least 28 RGB levels from the label fill. It
measured minimum horizontal label-box padding of `57.0`, `35.5`, `85.5`,
`55.5`, `42.5`, and `69.5` SVG units, so every label box exceeds the `24`-unit
floor.

Delivery boundary: this is local visual-review evidence only. It makes no push,
PR-head, CI, merge-ready, or merge claim.

## Circuit Breaker state checklist ledger

| Check | Result | Falsifiable evidence |
|---|---|---|
| DIA-01 | PASS | Canonical state SVG/PNG, both package READMEs, `_circuit.py`, `test_circuit.py`, approved state design spec, reader question, and resilience4j comparison set are listed above. Kind=`state machine`. |
| DIA-02 | PASS | Loaded Bluetape `SKILL.md` and `common.md`; Fireworks `SKILL.md` and `style-1-flat-icon.md` supply specialized UML state semantics/style. Sequence-only rules are N/A and no sequence-style audit ran. |
| DIA-03 | PASS | Review scope kept the finalized SVG read-only and treated it as the sole state asset at verified asset HEAD `c6591d97c7f6cecf30ab44243c22b73fc554f0bf`; the one-asset parse, temporary render, byte comparison, audits, and original-size inspection all completed before ledger entry. Source invariants are three states, lazy admission, four transitions, two unchanged-state rejections, bounded probes, slot release, and generation safety. |
| DIA-04 | PASS | `xmllint --noout` passed; exact CairoSVG CLI rendered the temporary `3800x2200` PNG and `cmp` reported byte identity with the canonical PNG without mutating it. |
| DIA-05 | PASS | Connector `markers=4 cards=3 connectors=7 intrusions=0 crossings=0`; geometry failures `0`; endpoint PASS; mixed corner `paths=7 q_bends=9 failures=0`; targeted state XPath=`3/1/4/2/7/4/1`. |
| DIA-06 | PASS | Original-detail inspection of the absolute `3800x2200` PNG found the exact subtitle, three readable states, readable labels/note, four transitions, two dashed rejections, solid heads, rounded corners, no clipping/overflow/overlap/intrusion/crossing, and balanced whitespace. |
| DIA-07 | PASS | Relative and absolute canonical links resolve; English and Korean READMEs each embed the state PNG once; scoped range diff check is clean. Scope stops at local visual evidence with no push, PR-head, CI, merge-ready, or merge claim. |
| DIA-08 | PASS | This ledger records commands, hashes, dimensions, audits, XPath/contracts, source/test limitations, visual notes, exposure, and all 17 physical rows. `Required checks: 16/16; N/A: 1; Blocked: 0`. |
| DIA-COM-01 | PASS | Target README prose, `_circuit.py`, `test_circuit.py`, approved design spec, related resilience4j module/assets, and source mapping are enumerated above; `failure_if=False` is explicitly limited to source-only branch evidence. |
| DIA-COM-02 | PASS | Original PNG shows `Architects Daughter` title/state names and `Comic Mono` technical text; exact subtitle, state summaries, transition/rejection labels, and invariant note are legible with no evidence logs inside the art. Minimum measured label-box padding is `35.5` SVG units, above `24`. |
| DIA-COM-03 | N/A | The approved state design requires text-only states and no decorative/infrastructure icons. XPath reports `<image>=0` and `<symbol>=0`, so there is no external-image, invented-logo, or duplicate-icon surface. |
| DIA-COM-04 | PASS | XPath finds three primary `14x14` state-transition markers and one secondary `10x10` neutral initial/rejection marker. All use fixed `userSpaceOnUse`, `refX=9`, `refY=5`, `orient=auto`, and explicit color-matched fills; bindings are red/amber/olive=`2/1/1` and neutral=`3`. Original PNG shows solid, correctly directed heads with the intended role-size distinction. |
| DIA-COM-05 | PASS | Connector audit reports `connectors=7 cards=3 intrusions=0 crossings=0`; geometry `--fail-diagonal` has `0` failures and endpoint audit PASS; original PNG shows perpendicular boundary attachment and no floating/corner-hugging routes. |
| DIA-COM-06 | PASS | Mixed-corner audit is meaningfully nonzero: `paths=7 q_bends=9 failures=0`; original PNG shows rounded orthogonal bends with clear terminal segments and no remaining hard mixed corner. |
| DIA-COM-07 | PASS | Root/canvas/frame contracts are each exactly `1`: SVG/viewBox `1900x1100`, PNG `3800x2200`, white background, bounded inset frame. Original inspection found balanced outer, card, label, note, and footer-free whitespace. |
| DIA-COM-08 | PASS | The executable block above reproduces fresh asset-scope binding, XML, temporary CairoSVG render, byte comparison, dimensions, all four audits, state/marker/canvas XPath, hashes, exposure, exact Pillow padding analysis, targeted `19 passed`, and scoped range diff results with nonzero counts and zero failures. |
| DIA-COM-09 | PASS | Review links target the current worktree's canonical state SVG/PNG; both files exist, hashes are recorded, and each locale embeds the PNG exactly once. |

Circuit Breaker state final: `Required checks: 16/16; N/A: 1; Blocked: 0`.

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
| DIA-08 | PASS | This ledger records paths, hashes, commands, dimensions, audit counts, fallback counts, references, and visual notes across 23 physical rows. `Required checks: 21/21; N/A: 2; Blocked: 0`. |
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
| DIA-08 | PASS | This ledger records paths, hashes, commands, dimensions, audit counts, fallback counts, references, and visual notes across 23 physical rows. `Required checks: 21/21; N/A: 2; Blocked: 0`. |
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
