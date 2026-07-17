# Issue #15 Testcontainers Fixture Families Plan Review

## Scope

- Artifact: `docs/superpowers/plans/2026-07-17-issue-15-testcontainers-fixtures-plan.md`
- Basis: approved issue #15 design, current Redis implementation/tests, package metadata, CI, both README locales, and workspace/repository guidance
- Gate: Type A Step 3-R, including risk prediction because the change crosses external providers, Docker networking, credentials, dependency extras, and cleanup ownership
- Heavy commands: none; this review is plan-only

## Review execution

Performance and Operator/Ops ran as independent read-only native review tasks.
User/caller ran as a distinct, bounded native follow-up task. The Stability and
Security native tasks exceeded their bounded review windows twice and were
interrupted; a fresh Developer/API task could not be allocated because the
native child-thread limit was reached. Under the workflow model-routing
fallback, the main session performed those three local equivalents and records
the unavailable/stalled roles explicitly rather than inventing agent evidence.

## Integrated findings and repairs

| Initial priority | Lens | Evidence | Required repair | Resolution |
| --- | --- | --- | --- | --- |
| P1 | Performance | Risk table and Task 5 had provider phases outside supported wrapper timeouts but no workflow cap | Add a whole-job cap without claiming a wrapper total deadline | Added `timeout-minutes: 30`, exact validation, and step-aware timeout triage |
| P1 | Stability | Lifecycle tests covered control-flow cleanup success but not the approved `STARTING -> CLEANUP_FAILED -> CLOSED` path with a primary `BaseException` | Prove the primary exception, retained cleanup state, retry, and terminal close | Added PostgreSQL and LocalStack control-flow-plus-cleanup-failure tests |
| P1 | Security | Image validation could accept credential-bearing input containing a later valid-looking digest | Parse exactly one digest separator and validate a complete SHA-256 digest without echoing input | Added crafted credential-plus-digest rejection and valid digest acceptance |
| P1 | Security | Missing-boto3 behavior mocked the internal error but did not prove `_load_provider()` translates only boto3 absence | Test the real lazy-loader exception boundary and preserve unrelated missing modules | Added a guarded-import matrix for boto3 translation versus unrelated propagation |
| P1 | Operator/Ops | Empty Docker port bindings satisfied a subset assertion | Require a non-empty binding set before the loopback-only subset assertion | Corrected both real-service integration tests |
| P1 | Operator/Ops | Any whole-job timeout was classified as infrastructure | Distinguish Docker preflight failure from an ambiguous later lifecycle/test timeout | Corrected risk and CI evidence wording; later timeout blocks blind retry |
| P1 | Operator/Ops | Exact-head merge-ready commands did not query unresolved review threads | Query exact PR GraphQL review threads and reject pagination gaps | Added head equality, `reviewThreads`, `hasNextPage`, and zero-unresolved assertions |
| P1 | Operator/Ops | Install-table replacement could remove the current PyPI publication hold | Retain source-only availability and label pip commands post-publication | Added the hold and the exact source-workspace sync command |
| P2 | Operator/Ops | Abnormal-exit cleanup had no safe PostgreSQL/LocalStack identification procedure | Label wrapper-owned services and document inspect-confirm-remove excluding Ryuk | Added per-service labels, unit assertions, and bilingual runbook requirements |
| P1 | User/caller | Stable error table lacked the required `TestcontainerStartError.kind` example | Add a copy-paste branch on stable kinds without rendering raw values | Added a sanitized example for both locales |
| P1 | User/caller | PostgreSQL and LocalStack timeout ownership was not caller-facing | Document wrapper-specific timeout scope and CI-cap distinction | Added a bilingual timeout-ownership table |
| P1 | User/caller | Fixture examples were assigned only to English | Require full executable examples and warnings in Korean too | Expanded Task 6 Step 1 to both locales |
| P2 | User/caller | Locale scan could pass with missing install, error, timeout, cleanup, or example sections | Validate paired executable anchors and perform a manual semantic parity pass | Expanded the anchor loop and final parity checklist |
| P1 | User/caller | Thread-safety and unsupported LocalStack capability boundaries were implicit | State one-owner/non-thread-safe use and that only S3 is CI-proven | Added explicit caller guidance for both locales |

## Six-perspective final verdict

| Lens | Final evidence | P0 | P1 | P2/P3 disposition |
| --- | --- | ---: | ---: | --- |
| Performance | Provider-supported timeouts remain unchanged; serial job now has an outer cap; benchmark is N/A because no steady-state hot path is introduced | 0 | 0 | none |
| Stability | Complete single-use lifecycle, startup/body control-flow preservation, cleanup failure retention/retry, serial Docker proof, and Ryuk ownership are task-level tests | 0 | 0 | none |
| Security | Complete digest parsing, negative image/service/region/driver/timeout tests, loopback verification, service labels, lazy dependency boundary, redacted exceptions, and ambient-AWS isolation are explicit | 0 | 0 | none |
| Operator/Ops | Preflight versus ambiguous timeout triage, bounded CI, service-label orphan runbook, rollback points, source-only availability, exact-head CI, and review-thread evidence are explicit | 0 | 0 | P2 fixed in plan |
| Developer/API | Tasks are sequential and atomic; shared helpers precede adapters, extras precede real services, public exports remain additive, provider classes stay private, and complete module/test snippets compile | 0 | 0 | none |
| User/caller | Both locales receive install availability, complete fixtures, reset/client ownership, stable error handling, timeout scope, cleanup/Ryuk guidance, Redis compatibility, and S3 capability limits | 0 | 0 | P2 fixed in plan |

Final verdict: **P0=0, P1=0, P2=0, P3=0**.

## Step 3-R completeness

| Check | Result |
| --- | --- |
| Spec and DoD traceability | Every approved acceptance group maps to Tasks 1-7 and named evidence in the plan traceability table |
| Implementable ordering | Shared identity -> adapters -> extras/lock -> real services/CI -> docs/lesson -> full verification/PR |
| No backward dependency | Each task consumes only earlier committed artifacts; shared files are explicitly sequential |
| Test shape | Success, invalid/empty/boundary input, lazy dependency, lifecycle, cleanup retry, primary exceptions, redaction, real backend capability, packaging, and CI are explicit |
| Concurrency/coroutines | N/A: wrappers are synchronous and intentionally not thread-safe; docs require one fixture/caller owner and Docker tests remain serial |
| Commands | Targeted pytest, focused/full sync, wheel smokes, real Docker tests, Ruff, build, actionlint, diff, exact head, CI, and GraphQL review-thread checks are concrete |
| Documentation | Package and root English/Korean docs, WIP, CHANGELOG, PR DoD, and mandatory Type A lesson are assigned |
| New module/build registration | N/A: this extends an existing Python distribution; extras, lock, wheel metadata, CI job, and import isolation replace JVM module/BOM registration concerns |
| Spring/Exposed/coroutine rules | N/A to this Python synchronous package |
| Duplication decision | Pure cross-adapter helpers are extracted; the small state machine is intentionally duplicated to avoid a generic lifecycle base and Redis refactor |
| Rollback/compatibility | Each task has a stop/revert point; Redis identity/message behavior, base-only root extra, no publish/release side effects, and fresh merge approval remain explicit |

## Plan artifact validation

- Required header, checkbox steps, exact file scopes, commands, expected evidence, Lore commits, rollback points, traceability, and implementation hold are present.
- Complete `_support.py`, PostgreSQL, LocalStack, unit-test, integration-test, packaging-test, and documentation Python snippets compile as plan text.
- Placeholder scan is empty.
- `git diff --check` passes.
- Implementation remains blocked until the user approves the reviewed written plan.
