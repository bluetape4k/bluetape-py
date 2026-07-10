# Issue #45 JSON Serde Code Review

## Scope

- Base: `develop@5b804865b4db0331207d09e3ded040505f920d4c`
- Reviewed head: `a4727082cbe97c39e620605165ace69fe21dd50e`
- Contract: strict, bounded JSON serialization in `bluetape-serde`
- Follow-up boundary: binary serialization remains in Issue #46 and must reuse
  the payload/error/limit contracts introduced here.

## Verification Gate

The implementation passed the independent Step 5 verifier after correcting two
P1 findings: a forbidden regex-based validation path and an obsolete performance
test selector. Final Step 5 result: `P0=0 P1=0`.

## Step 6-R Review Matrix

| Lane | Initial findings | Resolution | Final result |
| --- | --- | --- | --- |
| Performance | P1: `list[bytes]` chunk assembly caused excessive allocation growth | Replaced chunk accumulation with one incremental `bytearray`; added allocation regression coverage | `P0=0 P1=0` |
| Stability | P1: failure tracebacks retained source or partial output objects | Re-raised fresh typed errors outside handlers and explicitly released large locals | `P0=0 P1=0` |
| Security | P1: rejected input could remain reachable through exception state; rerun found native decoder/encoder configuration errors with the same risk | Sanitized public and native configuration error boundaries; targeted security suite passed | `P0=0 P1=0` |
| Operator | P1: encode failures retained partial output; P1: durable Apache Fory follow-up evidence was not yet live | Released partial output and verified live Issue #46 with assignee, milestone, dependency, limits, trust policy, schema IDs, and cross-language conformance scope | `P0=0 P1=0` |
| Developer | P1: integer acceptance depended on CPython's process-global digit setting; P1: one commit did not expose parseable Lore trailers | Added a symmetric public 640-digit integer limit and error code; repaired commit metadata | `P0=0 P1=0` |
| User | P2: local-wheel commands were incomplete; P2: native caller-configuration failures were not clearly documented | Updated English/Korean/package documentation and normalized caller-visible failure wording | `P0=0 P1=0 P2=0 P3=0` |

## Integrated Review

- The public boundary exports 21 names and 17 stable error codes, including
  `MAX_JSON_INTEGER_DIGITS` and `INTEGER_DIGIT_LIMIT`.
- Serialize and deserialize paths enforce byte, depth, reference, collection,
  string, and integer-digit limits without relying on process-global CPython
  settings.
- Rejected values, source buffers, decoded text, metadata intermediates, and
  partial output are not retained by public error tracebacks.
- The optional package boundary is isolated: `bluetape-serde` has no runtime
  dependency and the meta package includes it only through `serde`, `dev`, and
  `all` extras.
- README, localized README, package layout, changelog, and WIP scope agree with
  the implemented API and the Issue #46 binary-serde follow-up.
- Release and workflow changes are not required for this additive package;
  repository-wide tests and package builds cover the registration path.
- Local verification used Python 3.14.6. Repository CI remains the Python 3.13
  compatibility authority and must pass on the exact PR head before merge.

## Result

All blocking review findings are resolved: `P0=0 P1=0`. All recorded
non-blocking findings are also resolved: `P2=0 P3=0`.

## Post-PR Review

PR #48 review against exact head
`a6f5b0fc496ddfe0f11b8fa5e38a6d4de2c3abc8` found one P1 and one deduplicated
P2:

- P1: shared-reference DAGs were validated once per expanded path, allowing
  exponential preflight CPU before a tiny output limit could stop encoding.
- P2: decode accepted escaped unpaired UTF-16 surrogates even though encode
  rejected the resulting Python string, breaking the strict round-trip model.

Commit `5f3774c21538792c32d597b8c7724443dac36242` resolved both findings. Completed
container memoization initially bounded repeated-DAG work but introduced
O(unique containers) auxiliary state, violating the approved O(depth) design.
The follow-up correction restores active-path-only cycle state and uses the
output budget as a conservative encoded-byte lower bound; current-node type,
cycle, and depth errors still precede that guard. Strings contribute two
quotes plus UTF-8 scalar widths during their existing validation scan, and dict
keys plus colons are charged lazily without retained sibling state.
Strings now require Unicode scalar values; decode normalizes valid escaped
surrogate pairs and rejects unpaired surrogates before returning a value.
Deterministic bounded-visit, distinct-sibling memory, validation-order,
Unicode, duplicate-key, and source-retention regressions cover the corrected
contracts. The performance rerun at exact PR head `05845fc` found the
completed-memo O(unique containers) P1. A third rerun at exact head `b4e7eda`
found that the intermediate one-byte occurrence guard could rescan large
shared strings and keys. Deterministic large-value counters now cover that
case without wall-clock thresholds. The exact selector passed `8 passed, 237
deselected`, the serde suite passed `389 passed`, and the workspace passed `535
passed`. Final rerun status: `P0=0 P1=0 P2=0 P3=0`.
