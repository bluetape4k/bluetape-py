# Issue #24 Observability Spec Review

Date: 2026-07-15 KST
Artifact: `docs/superpowers/specs/2026-07-15-issue-24-observability-design.md`
Artifact kind: spec
Final reviewed commit: `2e3bba48301a8077b72e424b0a02f3822e0a2a86`
Final artifact SHA-256: `f555888ace6273bb7049073bdf953c816870599d725167321ed7e1f06c26f6a1`

## Scope

The review covered the approved `bluetape-observability` focused distribution, three
domain-native adapters, current-span event behavior, fixed metrics and attributes, API-only and
SDK ownership boundaries, fail-safe normalization, setup/runtime failure semantics, sync/async
context, package isolation, performance evidence, documentation, migration, release inventory,
and acceptance criteria.

The exact research basis was:

- `docs/research/2026-07-15-issue-23-observability-opentelemetry-boundaries.md`;
- current `PolicyEvent`, `RedisEvent`, and `RedisCoordinationEvent` source contracts;
- current workspace/package/CI/release inventory files;
- official OpenTelemetry library, Python signal-status, and 1.43.0 release evidence linked by
  the spec.

## Review Execution

Six fresh read-only perspective lanes ran in two waves because the session had three free child
slots. Each lane received one lens, the exact artifact, bounded read-only commands, no heavy-test
authority, no edit/commit authority, and a P0/P1/P2/P3 output contract.

| Wave | Perspective | Installed role surface | Result after rerun |
|---|---|---|---|
| 1 | Performance | `code-reviewer` | PASS |
| 1 | Stability | `verifier` | PASS |
| 1 | Security | `code-reviewer` | PASS |
| 2 | Operator/Ops | `verifier` | PASS |
| 2 | Developer/API | `code-reviewer` | PASS |
| 2 | User/caller | `writer` | PASS |

Some lanes exceeded the bounded wait while exploring. The main session stopped the long-running
turn, required a conclusion from already-read evidence, and reran incomplete or affected lanes.
The initial user/caller lane explicitly failed because it had not read the artifact; no finding
from that incomplete pass was accepted. Its replacement pass read the exact spec and produced the
findings below. No timeout was treated as review evidence.

## Initial Findings and Repairs

| Priority | Lens | Evidence | Required repair | Final result |
|---|---|---|---|---|
| P1 | Performance | Inline observers run on every terminal event, but the first spec had no measurable latency/allocation gate. | Add paired API-only and local-SDK median/p95 budgets, retained-allocation limit, and zero owned lock/task/thread/queue evidence. | Fixed and performance rerun PASS. |
| P2 | Performance | Mapping could allocate span detail when no recording span existed. | Normalize once, build metric attributes once, and build span-only detail only for a recording span. | Fixed and performance rerun PASS. |
| P1 | Security | Structural runtime field access could turn forged event-like objects into an arbitrary telemetry channel. | Add closed enum sets, finite/bounded scalar normalization, signed 64-bit limits, no partial emission, and hostile-input tests. | Fixed and security rerun PASS. |
| P2 | Security | The meter scope omitted the distribution version. | Use the installed distribution metadata as the instrumentation-scope version and test the exact default accessor call. | Fixed and security rerun PASS. |
| P2 | Stability | The first repair permanently disabled a failed instrument without a recovery contract. | The intermediate spec required reconstruction, then integration simplified setup to fail-fast construction and stateless runtime retry. | Superseded safely; stability rerun PASS. |
| P1 | Operator/Ops | Silently disabled instruments had no bridge-local diagnostic surface. | Remove hidden disabled state: fail adapter construction on setup errors; isolate runtime recording only; retain SDK/exporter diagnostics and lifecycle in the application. | Fixed and Ops rerun PASS. |
| P2 | Operator/Ops | Repository milestone `0.2.0`, distribution version `0.1.0`, and an earlier `0.2.x` compatibility claim conflicted. | Make installed distribution metadata the instrumentation authority and distinguish milestone grouping from package compatibility. | Fixed and Ops rerun PASS. |
| P2 | Developer/API | `TYPE_CHECKING` domain imports left runtime annotation introspection ambiguous. | Require postponed annotations, pin `inspect.signature`, and explicitly exclude raw `get_type_hints()` without supplied globals. | Fixed and Developer/API rerun PASS. |
| P2 | Developer/API | Attribute sections did not pin every source-field transformation. | Add exact resilience, Redis provider, and Redis coordination mapping matrices. | Fixed and Developer/API rerun PASS. |
| P3 | Developer/API | Instrument descriptions and exact creation calls were not fixed. | Specify exact names, types, units, descriptions, and construction calls. | Fixed and Developer/API rerun PASS. |
| P1 | Developer/API | An intermediate test bullet still mixed constructor creation failure with runtime isolation. | Test setup solely as fail-fast construction and runtime `add`/`record`/span calls as independently isolated. | Fixed and Developer/API rerun PASS. |
| P2 | Developer/API | Injected-meter tests could not prove the adapter's default meter scope. | Capture and verify the default `get_meter` name/version arguments directly. | Fixed and Developer/API rerun PASS. |
| P1 | User/caller | The only example looked successful while API-only behavior could be a safe no-op. | Require separate labeled API-only no-op and runnable application-owned SDK/provider/reader/exporter examples. | Fixed and user/caller rerun PASS. |
| P1 | User/caller | Assigning the adapter into a single observer slot could silently replace an existing observer. | Declare no v1 fan-out helper; warn about replacement and leave composition order/failure policy caller-owned. | Fixed and user/caller rerun PASS. |
| P2 | User/caller | Setup/runtime failure and recovery guidance was incomplete. | Document fail-fast setup, stateless runtime isolation/retry, and application-owned SDK delivery diagnostics. | Fixed and user/caller rerun PASS. |
| P2 | User/caller | README locale parity did not explicitly require language switches and source-equivalent examples. | Require `English | 한국어` switches plus equivalent commands, examples, non-goals, migration, rollback, and failures. | Fixed and user/caller rerun PASS. |
| P3 | User/caller | Logging coexistence did not state that trace/span IDs also remain absent from log records by default. | Require bidirectional non-promotion in the coexistence example. | Fixed and user/caller rerun PASS. |

## Final Perspective Results

| Perspective | P0 | P1 | P2 | P3 | Result | Final evidence |
|---|---:|---:|---:|---:|---|---|
| Performance | 0 | 0 | 0 | 0 | PASS | Measurable budgets, bounded retained allocation, single normalization, conditional span detail, no owned concurrency |
| Stability | 0 | 0 | 0 | 0 | PASS | Fail-fast setup, stateless runtime retry, independent signal isolation, no lifecycle resource |
| Security | 0 | 0 | 0 | 0 | PASS | Closed normalization, hostile-input drop, signed bounds, no partial emission, versioned scope |
| Operator/Ops | 0 | 0 | 0 | 0 | PASS | Observable setup failure, application SDK/exporter diagnostics, explicit version authority, rollback by removal |
| Developer/API | 0 | 0 | 0 | 0 | PASS | Exact modules/signatures, typing contract, field matrices, instrument creation, feasible isolated tests |
| User/caller | 0 | 0 | 0 | 0 | PASS | No-op versus recording examples, Redis wiring, observer replacement warning, locale and logging parity |

## Main-Session Integration

- The approved architecture remains unchanged: separate focused distribution, three
  domain-native adapters, current-span events, fixed metrics, no synthetic spans, no root meta
  extra, API-only production dependency, and application-owned SDK lifecycle.
- The setup fail-fast repair is a failure-contract clarification, not a new public API: the
  approved classes and constructor signatures remain the same, while hidden disabled state and
  a new health/callback surface are avoided.
- Issue #24's older extra, logging bridge, and future package-hook language is intentionally
  narrowed by issue #23 research and the user's explicit direct-install/domain-event approvals.
- The focused distribution itself is the optionality boundary. Neither the default `bluetape`
  wheel nor existing domain packages gain OTel dependencies.
- `PolicyEvent.policy_name`, raw errors, Redis data, logging context, baggage, and arbitrary
  attributes remain excluded. Every consumed structural field is fail-safe normalized before
  any signal emission.
- Existing single observer slots remain untouched. Documentation must prevent silent observer
  replacement and does not add an unapproved composition abstraction.
- Release/package registration is fail-closed: all workspace, package-layout, README, WIP,
  changelog, CI, release inventory, and publish allowlist enumerations are assigned to the future
  implementation plan. No release or publish side effect is authorized by this spec.

## Final Verdict

- P0: 0
- P1: 0
- P2: 0
- P3: 0
- Verdict: PASS
- Type A Step 2-R DoD: PASS

The design is ready for the required written-spec user review. Implementation planning remains
blocked until the user approves the committed final spec.

## Local Integrity Evidence

- Final spec commit: `2e3bba48301a8077b72e424b0a02f3822e0a2a86`
- Final spec SHA-256: `f555888ace6273bb7049073bdf953c816870599d725167321ed7e1f06c26f6a1`
- Placeholder scan: no `TBD`, `TODO`, `FIXME`, `XXX`, `placeholder`, or `decide later`
- `git diff --check`: PASS
- Worktree after final spec commit: clean, branch ahead of `origin/develop` by four commits
