# Issue #13 value packages implementation review

Date: 2026-07-15 KST
Reviewed implementation head: `76e89614a96e4ab7ea3af37adfc5fb626f0e4981`

## Method

Three independent read-only reviewers covered six lenses against the approved
spec, plan, `origin/develop..HEAD`, package tests, CI-shaped workspace tests,
wheel isolation, ISO regeneration, bilingual documentation, and the final
diagram. P0/P1 findings blocked delivery until repair and re-review.

## Findings and repairs

| Priority | Lens | Finding | Repair | Result |
|---|---|---|---|---|
| P0 | User/caller, performance | Precision-256 arithmetic returned silently rounded multiplication, division, FX, and accumulation results as exact money | Trapped Decimal `Inexact` and `Rounded` for ordinary arithmetic; explicit `quantize()` locally permits caller-selected rounding; added boundary probes | Closed in `76e8961` |
| P1 | Developer/API, stability | ISO parser accepted empty tables, missing country names, nested fields, and unexpected attributes | Added exact root/table/row/field schema checks while preserving the real `CcyNm IsFund="true"` contract | Closed in `76e8961` |
| P1 | Operator/Ops | A syntactically valid truncated canonical SIX response could become the current snapshot | Canonical URL generation now requires at least 250 source rows and 150 unique currencies; current source is 280/178 | Closed in `76e8961` |
| P2 | Developer/API | Invalid rounding could be ignored by unquantized formatting, and unknown-minor-unit error priority differed by argument | Validate the public rounding argument consistently and resolve the currency quantum before rounding validation | Closed in `76e8961` |
| P2 | Operator/Ops | Provenance tests did not bind every manifest field or full generated output | Assert URLs, dates, digest, bytes, counts, exclusions, and byte-identical full-source regeneration | Closed in `76e8961` |
| P2 | Security/privacy | Wheel verifier labeled imports network-free without denying Python sockets | Deny `socket.socket` and `socket.create_connection` inside all ten isolated import probes | Closed in `76e8961` |

## Final lens results

| Lens | Final evidence | P0 | P1 | P2 |
|---|---|---:|---:|---:|
| Developer/API | Exact exports/signatures, rounding/error priority, serialization, full collection | 0 | 0 | 0 |
| Stability | 5,000 ID runs, 10,000 measure/money runs, concurrency, rollback, arithmetic traps | 0 | 0 | 0 |
| Operator/Ops | Canonical completeness, exact regeneration, release classification, wheel isolation | 0 | 0 | 0 |
| Security/privacy | Payload-free errors, no secret claims, socket-denied imports, no runtime fetch | 0 | 0 | 0 |
| User/caller | Installed-wheel EN/KO examples, explicit policy ownership, rollback guidance | 0 | 0 | 0 |
| Performance | Bounded values/state, no hidden workers or I/O, repeated stability matrices | 0 | 0 | 0 |

Integrated result: **P0=0, P1=0, P2=0**.

Fresh re-review evidence was `47` focused arithmetic/ISO tests, `85` complete
money tests, `18` wheels, `10/10` socket-guarded environments, exact canonical
regeneration, and three independent zero-finding verdicts. No reviewer edited
the implementation.
