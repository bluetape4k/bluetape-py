# Issue #46 Apache Fory Plan Review

Date: 2026-07-11
Artifact: `docs/superpowers/plans/2026-07-11-issue-46-apache-fory-implementation-plan.md`
Gate: Step 3-R 7-Tier plan review

## Initial Review

| Tier | Initial result | Main blocking themes |
| --- | --- | --- |
| Performance | P0=0 P1=3 P2=2 | Pool failure/reuse semantics, eager-probe accounting, executable final verifiers, RSS isolation, exact cache inputs |
| Stability | P0=0 P1=5 P2=1 | Lazy registration failures, exact Python pin order, manifest lifecycle, reproducible Go/Kotlin generation, same-runtime reuse |
| Security | P0=0 P1=5 P2=2 | Trust gates, exception-local cleanup, semaphore release, import-failure classification, empty/root-body handling and no-log proof |
| Operator/Ops | P0=0 P1=3 P2=3 P3=2 | Normal-CI fixture proof, producer manifest fragments, observability boundary, exact triggers, operational limits, canary/rollback, cache/temp hygiene |
| Developer/API | P0=0 P1=2 | Explicit optional-extra execution and cross-language field identity |
| Caller/User | P0=0 P1=3 P2=2 | Application ID ownership, local meta-extra install proof, troubleshooting, fixed-schema migration, API/error documentation |

## Corrections Applied

- Defined eager-probe versus pooled-runtime accounting, ordinary failure reuse,
  lazy registration failure translation, semaphore release, and deterministic
  runtime-identity tests.
- Pinned CPython 3.13.14 before provider work and made every provider command
  select `--package bluetape-serde --extra fory` explicitly.
- Deferred the canonical four-producer manifest until all fixtures exist; made
  each producer generate twice in isolated temporary paths under exact
  toolchains and fixed locale/timezone.
- Tarred runnable verifier distributions with SHA-256 validation so artifact
  transfer preserves executable modes.
- Extended fresh-error isolation to pre-provider gates and concurrency timeout;
  added direct/transitive/ABI import classification, no-log, empty-body, Fory
  root-header, and sensitive-local tests.
- Added normal-CI checksum/Python decode gates, machine-readable producer
  fragments, exact workflow triggers, authoritative lock checks, per-route
  observability isolation, resource-limit scope, and actionable canary/rollback.
- Kept Kotlin KSP `@ForyField` metadata as required by the official API and
  aligned field IDs 1-4 through Python `pyfory.field`, Go struct tags, Rust
  attributes, and Kotlin annotations instead of removing Kotlin metadata.
- Added a no-index local meta-extra installation proof, application-owned ID
  manifest contract, ABI troubleshooting, versioned-route migration, and
  public API/error table updates.

## Final Rerun

| Tier | Final result | Residual notes |
| --- | --- | --- |
| Performance | P0=0 P1=0 | Timing and RSS remain recorded evidence, not flaky absolute gates |
| Stability | P0=0 P1=0 | Task dependencies and exact generation commands are implementable in order |
| Security | P0=0 P1=0 | Hard CPU/RSS containment remains an explicitly documented process boundary |
| Operator/Ops | P0=0 P1=0 | CI, artifacts, observability, and rollback have concrete verification paths |
| Developer/API | P0=0 P1=0 | Provider commands and four-language field metadata use supported 1.3.0 surfaces |
| Caller/User | P0=0 P1=0 | Install, ownership, error recovery, migration, and docs contracts are complete |

## Main Integration Critique

Every approved spec requirement maps to Tasks 1-13, and no task consumes a
canonical artifact before its producer task. The plan separates provider-free
base behavior from explicit provider verification, uses one field-ID and varint
schema across four runtimes, and keeps expensive generation path-gated while
normal CI performs cheap committed-fixture checks. Public behavior changes cover
both root README locales, package READMEs, changelog, package layout, rollout,
rollback, and application ownership.

The final plan has concrete red/green commands, failure and lifecycle tests,
full verification, review convergence, PR/CI handling, lessons, and knowledge
capture. No unresolved placeholder or later-task dependency remains.

Final gate: **P0=0 P1=0**.
