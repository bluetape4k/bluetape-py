# Issue #12 Circuit Breaker State Diagram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one source-backed Circuit Breaker state diagram to both `bluetape-resilience` README locales and record falsifiable visual evidence.

**Architecture:** Hand-author one shared UML-style SVG for the `_CircuitData` state model, render its canonical PNG with CairoSVG at 2x, and close the complete audit plus original-size inspection loop before exposing it in either README. Keep runtime sequence assets unchanged; the new asset explains lifecycle only.

**Tech Stack:** SVG 1.1, CairoSVG CLI, xmllint, Bluetape diagram audit scripts, XPath invariants, Markdown, Git

---

## File Map

- Create `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg`: canonical editable state-machine source.
- Create `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png`: exact CairoSVG 2x README render.
- Modify `packages/bluetape-resilience/README.md`: English state-model section and shared PNG embed.
- Modify `packages/bluetape-resilience/README.ko.md`: Korean claim-parity section and the same shared PNG embed.
- Modify `docs/review/2026-07-14-issue-12-resilience-diagram-review.md`: state asset paths, hashes, commands, audit counts, checklist ledger, and visual inspection evidence.
- Do not modify production Python, tests, package metadata, root READMEs, dependencies, existing sequence assets, or PR state.

### Task 1: Reconfirm The State Contract And Worktree Boundary

**Files:**
- Read: `docs/superpowers/specs/2026-07-14-issue-12-circuit-breaker-state-design.md`
- Read: `packages/bluetape-resilience/src/bluetape/resilience/_circuit.py`
- Read: `packages/bluetape-resilience/tests/bluetape_resilience_tests/test_circuit.py`
- Read: `packages/bluetape-resilience/README.md`
- Read: `packages/bluetape-resilience/README.ko.md`

- [ ] **Step 1: Verify the approved branch and clean start**

```bash
git status -sb
git rev-parse HEAD
git merge-base --is-ancestor develop HEAD
```

Expected: branch `feat/issue-12-resilience-policies`, clean worktree, approved plan commit at `HEAD`, and exit status `0` from the merge-base check.

- [ ] **Step 2: Reconfirm every drawn transition from source**

```bash
rg -n 'state = CircuitState.CLOSED|now < self.open_until|CircuitState.HALF_OPEN|half_open_in_flight >=|recovery_successes >=|CircuitState.OPEN|def ignore|generation !=' \
  packages/bluetape-resilience/src/bluetape/resilience/_circuit.py
rg -n 'lazy|half.open|cancel|ignored|CircuitOpenError|generation' \
  packages/bluetape-resilience/tests/bluetape_resilience_tests/test_circuit.py
```

Expected: source and tests prove initial `CLOSED`, threshold opening, pre-deadline rejection, admission-driven `OPEN → HALF_OPEN`, bounded probes, recovery close, classified-failure reopen, ignored/cancelled slot release, and generation safety.

- [ ] **Step 3: Freeze the visual invariant inventory**

```text
State nodes: CLOSED | OPEN | HALF_OPEN
Initial node: one filled circle -> CLOSED
State-changing transitions:
  CLOSED -> OPEN: classified failures >= failure_threshold
  OPEN -> HALF_OPEN: next admission after open_duration (lazy)
  HALF_OPEN -> CLOSED: recovery_successes >= recovery_success_threshold
  HALF_OPEN -> OPEN: any classified probe failure
Non-transitioning decisions:
  OPEN -> OPEN: before open_until, reject CircuitOpenError
  HALF_OPEN -> HALF_OPEN: in-flight >= half_open_max_calls, reject CircuitOpenError
Invariant note:
  ignored exception or cancellation releases the probe slot without counting;
  stale-generation outcomes cannot mutate current state
```

Expected: no automatic timer edge, final state, RateLimiter/cache/fallback state, sync/async split, or wrapper-order chronology enters the asset.

### Task 2: Build The Canonical State Asset

**Files:**
- Create: `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg`
- Create: `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png`

- [ ] **Step 1: Create the `1900x1100` SVG canvas and semantic groups**

Use this exact content inventory and class/id contract so audits can count semantics without guessing:

```text
Title: Circuit Breaker State Model
Subtitle: Sync and async breakers share admission-driven recovery; no timer changes state.

Group id=initial-state, class=initial-node: filled initial circle
Group id=state-closed, class=state-node: CLOSED card and its three behavior lines
Group id=state-open, class=state-node: OPEN card and its three behavior lines
Group id=state-half-open, class=state-node: HALF_OPEN card and its three behavior lines

Path id=transition-closed-open, class=connector state-transition
Path id=transition-open-half-open, class=connector state-transition
Path id=transition-half-open-closed, class=connector state-transition
Path id=transition-half-open-open, class=connector state-transition
Path id=rejection-open, class=connector rejection-decision
Path id=rejection-half-open, class=connector rejection-decision
Path id=initial-closed, class=connector initial-transition

Group id=invariant-note, class=invariant-note: ignored/cancelled slot release and generation safety
```

Use a white/light-blue canvas, rounded state cards, `Architects Daughter` for the title and state names, and `Comic Mono` for technical labels. Reuse the established muted palette: blue `#4F83BF`, red `#A95D61`, amber `#A97924`, teal `#2E8F89`, olive `#64834A`, and neutral `#41545D`. Do not add filters, shadows, gradients, external images, or icons.

- [ ] **Step 2: Populate each state card with source-backed internal behavior**

```text
CLOSED
  admit calls
  success -> consecutive_failures = 0
  classified failure -> increment counter

OPEN
  reject before open_until
  entering state sets open_until = now + open_duration
  no background timer or worker

HALF_OPEN
  bounded concurrent probes
  success -> increment recovery_successes
  ignored/cancelled outcome -> release slot, do not count
```

Keep each line inside its card with at least 24 SVG units of inner padding. Put the lazy-admission label directly beside `OPEN → HALF_OPEN`, and place both rejection labels beside their self-loops without crossing a card boundary.

- [ ] **Step 3: Route seven labeled connectors without crossings or card intrusion**

Place `CLOSED` left, `OPEN` upper-right, and `HALF_OPEN` lower-right. Use four explicit fixed markers with `markerWidth="13"`, `markerHeight="13"`, `refX="9"`, `refY="5"`, `orient="auto"`, and `markerUnits="userSpaceOnUse"`. Every connector uses `fill="none"`, color-matched stroke/marker, rounded caps and joins, and terminates at a state-card edge or initial node.

Use one consistent bend language for routed paths. If a route bends, use quadratic `Q` segments throughout that route; do not mix hard `L/H/V` elbows and rounded bends in the same connector. Keep the four state-changing labels visually primary and the two rejection labels secondary.

- [ ] **Step 4: Parse, render, and measure**

```bash
xmllint --noout docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
cairosvg docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg -o docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png -s 2
sips -g pixelWidth -g pixelHeight docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png
```

Expected: XML PASS and `3800x2200` PNG.

### Task 3: Close Automated And Visual Validation Before README Edits

**Files:**
- Verify: `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg`
- Verify: `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png`

- [ ] **Step 1: Run the four applicable common audits**

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" --fail-diagonal docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
```

Expected: meaningful nonzero card/connector/marker counts; `intrusions=0`, `crossings=0`, endpoint PASS, geometry failures `0`, and mixed-corner failures `0`. The sequence-style audit is intentionally not run because this asset has no participants, lifelines, activations, messages, or chronological frames.

- [ ] **Step 2: Prove state semantics with targeted XPath counts**

```bash
svg=docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
xmllint --xpath 'count(//*[contains(concat(" ",normalize-space(@class)," ")," state-node ")])' "$svg"
xmllint --xpath 'count(//*[contains(concat(" ",normalize-space(@class)," ")," initial-node ")])' "$svg"
xmllint --xpath 'count(//*[contains(concat(" ",normalize-space(@class)," ")," state-transition ")])' "$svg"
xmllint --xpath 'count(//*[contains(concat(" ",normalize-space(@class)," ")," rejection-decision ")])' "$svg"
xmllint --xpath 'count(//*[contains(concat(" ",normalize-space(@class)," ")," connector ")])' "$svg"
xmllint --xpath 'count(//*[local-name()="marker"])' "$svg"
xmllint --xpath 'count(//*[@id="invariant-note"])' "$svg"
```

Expected outputs in order: `3`, `1`, `4`, `2`, `7`, `4`, `1`.

- [ ] **Step 3: Prove required and forbidden claims**

```bash
svg=docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
rg -n 'CLOSED|OPEN|HALF_OPEN|failure_threshold|open_duration|lazy|half_open_max_calls|recovery_success_threshold|CircuitOpenError|cancel|generation' "$svg"
if rg -n 'automatic timer|background scheduler|RateLimiter|cache|fallback|final state' "$svg"; then exit 1; fi
```

Expected: every required state/threshold/invariant term is present; the forbidden-claim check produces no output and exits successfully.

- [ ] **Step 4: Inspect the final PNG at original size**

Open `docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png` with original detail after the last coordinate change. Verify:

```text
three state names and all threshold labels are legible;
lazy admission cannot be mistaken for an automatic timer;
seven arrowheads match their connector colors and destinations;
both rejection loops visibly remain in the same state;
no label touches a connector, card, title, subtitle, or invariant note;
no connector crosses another connector or enters a card except at its endpoint;
outer margins are balanced and no region is clipped or excessively empty
```

Any contradiction returns to Task 2 Step 1, rerenders the PNG, reruns all four audits and XPath proofs, and repeats original-size inspection.

- [ ] **Step 5: Commit the closed asset loop**

```bash
git add docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg \
  docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png
git commit -m "docs: add circuit breaker state diagram"
```

Expected: exactly the SVG and PNG are committed; the worktree is clean before README work begins.

### Task 4: Add Locale-Equivalent README Sections

**Files:**
- Modify: `packages/bluetape-resilience/README.md`
- Modify: `packages/bluetape-resilience/README.ko.md`

- [ ] **Step 1: Add the English section before `## How policy composition executes`**

```markdown
## Circuit Breaker state model

![Circuit Breaker state transitions](../../docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png)

Synchronous and asynchronous breakers share this state model. While `OPEN`,
admissions fail with `CircuitOpenError`. After `open_duration`, the next
admission lazily enters `HALF_OPEN`; no timer or background worker changes the
state. Enough successful probes close the circuit, while any classified probe
failure reopens it. Ignored exceptions and cancellation release an owned probe
slot without counting as success or failure.
```

- [ ] **Step 2: Add the Korean parity section before `## Policy 조합 실행 순서`**

```markdown
## Circuit Breaker 상태 모델

![Circuit Breaker 상태 전이](../../docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png)

동기와 비동기 breaker는 이 상태 모델을 공유합니다. `OPEN` 상태에서는 admission이
`CircuitOpenError`로 실패합니다. `open_duration`이 지난 뒤 다음 admission이
lazy 방식으로 `HALF_OPEN`에 진입하며 timer나 background worker가 상태를 바꾸지
않습니다. 충분한 probe가 성공하면 circuit이 닫히고, classified probe failure가
하나라도 발생하면 다시 열립니다. 무시한 exception과 cancellation은 소유한 probe
slot을 반환하지만 success나 failure로 계산하지 않습니다.
```

- [ ] **Step 3: Verify exposure and claim parity**

```bash
test "$(rg -c 'bluetape-resilience-circuit-breaker-state\.png' packages/bluetape-resilience/README.md)" -eq 1
test "$(rg -c 'bluetape-resilience-circuit-breaker-state\.png' packages/bluetape-resilience/README.ko.md)" -eq 1
rg -n 'open_duration|HALF_OPEN|timer|background worker|Ignored exceptions|cancellation' packages/bluetape-resilience/README.md
rg -n 'open_duration|HALF_OPEN|timer|background worker|무시한 exception|cancellation' packages/bluetape-resilience/README.ko.md
git diff --check -- packages/bluetape-resilience/README.md packages/bluetape-resilience/README.ko.md
```

Expected: the shared PNG appears once per locale, both prose blocks preserve all six claims, and `git diff --check` produces no output.

- [ ] **Step 4: Commit README exposure**

```bash
git add packages/bluetape-resilience/README.md packages/bluetape-resilience/README.ko.md
git commit -m "docs: explain circuit breaker state transitions"
```

### Task 5: Extend The Diagram Review Ledger

**Files:**
- Modify: `docs/review/2026-07-14-issue-12-resilience-diagram-review.md`

- [ ] **Step 1: Add state-asset authorities and canonical paths**

Record the second reader question, `_circuit.py` and circuit tests as behavior authorities, the approved state-machine design, Bluetape common rules, Fireworks state-machine semantics, and the resilience4j module as an ecosystem comparison. Add relative and absolute SVG/PNG paths plus both SHA-256 hashes.

Update the headline without weakening existing sequence evidence:

```text
Result: PASS (sync sequence 23/23, async sequence 23/23, Circuit Breaker state 17/17, Blocked=0)
```

- [ ] **Step 2: Record falsifiable state validation**

Add the exact CairoSVG command, `3800x2200` dimensions, four audit outputs, XPath counts `3/1/4/2/7/4/1`, README exposure counts `1/1`, and the final original-size inspection observations. Render `DIA-01..08` and `DIA-COM-01..09` as a 17-row state checklist; use `N/A` only for icon or bend checks with concrete absence evidence.

- [ ] **Step 3: Verify and commit the ledger**

```bash
shasum -a 256 docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg \
  docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png
rg -n 'Circuit Breaker state|3800x2200|3/1/4/2/7/4/1|DIA-COM-09' \
  docs/review/2026-07-14-issue-12-resilience-diagram-review.md
git diff --check
git add docs/review/2026-07-14-issue-12-resilience-diagram-review.md
git commit -m "docs: record circuit breaker diagram review"
```

Expected: hashes match current canonical assets, the state ledger contains all 17 rows, and the repository diff check produces no output.

### Task 6: Verify Current HEAD And Stop For Human Review

**Files:**
- Verify all files listed in the File Map.

- [ ] **Step 1: Run proportional repository checks**

```bash
xmllint --noout docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
cairosvg docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg -o /tmp/bluetape-resilience-circuit-breaker-state-verification.png -s 2
cmp docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png /tmp/bluetape-resilience-circuit-breaker-state-verification.png
uv run pytest packages/bluetape-resilience -q
git diff --check
git status -sb
```

Expected: XML PASS, rendered verification PNG byte-identical to the committed PNG, `144 passed`, no diff-check output, and a clean local branch ahead of the existing remote/PR head.

- [ ] **Step 2: Provide absolute asset paths and wait**

Provide these two absolute paths, dimensions, audit counts, XPath counts, and inspection notes:

```text
/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.svg
/Users/debop/work/bluetape4k/bluetape-py/.worktrees/feat-issue-12-resilience-policies/docs/images/readme-diagrams/bluetape-resilience-circuit-breaker-state.png
```

Do not push, update draft PR #71, report merge-ready, or merge before the user's visual verdict.

### Task 7: Publish Only After Explicit Visual Approval

- [ ] **Step 1: Push without force and reconcile heads**

After the user approves the local state asset, push the feature branch without force. Compare local, remote, and draft PR #71 head SHAs before updating the PR validation and DoD rows with asset paths, dimensions, audit counts, and the visual-review decision.

- [ ] **Step 2: Re-run live delivery gates**

Wait for exact-head CI, reread reviews/comments/threads, verify the final PR body ends with `## DoD Status`, and report current CG-14/CG-15 evidence. Stop at CG-16 for a fresh merge approval; never enable auto-merge.
