# Issue #63 Active-Marker Result Transfer Analysis

## Outcome

The accepted candidate changes the fixed coordination snapshot Lua script so
an active marker returns no result bytes. The provider maps that response to
`result=None`; completed and missing markers retain the prior bounded result
prefix. No public signature, exception, ACL, key, TTL, or round-trip contract
changes.

The full paired benchmark met its primary correctness target:

| Mode | Baseline active bytes | Candidate active bytes | Reduction | Baseline snapshots | Candidate snapshots |
|---|---:|---:|---:|---:|---:|
| sync | 1,572,864 | 0 | 100% | 24 | 28 |
| async | 1,835,008 | 0 | 100% | 28 | 24 |
| total | 3,407,872 | 0 | 100% | 52 | 52 |

Completed-result reuse remained non-zero in all four sync/async cases, every
scenario invariant passed, and the generic comparison reported
`comparable=true` with no reasons.

## Paired evidence

| Item | Value |
|---|---|
| Pair | `issue-63-pair-000`, index 0, baseline-first |
| Seed/profile/modes | `20260713`, full, sync and async |
| Runner | `runner-colima-a`, Colima, macOS arm64, 10 CPUs |
| Python / Redis | 3.13.14 / 8.8.0 (`redis` dependency 8.0.1) |
| Baseline | `b2f3ad5de9c5b0bdb3e1c206ac1581a3df9af474` |
| Candidate | `ebdda950c854c69f19ebc61761774762cb46641c` |
| Baseline artifact SHA-256 | `3d0cc4f8f88e0a70ae1cc03a647d4c5c1f25f0a6306cd19f1f7dacfbfb5da1ab` |
| Candidate artifact SHA-256 | `99619f008559e4ea3b4f2669eb3dbe7199c1196de260db27752647a3523d3361` |
| Comparison artifact SHA-256 | `93b8bccf3306cec3016d688183f932f77ff155da11f1983f5463780e236b650b` |
| Lock / registry digest | `a825207f86a8935492348035f65b942db501fe4fb6d3609797c3e678cdcbbd36` / `2cc0e4b8700f3678aa51e004acfd966a4fdd363a9b5435459188b039849e5566` |

The source was clean for both reports. The paired environment, dependency
lock, registry, image, and policy identities matched.

## Command-parity correction

The initially approved validator required raw Redis command equality for every
scenario. It rejected the first valid candidate because concurrent polling
produced different active-snapshot counts. A diagnostic rerun of the exact same
baseline SHA reproduced raw command drift:

| Case | Original commands | Same-SHA rerun | Commands minus active snapshots |
|---|---:|---:|---:|
| sync moderate | 18 | 19 | 8 / 8 |
| sync high | 40 | 39 | 16 / 16 |
| async high | 44 | 41 | 16 / 16 |

The diagnostic artifact SHA-256 is
`ea701537942e95bd6a1e8da658e03b4a386a67005cc14a512557b86e875ea98c`.
After explicit approval, the acceptance rule was corrected to compare
`redis_commands - active_snapshot_count` for `multi-coordinator` only. Every
other scenario retains raw command parity. Exact provider tests additionally
prove one `EVAL` per snapshot in sync and async modes.

## Timing observations and limits

Timing was not the acceptance metric. On the selected high case, sync median
changed from 14,104,875 ns to 14,958,541 ns and async median from 10,806,625 ns
to 11,981,625 ns. These single baseline-first samples do not demonstrate a
latency improvement and must not be used as capacity or SLO evidence. The
accepted claim is limited to eliminating ignored active-marker result bytes
while preserving correctness and command shape.

The fixture also required a pre-baseline repair: the zero-delay
`unrelated-keys` correctness case now uses a bounded overlap gate so it proves
concurrent loaders instead of relying on scheduler luck. Test-only readiness
uses `bluetape.testing.eventually` to observe the mapped Redis port before real
integration cases begin.
