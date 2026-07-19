# Issue #17 leader lock pre-head code review

Date: 2026-07-19 KST
Reviewed implementation range:
`48b1dbc291a3a00606654f3c1c46bffbeed1361e..f93e4e057cac6cd0994f6a2a6b3438921a515e4d`

## Method and boundary

Task-level reviews and the final six independent lenses were read-only. The
first security reviewer stalled without evidence; the main session interrupted
that delegation, reused a fresh bounded reviewer, and recorded the fallback in
the workflow receipt. Findings below were converted to focused RED tests when
they represented executable behavior, then repaired and rerun. This file is a
pre-evidence ledger and does not pre-claim the immutable-head verifier verdict.

## Findings and repairs

| Priority | Lens | Finding | Repair | Status |
|---|---|---|---|---|
| P0 | Stability | A process-control exception raised after the real sync renewal thread started could leave a non-daemon worker and lease behind | Stop and join the published worker, perform owner-checked release, then rethrow the identical control object | Closed in `fd149bd` |
| P1 | Performance/stability | Async acquisition lacked the sync pre-I/O auto-renew timing proof | Share one strict sync/async option normalization and timing gate | Closed in `fd149bd` |
| P2 | Performance | Async contention lacked a direct bounded nonzero retry-count proof | Add exact dispatch/sleep-count regression | Closed in `f1d8fa0`; GREEN at `fd149bd` |
| P3 | Performance | Derived renewal interval retained sub-millisecond precision not representable by Redis | Copy and floor the derived interval to whole Redis milliseconds | Closed in `fd149bd` |
| P1 | Security | Timing validation compared renewal completion with the longer Python lease instead of the effective Redis TTL | Convert lease to the exact encoded millisecond TTL before comparison; add sync/async boundary regressions | Closed in `16d84ea` |
| P2 | Security/operator | ACL integration always granted `CLIENT SETINFO`, wider than the documented minimum | Remove the unconditional grant and rerun all 48 ACL shapes | Closed in `2165c77` |
| P1 | Developer/API | `LeaderExecutionError` accepted an arbitrary raw lifecycle exception despite the sanitized `LeaderError` contract | Runtime-validate both ordinary action and sanitized lifecycle cause types | Closed in `f31684a` |
| P1 | Developer/API | Manual README renewal failure returned `False`, but `finally: release()` replaced it with a different lifecycle exception | Raise the sanitized terminal renewal failure before entering the action/release block and execute both failure paths in README tests | Closed in `f31684a` |
| P2 | Operator | Migration did not explain the signed counter ceiling or impossible strictly-above restore | Document fail-closed exhaustion and downstream-recognized compound epoch/token migration | Closed in `4452a15` |
| P3 | Operator | Server compatibility named redis-py but not the proven Redis Server major | Pin the tested support target to Redis Server 8 and add a deployment qualification gate | Closed in `4452a15` |
| P1 | User/caller | Both lock constructors allowed positional `prefix`, unlike the approved contract and keyword-only electors | Make sync/async lock `prefix` keyword-only and pin exact signatures | Closed in `f93e4e0` |
| P2 | User/caller | The async README returned a borrowed client from a temporary `asyncio.run()` loop and did not close it | Keep construction, operation and `aclose()` in one caller-owned async scope | Closed in `f93e4e0` |
| P2 | User/caller | Composite action+lifecycle failure handling was public but undocumented | Explain `action_cause`, sanitized `lifecycle_cause`, propagation and safe classification | Closed in `f93e4e0` |
| P3 | User/caller | No complete sync/async Redis elector outcome example existed | Add one identical bilingual example covering both electors and all precise outcomes | Closed in `f93e4e0` |

## Six-lens convergence

| Lens | Initial highest finding | Repair evidence | Pre-evidence P0 | Pre-evidence P1 |
|---|---|---|---:|---:|
| Performance | P1 async timing parity | `5 passed`, lock `204 passed`; final core+adapter `867 passed` | 0 | 0 |
| Stability/reliability | P0 real-thread-start cleanup | identical control propagation and worker/lease cleanup regressions | 0 | 0 |
| Security/privacy | P1 effective TTL | adapter `753 passed`, ACL `48` shapes | 0 | 0 |
| Operator/Ops | P2 counter exhaustion | bilingual operator docs and README contracts `7 passed` | 0 | 0 |
| Developer/public API | P1 composite/manual lifecycle | core `113 passed` | 0 | 0 |
| User/caller | P1 positional coordination prefix | four RED-to-GREEN public-contract tests; combined `867 passed` | 0 | 0 |

All review-discovered P0/P1 findings are closed before the evidence commit.
Fresh canonical commands and an independent verifier must still run at the
unchanged evidence head.
