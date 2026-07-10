# Issue #46 Apache Fory Spec Review

Date: 2026-07-11
Artifact: `docs/superpowers/specs/2026-07-11-issue-46-apache-fory-design.md`
Gate: Step 2-R 7-Tier spec review

## Iteration 1

| Tier | Initial result | Required corrections applied |
| --- | --- | --- |
| Performance | P0=0 P1=3 | Thread-safe reuse, explicit allocation semantics, bounded/path-gated producer CI |
| Stability | P0=0 P1=4 | Frozen registration lifecycle, unchained errors, supported provider limits, exact fixture pins |
| Security | P0=0 P1=5 | Exact root types, public Buffer consumption check, exception isolation, fixed trust/resource boundaries |
| Operator | P0=0 P1=3 | Artifact-based bidirectional CI, rollout/rollback runbook, caller-owned observability |
| Developer/API | P0=0 P1=4 | Tagged 1.3.0 API alignment, public Buffer path, numeric ID bounds, base error contracts |
| Caller/User | P0=0 P1=6 | Nested-type scope, complete errors/install/routing example, extras matrix, fixed-schema migration |

## Convergence Corrections

The first rerun found one shared P1: upstream `ThreadSafeFory` retains an
unbounded number of runtimes after contention. The spec now caps provider calls
with a bounded semaphore, defines finite acquisition timeout behavior, and
requires retained-runtime verification through the public `fory_factory` seam.

Stability then found incomplete toolchain reproducibility. The spec now pins
CPython, Go, Rust, Temurin, Gradle, wrapper checksums, dependency versions, and
fresh-process regeneration. Operator review added caller-owned low-cardinality
route attribution. Developer review removed impossible provider-message-based
limit classification and isolated registration failures through an eager public
probe plus callback sentinel. Caller review completed the independent-policy
example and corrected local-wheel installation.

## Final Rerun

| Tier | Final result | Residual notes |
| --- | --- | --- |
| Performance | P0=0 P1=0 | Native RSS and post-allocation output observations remain non-blocking evidence |
| Stability | P0=0 P1=0 | Lazy provider lifecycle risks are covered by eager probe and failure isolation |
| Security | P0=0 P1=0 | Hard CPU/RSS isolation remains an explicitly documented caller responsibility |
| Operator | P0=0 P1=0 | Exact CI timeout/cache/retention values move to the reviewed implementation plan |
| Developer/API | P0=0 P1=0 | Public `pyfory 1.3.0` implementation surfaces are specified |
| Caller/User | P0=0 P1=0 | Remaining documentation refinements are non-blocking |

## Main Integration Critique

The final contract has one caller-selected trust/routing model, one fixed-schema
adapter per route, deterministic numeric identifiers, provider-independent
public failures, bounded concurrency, exact body consumption, reproducible
four-language fixtures, and artifact-based CI proof. Cross-tier corrections do
not conflict: provider limit failures deliberately map to `INVALID_FORY`, while
outer byte and concurrency limits retain precise stable codes.

Step 3 implementability cross-check clarified one wording ambiguity: only the
outer envelope version maps to `UnsupportedVersionError`; indistinguishable
provider parse/version/limit failures remain `INVALID_FORY`, as the reviewed
error-classification paragraph already required.

Final gate: **P0=0 P1=0**.
