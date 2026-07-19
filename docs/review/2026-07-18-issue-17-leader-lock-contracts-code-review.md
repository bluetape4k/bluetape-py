# Issue #17 leader lock pre-head code review

Date: 2026-07-19 KST
Reviewed implementation range:
`48b1dbc291a3a00606654f3c1c46bffbeed1361e..2f6cf37657ea86ee148e87ac023d91eb9a7e51e4`

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
| P0 | Stability | A process-control exception raised after the real sync renewal thread started could leave a non-daemon worker and lease behind | Stop and join the published worker, perform owner-checked release, then rethrow the identical control object | Closed in `077f083` |
| P1 | Performance/stability | Async acquisition lacked the sync pre-I/O auto-renew timing proof | Share one strict sync/async option normalization and timing gate | Closed in `077f083` |
| P2 | Performance | Async contention lacked a direct bounded nonzero retry-count proof | Add exact dispatch/sleep-count regression | Closed in `9bd104c`; GREEN at `077f083` |
| P3 | Performance | Derived renewal interval retained sub-millisecond precision not representable by Redis | Copy and floor the derived interval to whole Redis milliseconds | Closed in `077f083` |
| P1 | Security | Timing validation compared renewal completion with the longer Python lease instead of the effective Redis TTL | Convert lease to the exact encoded millisecond TTL before comparison; add sync/async boundary regressions | Closed in `8c9fc98` |
| P2 | Security/operator | ACL integration always granted `CLIENT SETINFO`, wider than the documented minimum | Remove the unconditional grant and rerun all 48 ACL shapes | Closed in `91e8ee4` |
| P1 | Developer/API | `LeaderExecutionError` accepted an arbitrary raw lifecycle exception despite the sanitized `LeaderError` contract | Runtime-validate both ordinary action and sanitized lifecycle cause types | Closed in `8167fa9` |
| P1 | Developer/API | Manual README renewal failure returned `False`, but `finally: release()` replaced it with a different lifecycle exception | Raise the sanitized terminal renewal failure before entering the action/release block and execute both failure paths in README tests | Closed in `8167fa9` |
| P2 | Operator | Migration did not explain the signed counter ceiling or impossible strictly-above restore | Document fail-closed exhaustion and downstream-recognized compound epoch/token migration | Closed in `1451f7f` |
| P3 | Operator | Server compatibility named redis-py but not the proven Redis Server major | Pin the tested support target to Redis Server 8 and add a deployment qualification gate | Closed in `1451f7f` |
| P1 | User/caller | Both lock constructors allowed positional `prefix`, unlike the approved contract and keyword-only electors | Make sync/async lock `prefix` keyword-only and pin exact signatures | Closed in `2f6cf37` |
| P2 | User/caller | The async README returned a borrowed client from a temporary `asyncio.run()` loop and did not close it | Keep construction, operation and `aclose()` in one caller-owned async scope | Closed in `2f6cf37` |
| P2 | User/caller | Composite action+lifecycle failure handling was public but undocumented | Explain `action_cause`, sanitized `lifecycle_cause`, propagation and safe classification | Closed in `2f6cf37` |
| P3 | User/caller | No complete sync/async Redis elector outcome example existed | Add one identical bilingual example covering both electors and all precise outcomes | Closed in `2f6cf37` |

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

## Post-PR correction loop (PR #83)

Hosted CI and a fresh security lens challenged the pre-PR evidence after the
pull request was created. These findings belong to the later exact-head gate;
they do not rewrite the historical review range above.

| Priority | Lens | Finding | Repair | Status |
|---|---|---|---|---|
| P1 | Performance/stability | On Linux async TCP, a 10 ms timeout could expire during the final handshake response before the intended primitive `PING` was emitted; a post-timeout observation wait could not repair that ordering | Separate handshake-stage stalls from the primitive-response case, pre-establish the exact connection with a bounded 500 ms setup timeout, restore the validated 10 ms response timeout, then issue and observe the primitive before teardown | Local timing matrix `206 passed`; hosted CI rerun pending |
| P0 | Security | Rejecting only a positive counter TTL still allowed the expired counter to disappear and later be recreated at token 1; an active lease could also hide a rolled-back counter until expiry | Add a same-slot persistent `v1` history marker and a strict atomic state machine: marker/counter must both be absent for a fresh lease or both be canonical persistent strings; any one-sided, expiring, malformed, active-lease-with-missing-history, or active-lease/counter-token-mismatch state returns `CORRUPT` | RED/GREEN source checks plus sync/async real Redis expiry, mismatch, and corruption matrices passed; exact-head review pending |
| P2 | Stability | The timing harness could retain a checked-out primitive connection if setup or the expected timeout assertion failed | Release any still-borrowed connection and disconnect the pool through nested `finally` cleanup in sync and async helpers | Local timing matrix `206 passed`; exact-head review pending |
| P2 | Performance/stability | The commandstats evidence still documented the pre-marker `GET` count | Record the exact marker-aware formula and `498` observed calls per mode | Concurrency integration passed; exact-head review pending |
| P2 | Developer | The approved implementation plan retained historical two-key examples that could be mistaken for the final contract | Preserve the plan history but add an explicit post-PR supersession note pointing to the authoritative three-key design | Documentation review pending |
| P2 | Verification | Real Redis tests covered history corruption and counter expiry but not counter wrong-type/malformed states directly | Add sync/async no-mutation fail-closed cases for list and noncanonical decimal counter values | Targeted real Redis matrix passed; exact-head review pending |
| P2 | Operator | The structured action table omitted contention, lease-loss, renewal-failure, and release-failure rows required by the design | Add bilingual signal-to-action rows and a table-scoped regression test | README examples `7 passed`; exact-head review pending |
| P1 | Developer/API | The bilingual elector example defined zero-argument actions even though both electors call actions with the acquired lease | Accept the lease argument in both examples and execute sync/async elected paths through the actual elector methods in the README regression | README examples `7 passed`; exact-head review pending |
| P1 | Security/operator | TLS rejection was documented as a compatibility boundary but the public constructor and deployment guidance did not state the confidentiality consequence of plaintext TCP | Require caller-controlled protected networking for TCP, prefer a local Unix socket, and warn that credentials, owner tokens and capability-bearing lock material are visible to network observers | Bilingual README regression `5 passed`; exact-head review pending |

The correction loop remains open until the new exact head passes hosted CI and
all six post-PR review lenses with P0=0/P1=0.
