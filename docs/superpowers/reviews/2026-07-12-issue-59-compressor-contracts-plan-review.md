# Issue #59 Compressor Contracts Plan Review

- Artifact: `docs/superpowers/plans/2026-07-12-issue-59-compressor-contracts-implementation-plan.md`
- Artifact kind: plan
- Work type: Type A - Full Feature
- Review date: 2026-07-12
- Gate: Step 3-R 7-Tier plan review
- Result: `P0=0 P1=0`

## Review execution

Six independent plan lenses and the main-session integration lane reviewed the same approved spec,
repository state, provider probes, and implementation plan. The active collaboration surface cannot
attach the OMX-required native `agent_type`; the documented main-session fallback therefore ran
each read-only lens separately. No untyped subagent was dispatched, and the main session alone
edited the plan and integrated severity.

## Initial findings and repairs

| Priority | Lens | Evidence | Required plan edit | Rerun lane |
|---|---|---|---|---|
| P1 | Stability | Zstd plan initially inherited the spec's streaming wording although the pinned provider does not hard-cap known-size frames with `max_output_size`. | Preflight declared content size, reject unknown/error/oversized frames, require `allow_extra_data=False` and actual-size equality, and update affected spec evidence. | Stability, Security, Performance |
| P1 | Developer/API | `native_compression` marker registration was assigned after the first marked provider tests. | Register the marker in Task 3 before any marked test command and make Task 7 verify it. | Developer/API |
| P1 | Developer/API | Isolated focused-extra smoke checks described outcomes without executable assertions. | Add exact base/focused/native/meta venv install and construction checks. | Developer/API |
| P1 | Security | Native export and input-boundary coverage did not explicitly prove exact namespace exposure. | Add exact root/native export assertions and stable bytes-like validation before provider resolution. | Security, Developer/API |
| P2 | Operator/Ops | Forwarding extra names were listed but their exact dependency targets were implicit. | Record all four exact `bluetape-compression[extra]==0.1.0` mappings. | Operator/Ops |
| P2 | User/caller | The focused smoke wording did not demonstrate that unselected class names import but fail only on construction. | Add per-environment class-name import, provider-spec, selected construction, and unselected focused-error assertions. | User/caller |
| P2 | Performance | Stress coverage named a large round-trip but not the evidence rule. | Require call/allocation/input-budget evidence and prohibit flaky absolute-time thresholds. | Performance |

All findings were repaired in the plan or the non-material provider-safety clarification to the
spec. Nothing was deferred and no follow-up issue is required for the approved #59 scope.

## Final 7-Tier rerun

### Tier 1: Performance

`P0=0 P1=0`. Tasks 3-5 assign algorithm-specific pre-decode or incremental bounds. Task 6 verifies
input windows, provider-call suppression, an 8 MiB stress path, and deterministic call/allocation
evidence without claiming an unstable latency threshold. Step 4-P is explicitly required.

### Tier 2: Stability

`P0=0 P1=0`. Task ordering is implementable: metadata/support precedes providers, every provider
precedes common conformance, packaging precedes docs/full verification, and lessons precede PR.
Malformed, truncated, trailing, concatenated, missing-provider, fatal-failure, and upgrade-drift
paths have deterministic tests and rollback points. Concurrency/cancellation/resource cleanup is
N/A because the implementation owns no asynchronous work or external resource.

### Tier 3: Security

`P0=0 P1=0`. Oversized output is rejected before unbounded native decode; ordinary provider
failures are redacted outside active handlers; fatal failures propagate; no logging, registry,
auto-detection, or unsafe deserialization is introduced. Hostile error/context/reference tests and
base dependency-isolation checks are concrete.

### Tier 4: Operator/Ops

`P0=0 P1=0`. Exact pins, lock checks, base/focused/aggregate/meta wheel smoke environments, a
dedicated non-Docker native CI job, additive rollout, provider-first rollback, changelog/WIP state,
and PR/CI evidence are assigned. Health/readiness/shutdown/runbook work is N/A for a synchronous
in-process byte-transform library with no service lifecycle.

### Tier 5: Developer/API

`P0=0 P1=0`. The plan defines exact files, dependencies, public names, signatures, configuration
ranges, export surfaces, RED/GREEN commands, commit boundaries, and validation expectations. The
structural protocol remains Python-native, native providers stay in focused modules, and existing
functions retain source/wire compatibility.

### Tier 6: User/Caller

`P0=0 P1=0`. Focused and forwarding install choices, missing-extra timing, empty behavior, error
table, logical output limit, custom structural implementation, Kotlin-interface semantic analogy,
wire non-compatibility, migration, and serde/compressor/Redis order are assigned to English/Korean
documentation. #54 remains visibly unimplemented and blocked on merged #59.

### Tier 7: Main-session integration

Every approved acceptance criterion and DoD item maps to Tasks 1-10. No task consumes a later
artifact. Public behavior has success, invalid, empty, exact-bound, one-over, malformed, trailing,
fatal-provider, packaging, and caller-preservation coverage. Workflow YAML, lock/build metadata,
localized docs, rollout/rollback, review evidence, lessons, live PR metadata, and the explicit merge
hold all have owners and exact gates.

Final gate: `P0=0 P1=0`.
