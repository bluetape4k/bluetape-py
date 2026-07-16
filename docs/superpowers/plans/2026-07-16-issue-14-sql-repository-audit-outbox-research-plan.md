# Issue #14 SQL, Repository, Audit, and Outbox Research Plan

> **For Codex:** Execute tasks in order. The PostgreSQL spike is disposable evidence, not repository implementation.

**Goal:** Decide Python-native SQL, repository, audit, outbox, and Testcontainers boundaries with official-source evidence and one real PostgreSQL proof, then turn the decision into durable documentation and non-overlapping follow-up issues.

**Architecture:** Keep application code as the transaction owner. Evaluate Psycopg as the DB-API baseline and SQLAlchemy Core as the candidate shared sync/async expression layer. Keep audit contracts storage-neutral and place durable claim/relay behavior in a PostgreSQL-specific outbox adapter with caller-driven execution.

**Tools:** Python 3.13, `uv`, Psycopg 3, SQLAlchemy 2, asyncpg, Testcontainers Python, PostgreSQL 18, GitHub CLI.

---

## Task 1: Lock the evidence ledger

**Files:**

- Read: `docs/superpowers/specs/2026-07-16-issue-14-sql-repository-audit-outbox-research-design.md`
- Read: `WIP.md`
- Read: `docs/package-layout.md`
- Read: sibling `bluetape-go` SQL/audit/outbox research, specs, and lessons
- Create later: `docs/research/2026-07-16-issue-14-sql-repository-audit-outbox-strategy.md`

1. Recheck issue #14, milestone, labels, assignee, #25, #30, and related Testcontainers issues live.
2. Verify official PEP 249, Psycopg, SQLAlchemy Core/asyncio/PostgreSQL dialect, asyncpg, PostgreSQL locking/isolation, and Testcontainers PostgreSQL URLs.
3. Record source version or retrieval date when the source exposes one.
4. Do not infer production behavior from sibling APIs; use them only for transaction and delivery semantics.

## Task 2: Run the disposable PostgreSQL spike

**Files:**

- Create outside repository: `/tmp/bluetape-issue14-spike/spike.py`
- Do not modify: `pyproject.toml`, `uv.lock`, `packages/`, `.github/workflows/`

1. Check Docker availability before acquiring dependencies or starting the container.
2. Write one self-contained spike with three tables and bounded JSON output.
3. Run exactly one serial command using temporary dependencies:

   ```bash
   uv run --no-project \
     --with 'testcontainers[postgres]' \
     --with 'psycopg[binary]' \
     --with 'sqlalchemy[asyncio]' \
     --with asyncpg \
     python /tmp/bluetape-issue14-spike/spike.py
   ```

4. Require PASS for Psycopg commit/mapping, Psycopg rollback, SQLAlchemy sync commit/mapping, SQLAlchemy sync rollback, SQLAlchemy async commit/mapping, SQLAlchemy async rollback, and concurrent `SKIP LOCKED` claim.
5. Allow one rerun only for container-start or dependency-acquisition failure. A semantic failure remains visible and blocks the affected recommendation.
6. Capture only resolved versions, image tag, proof booleans, bounded identifiers/counts, duration, and sanitized failure category. Do not preserve credentials, connection URLs, raw logs, or spike source in the repository.

Execution note: the first run's plain `sqlalchemy` dependency omitted
SQLAlchemy's declared asyncio runtime extra and failed before the async
candidate could execute. This was classified as dependency-environment
acquisition/configuration, not a semantic proof failure. The single allowed
retry used `sqlalchemy[asyncio]`; no assertion or spike behavior changed.

## Task 3: Write the research decision

**Files:**

- Create: `docs/research/2026-07-16-issue-14-sql-repository-audit-outbox-strategy.md`
- Modify: `docs/research/README.md`
- Modify: `docs/research/README.ko.md`
- Modify: `WIP.md`
- Modify: `docs/package-layout.md`

1. Lead with the selected production boundaries and state which hypotheses the spike supported or rejected.
2. Include a candidate matrix for Psycopg DB-API, SQLAlchemy Core sync, SQLAlchemy async, and direct asyncpg.
3. Define caller-owned transaction rules and explicit mapping rules without promising a generic repository base class.
4. Split storage-neutral audit contracts from PostgreSQL outbox behavior.
5. Document at-least-once delivery, duplicate possibility, bounded `SKIP LOCKED` claiming, caller-driven relay, and absence of hidden workers.
6. Specify the minimum PostgreSQL Testcontainers fixture boundary without implementing it.
7. Include rejected alternatives, follow-up mapping, sources, resolved versions, exact spike command, results, limitations, and retrieval notes.
8. Keep English/Korean research index entries semantically aligned.

## Task 4: Preserve external research in the wiki

**Files:**

- Create: `/Users/debop/work/bluetape4k/bluetape4k-wiki/research/2026-07-16-python-sql-audit-outbox-strategy.md`

1. Write a copyright-safe Korean summary with source URLs, retrieval metadata, decisions, bluetape-py implications, adoption notes, and an `Assets` section stating that no images were required.
2. Run `git diff --check` in the wiki.
3. Run `gno update`, `gno embed --collection bluetape4k-wiki`, and a representative `gno search`.
4. Commit and push the wiki change because the approved design requires durable preservation.

## Task 5: Reconcile follow-up issues

**External targets:**

- SQL toolkit/repository boundary
- Storage-neutral audit model
- PostgreSQL transactional outbox
- Existing #25 and #30

1. Search live open issues for duplicates before creating or editing anything.
2. Reuse, narrow, or split #25/#30 so each implementation issue has one package boundary and explicit non-goals.
3. Preserve milestone `0.2.0`, assignee `debop`, relevant labels, and links back to #14.
4. Write all public GitHub issue content in English.
5. Verify the three final issue URLs and their live metadata.

## Task 6: Review and verify the documentation branch

**Files:**

- Create: `docs/review/2026-07-16-issue-14-sql-repository-audit-outbox-research-review.md`
- Create conditionally: `docs/lessons/2026-07-16-issue-14-sql-repository-audit-outbox.md`

1. Review factual claims against official sources, spike output, local paths, and sibling paths.
2. Run a separate P0/P1 review and fix every P0/P1 finding.
3. Evaluate the lesson gate. Commit a lesson only if the task produced reusable failure, recovery, design, or operational guidance not already captured by the existing caller-owned transaction and disposable-research rules; otherwise document evidence-backed `N/A` in the review.
4. Run:

   ```bash
   git diff --check
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest packages/bluetape/tests/test_value_readmes.py -q
   ```

5. Confirm that `pyproject.toml`, `uv.lock`, `packages/`, and workflows are unchanged.
6. Commit with the Lore protocol and record the exact local head SHA.

## Task 7: Deliver the exact-head PR

**Target:** `bluetape4k/bluetape-py`, base `develop`, head `research/issue-14-sql-audit-outbox`

1. Read `bluetape-workflow/templates/pr-body-step-dod.md`.
2. Push the exact converged branch and verify local/remote head equality.
3. Create or update the PR, assign `debop`, mirror milestone and labels, and end the body with `## DoD Status`.
4. Verify live PR metadata and final heading.
5. Wait for exact-head CI, reread reviews and threads, and report merge-ready evidence.
6. Stop for fresh merge approval. Do not enable auto-merge and do not merge based on the current spec/execution approval.
