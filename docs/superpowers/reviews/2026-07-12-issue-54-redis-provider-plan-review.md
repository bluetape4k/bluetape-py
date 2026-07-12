# Issue #54 Redis Provider Substrate Plan Review

- Artifact: `docs/superpowers/plans/2026-07-12-issue-54-redis-provider-implementation-plan.md`
- Source spec: `docs/superpowers/specs/2026-07-12-issue-54-redis-provider-design.md`
- Artifact kind: implementation plan
- Work type: Type A - Full Feature
- Review date: 2026-07-12
- Result: `P0=0 P1=0`

## Review execution

Six bounded perspective passes reviewed the same implementation plan, approved
spec, and current repository layout before main-session integration. The active
collaboration surface cannot attach the OMX-required native `agent_type`, so
untyped agents were not spawned. The workflow's local-equivalent fallback was
used and the perspectives remained separate until integration.

This is a plan review, not implementation evidence. Commands labeled RED,
GREEN, integration, benchmark, build, or full-suite remain future obligations
and must not be reported as passing until executed with fresh output.

## Initial findings and repairs

| Priority | Lens | Finding | Repair applied | Rerun lane |
|---|---|---|---|---|
| P1 | Developer/API | `ResultEnvelopeCodec.max_encoded_size` and a built-in format's direct-use bound could disagree without a deterministic construction rule. | Require the built-in format bound to be at least the codec bound; keep the codec's smaller bound authoritative and the outer bound authoritative for custom formats. Clarify the approved spec and add construction tests. | Developer/API, Security |
| P1 | Stability | Concurrent close joiners, later idempotent close calls, and cancellation combined with owned-client close failure did not have one complete outcome rule. | Persist the private terminal result, share it only with callers that observed `closing`, make later `closed` calls no-ops, and define cancellation precedence plus one redacted terminal event. Clarify the approved spec and add deterministic tests. | Stability, Developer/API |
| P1 | Operator/Ops | The existing in-workspace `redis` absence assertion cannot remain true after `uv sync --all-packages` intentionally installs the new workspace member. | Keep the general lane's Fory/native isolation checks and move Redis/default-install proof to the existing isolated default-wheel environment; add a dedicated Redis-provider job. | Operator/Ops |
| P2 | Security | `json.loads()` can accept trailing whitespace even though the approved format rejects all trailing JSON input. | Require UTF-8 plus `JSONDecoder.raw_decode()` and an exact terminal offset; add trailing-whitespace coverage. | Security |
| P2 | Developer/API | Async lifecycle examples introduced production test-only constructors and cleanup inspection methods. | Exercise owned mode through a patched public redis-py factory and prove cleanup through public post-close behavior plus `asyncio.all_tasks()`. | Developer/API |
| P2 | User/caller | The package metadata referenced `README.md` several tasks before documentation created it. | Create narrow bilingual package READMEs in the scaffold task and expand them from verified behavior in the documentation task. | User/caller, Operator/Ops |
| P2 | Performance | The near-limit benchmark did not constrain sample counts and could create avoidable workstation load. | Set per-size sample counts with ten near-limit iterations and keep results non-gating. | Performance |
| P2 | Developer/API | Provider tasks described behavioral conformance but did not explicitly lock `inspect.signature()` and context-manager contracts. | Add exact sync/async signature, export-order, and context-manager tests to Tasks 5 and 6. | Developer/API |

All findings were repaired in the plan. The two contract clarifications were
also applied to the source spec so the plan does not become a competing source
of truth. No public name or approved architecture changed.

## Final 7-Tier rerun

### Tier 1: Performance

`P0=0 P1=0`. Binary and JSON encoders preflight predictable output, outer and
logical decompression bounds are tested at exact/+1 edges, and the benchmark
uses bounded case-specific samples. It records raw size and latency without an
absolute production claim.

### Tier 2: Stability

`P0=0 P1=0`. Tasks separately prove sync admission, async loop affinity,
concurrent close, shared terminal outcomes, owned/borrowed lifecycle,
cancellation while draining/closing, and absence of detached tasks. Barrier
tests and repeated focused runs avoid timing-only race assertions.

### Tier 3: Security

`P0=0 P1=0`. Parsing starts behind the outer bound; binary lengths, exact JSON
terminal input, canonical base64, semantic return types, decompression choice,
Lua arguments, binary Redis responses, and redacted diagnostics all have hostile
cases. Format, compressor, and command fallbacks remain forbidden.

### Tier 4: Operator/Ops

`P0=0 P1=0`. Exact pins, lock checks, isolated default and focused wheel
environments, serial RedisServer integration, ACL capability failure, a
dedicated CI job, namespace rollout, TTL-aware rollback, and build/actionlint
gates are executable. Default/dev/all isolation is tested in the environment
where that claim is meaningful.

### Tier 5: Developer/API

`P0=0 P1=0`. The file split has one responsibility per module. Protocols,
dataclasses, enums, error codes, exports, signatures, format IDs, option
forwarding, ownership, TTL conversion, command results, and context managers
map to exact tests. Each behavior slice follows RED, minimal GREEN, focused
verification, and a rollback commit.

### Tier 6: User/caller

`P0=0 P1=0`. The plan produces bilingual focused/root/meta documentation with
binary and JSON choices, identity/native compression, sync/async examples,
borrowed/owned lifecycle, trusted cause boundaries, ACL requirements, and
rollout/rollback guidance. #55 behavior is explicitly excluded.

### Tier 7: Main-session integration

`P0=0 P1=0`.

- Spec coverage: all 13 acceptance criteria map to Tasks 1-10.
- Ordering: package/import proof precedes parser, codec, provider, Redis,
  packaging, documentation, and final-review work.
- TDD: each production slice starts with an executable RED case and ends with
  focused GREEN evidence before its commit.
- Repository fit: paths, uv workspace metadata, RedisServer, marker names,
  bilingual docs, develop/main policy, and PR DoD match current conventions.
- Scope: one independently testable provider substrate is delivered; #55 and
  #56 remain separate.
- Stop condition: implementation stops before push/PR/merge and requires the
  next explicit user approval.
- Open decisions: execution mode only; no design decision remains.

Final integrated gate: `P0=0 P1=0`.
