# Issue #56 RESP3 Near-Cache Design Self-Review

## Scope

- Review the committed design at `6c81930` against issue #56.
- Challenge namespace isolation, connection ownership, lifecycle races,
  fail-closed behavior, loader fencing, resource cleanup, packaging boundaries,
  and the redis-py public-API stop condition.
- Review the design only; no production implementation or capability spike is
  included in this change.

## Result

- Self-review after corrections: CLEAR.
- P0=0, P1=0 for the design document.
- Independent implementation review remains required before merge readiness.

## Findings and Resolutions

### Resolved P1: logical namespace prefix overlap

The initial format used raw `<namespace>:` as the BCAST prefix. Logical
namespaces `a` and `a:b` would overlap because `a:b:<key>` also begins with
`a:`. The corrected design base64url-frames namespace UTF-8 bytes under the
fixed `bluetape:near:` root before appending the encoded key. Tests now include
overlapping logical namespace names.

### Resolved P1: distinct clients could still share a pool

The initial ownership rule rejected only identical client objects. Two redis-py
clients can still wrap one pool, which would not prove a dedicated reader
connection. The corrected constructor contract requires distinct pools or
another publicly provable dedicated-connection shape and rejects two wrappers
over one shared pool. Gate 0 may narrow the constructor if public redis-py APIs
cannot validate the broader form.

### Resolved P1: close did not drain admitted loaders

Clearing `TTLCache` or `AsyncTTLCache` supersedes publication but does not by
itself prove that a running loader task has terminated. The corrected facade
tracks admitted public operations and close drains them before closing clients.
This prevents an owned async loader task from surviving facade close. Caller-
owned finite loader deadlines remain required, and recursive close from an
admitted loader is rejected to avoid self-deadlock.

### Resolved P1: concurrent start outcome was ambiguous

The initial document said start was idempotent without defining the owner of a
concurrent initial attempt. The corrected rule gives the first caller ownership,
makes concurrent callers observe the same terminal result, prevents duplicate
readers, defines started-state no-ops, and makes close win before readiness
publication when it races initial start.

### Resolved P2: Markdown hard-break whitespace

The initial commit used trailing spaces in metadata lines. The correction uses
blank-line separation and passes `git diff --check`/`git show --check` for the
reviewed delta.

## Acceptance Review

| Issue requirement | Review evidence |
|---|---|
| Dedicated RESP3 reader and separate command path | Gate 0 plus distinct client/pool ownership rules |
| BCAST PREFIX namespace isolation | Delimiter-safe namespace framing and overlap test |
| Marker-only Redis data | Reversible marker keys, opaque token value, finite TTL |
| Sync/async parity | Parallel public contracts and all-or-nothing Gate 0 |
| Fail closed on reader loss | Generation transition, complete clear, local gate, bounded reconnect delay |
| No stale in-flight publication | Existing key/clear fencing plus readiness generation |
| No reads/population while unhealthy | Owned local cache; `get` misses and direct load never populates |
| Explicit lifecycle and cleanup | Concurrent start rule, admitted-operation drain, owned worker/client cleanup |
| No private redis-py integration | Explicit forbidden-technique list and upstream stop condition |
| Optional dependency isolation | No changes to `bluetape-cache`; Redis surface remains in the optional package |

## Verification

- Worktree baseline after installing locked `fory` and native-compression test
  extras: 1,515 tests passed on Python 3.13.14.
- Initial document commit: `6c81930`.
- `git diff --check`: passing after corrections.
- Production code, package metadata, and public exports: unchanged.

## Remaining Gate

The next step is user review of the corrected design and this evidence. Only
after approval may `writing-plans` produce the implementation plan. Gate 0 must
then pass for both sync and async before production implementation begins.
