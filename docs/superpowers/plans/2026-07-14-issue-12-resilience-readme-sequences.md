# Issue #12 Resilience README Sequences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add independently reviewable sync and async resilience pipeline sequence diagrams to both package README locales.

**Architecture:** Complete one hand-authored SVG -> CairoSVG 2x PNG -> audits -> original-size inspection loop before starting the next asset. Python `_pipeline.py` and tests own behavior; resilience4j assets provide ecosystem comparison and README placement only.

**Tech Stack:** SVG 1.1, CairoSVG CLI, xmllint, Bluetape diagram audit scripts, Markdown, Git

---

## File Map

- Create `docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg` and matching PNG.
- Create `docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg` and matching PNG.
- Create `docs/review/2026-07-14-issue-12-resilience-diagram-review.md`.
- Modify `packages/bluetape-resilience/README.md` and `README.ko.md`.
- Do not modify production Python, tests, package metadata, root READMEs, dependencies, or unrelated assets.

### Task 1: Freeze Source And Visual Authorities

**Files:**
- Read: `packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py`
- Read: `packages/bluetape-resilience/tests/bluetape_resilience_tests/test_pipeline.py`
- Read: `packages/bluetape-resilience/README.md`
- Read: `packages/bluetape-resilience/README.ko.md`
- Read: `/Users/debop/work/bluetape4k/bluetape4k-projects/infra/resilience4j/README.md`

- [ ] **Step 1: Confirm worktree and composition behavior**

```bash
git status -sb
git rev-parse HEAD
rg -n 'for policy in self\._policies|with_retry|with_circuit_breaker|with_bulkhead|with_timeout' \
  packages/bluetape-resilience/src/bluetape/resilience/_pipeline.py \
  packages/bluetape-resilience/tests/bluetape_resilience_tests/test_pipeline.py
```

Expected: clean feature branch; append-order builders and runtime iteration prove last-added-is-outermost; timeout exists only for async.

- [ ] **Step 2: Open visual authorities at original size**

```text
/Users/debop/work/bluetape4k/bluetape4k-wiki/docs/diagrams/best-practices/assets/sequence-workflow-sample.png
/Users/debop/work/bluetape4k/clinic-appointment/docs/images/readme-diagrams/appointment-api-sequence-01.png
/Users/debop/work/bluetape4k/bluetape4k-projects/docs/images/readme-diagrams/infra-resilience4j-sequence-01.png
```

Expected: record catalog palette/message rules, README density, and resilience lifecycle separately.

### Task 2: Build And Close The Sync Asset

**Files:**
- Create: `docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg`
- Create: `docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png`

- [ ] **Step 1: Create the `1900x1180` sync SVG**

```text
Title: Synchronous Resilience Pipeline
Participants: Caller | ResiliencePipeline | Bulkhead | Retry | CircuitBreaker | Operation
Configured: with_circuit_breaker -> with_retry -> with_bulkhead
Runtime: Bulkhead -> Retry -> CircuitBreaker -> Operation
1 call decorated function or pipeline.call()
2 acquire bounded permit
3 begin attempt [loop up to max_attempts]
4 admit when circuit is CLOSED or HALF_OPEN
5 execute operation
6 return value or classified failure
7 retry retryable failure after backoff
8 record final outcome and release permit
9 return value or domain failure
Footer: Sync timeout is intentionally absent; no hidden worker owns the call.
```

Use `Architects Daughter` headings, `Comic Mono` technical text, dashed lifelines, activations, transparent loop/alt frames, and explicit blue/olive/amber/teal/red `16x16` markers with `markerUnits="userSpaceOnUse"`. Every message has a numbered pill above a continuous horizontal line.

- [ ] **Step 2: Parse, render, and measure**

```bash
xmllint --noout docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
cairosvg docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg -o docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png -s 2
sips -g pixelWidth -g pixelHeight docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png
```

Expected: XML PASS and `3800x2360` PNG.

- [ ] **Step 3: Run all five audits**

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" --fail-diagonal docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-sequence-style-audit.py" docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
```

Expected: meaningful nonzero cards/connectors/markers/activations/labels/frames and failures=0. Replace weak generic counts with targeted `xmllint --xpath 'count(...)'` proof against explicit SVG classes.

- [ ] **Step 4: Inspect and commit**

At original size confirm nine ordered labels, color-matched solid heads, transparent frames, no overlap/intrusion/clipping, readable footer, and balanced margins. Any contradiction returns to Step 1 and reruns all proof.

```bash
git add docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png
git commit -m "docs: add sync resilience sequence"
```

### Task 3: Build And Close The Async Asset

**Files:**
- Create: `docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg`
- Create: `docs/images/readme-diagrams/bluetape-resilience-async-sequence.png`

- [ ] **Step 1: Create the `2100x1380` async SVG**

```text
Title: Asynchronous Resilience Pipeline
Participants: Caller | AsyncResiliencePipeline | AsyncBulkhead | AsyncTimeout | AsyncRetry | AsyncCircuitBreaker | Async Operation
Configured: with_circuit_breaker -> with_retry -> with_timeout -> with_bulkhead
Runtime: AsyncBulkhead -> AsyncTimeout -> AsyncRetry -> AsyncCircuitBreaker -> Async Operation
1 await decorated function or pipeline.call()
2 acquire bounded permit
3 enter asyncio.timeout() scope
4 begin attempt [loop up to max_attempts]
5 admit when circuit is CLOSED or HALF_OPEN
6 await operation
7 return value or classified failure
8 retry retryable failure after async backoff
9a success: record outcome, exit timeout scope, release permit
9b policy timeout: raise PolicyTimeoutError after cleanup
9c external cancellation: propagate CancelledError unchanged after cleanup
10 return value or terminal failure
Footer: No detached task, reset scheduler, unbounded queue, or package-owned logger.
```

Reuse sync visual tokens. Put success, policy-timeout, and external-cancellation branches inside one transparent padded alt frame.

- [ ] **Step 2: Parse, render, and measure**

```bash
xmllint --noout docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
cairosvg docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg -o docs/images/readme-diagrams/bluetape-resilience-async-sequence.png -s 2
sips -g pixelWidth -g pixelHeight docs/images/readme-diagrams/bluetape-resilience-async-sequence.png
```

Expected: XML PASS and `4200x2760` PNG.

- [ ] **Step 3: Run all five async audits**

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" --fail-diagonal docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-sequence-style-audit.py" docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
```

Expected: meaningful nonzero cards/connectors/markers/activations/labels/frames and failures=0. Add targeted XPath proof for any unsupported generic count.

- [ ] **Step 4: Inspect and commit**

At original size verify timeout/cancellation distinction, reverse cleanup, numbered-row clearance, marker parity, transparent frame padding, readable footer, and balanced whitespace. Any contradiction returns to Step 1 and reruns XML, render, dimensions, and all five audits.

```bash
git add docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg docs/images/readme-diagrams/bluetape-resilience-async-sequence.png
git commit -m "docs: add async resilience sequence"
```

### Task 4: Embed Both Assets In Both Package READMEs

**Files:**
- Modify: `packages/bluetape-resilience/README.md`
- Modify: `packages/bluetape-resilience/README.ko.md`

- [ ] **Step 1: Add the English section before `## Synchronous use`**

```markdown
## How policy composition executes

Each `.with_*()` returns a new pipeline. At runtime the last-added policy is
the outermost wrapper and runs first; cleanup unwinds in reverse order.

### Synchronous pipeline

![Synchronous resilience pipeline sequence](../../docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png)

The synchronous pipeline composes bulkhead, retry, and circuit-breaker policies.
It deliberately has no timeout because the package does not own a worker that
could safely outlive or preempt the call.

### Asynchronous pipeline

![Asynchronous resilience pipeline sequence](../../docs/images/readme-diagrams/bluetape-resilience-async-sequence.png)

The asynchronous pipeline adds cooperative `asyncio.timeout()` handling.
Policy-owned timeout becomes `PolicyTimeoutError`, while external cancellation
propagates unchanged after cleanup.
```

- [ ] **Step 2: Add the Korean parity section before `## 동기 사용`**

```markdown
## Policy 조합 실행 순서

각 `.with_*()`는 새 pipeline을 반환합니다. 실행 시 마지막에 추가한 policy가
가장 바깥 wrapper가 되어 먼저 실행되고, cleanup은 반대 순서로 진행됩니다.

### 동기 pipeline

![동기 resilience pipeline sequence](../../docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png)

동기 pipeline은 bulkhead, retry, circuit breaker policy를 조합합니다. 호출보다
오래 살거나 호출을 선점할 수 있는 worker를 패키지가 소유하지 않으므로 timeout은
의도적으로 제공하지 않습니다.

### 비동기 pipeline

![비동기 resilience pipeline sequence](../../docs/images/readme-diagrams/bluetape-resilience-async-sequence.png)

비동기 pipeline은 cooperative `asyncio.timeout()` 처리를 추가합니다. Policy가
소유한 timeout은 `PolicyTimeoutError`가 되고, 외부 cancellation은 cleanup 뒤에도
변경 없이 전파됩니다.
```

- [ ] **Step 3: Verify and commit README exposure**

```bash
rg -n 'bluetape-resilience-(sync|async)-sequence\.png|last-added|마지막에 추가한' packages/bluetape-resilience/README.md packages/bluetape-resilience/README.ko.md
test -f docs/images/readme-diagrams/bluetape-resilience-sync-sequence.png
test -f docs/images/readme-diagrams/bluetape-resilience-async-sequence.png
git diff --check -- packages/bluetape-resilience/README.md packages/bluetape-resilience/README.ko.md
git add packages/bluetape-resilience/README.md packages/bluetape-resilience/README.ko.md
git commit -m "docs: explain resilience pipeline execution"
```

Expected: each README embeds both shared PNGs once and locale structure aligns.

### Task 5: Record Falsifiable Diagram Evidence

**Files:**
- Create: `docs/review/2026-07-14-issue-12-resilience-diagram-review.md`

- [ ] **Step 1: Write separate sync and async ledgers**

For each asset record absolute paths, reader question, source files, all visual references, kind, XML result, exact CairoSVG command, dimensions, all audit outputs, fallback counts, and original-size inspection notes. Render DIA-01..08, DIA-COM-01..09, and DIA-SEQ-01..06 separately. Every PASS row includes observed numbers or a concrete path/result; never use `checklist passed` as evidence.

- [ ] **Step 2: Final verification and evidence commit**

```bash
xmllint --noout docs/images/readme-diagrams/bluetape-resilience-sync-sequence.svg
xmllint --noout docs/images/readme-diagrams/bluetape-resilience-async-sequence.svg
git diff --check
rg -n 'bluetape-resilience-(sync|async)-sequence\.png' packages/bluetape-resilience/README.md packages/bluetape-resilience/README.ko.md
git add docs/review/2026-07-14-issue-12-resilience-diagram-review.md
git commit -m "docs: record resilience diagram review"
```

### Task 6: Stop For User Full-Size Review

- [ ] **Step 1: Verify local completion**

```bash
git status -sb
git log -5 --oneline
```

Expected: clean worktree with local commits ahead of the existing PR head.

- [ ] **Step 2: Provide absolute paths and wait**

Provide all four absolute SVG/PNG paths, dimensions, audit counts, and inspection notes. Do not push, update PR #71, report merge-ready, or merge before the user's visual verdict.

### Task 7: Publish Only After User Visual Approval

- [ ] **Step 1: Push and refresh PR #71**

After explicit visual approval, push without force, compare local/remote/PR head SHAs, and update PR validation/DoD rows with asset paths, dimensions, audit counts, and user review decision.

- [ ] **Step 2: Re-run live delivery gates**

Verify final PR heading `## DoD Status`, wait for exact-head CI, reread reviews/comments/threads, and report CG-14/CG-15 evidence. Stop at CG-16 for fresh merge approval; never enable auto-merge.
