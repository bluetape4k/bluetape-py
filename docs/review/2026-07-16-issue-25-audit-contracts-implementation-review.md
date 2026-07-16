# Issue #25 audit contracts pre-head implementation review

Date: 2026-07-16 KST
Reviewed pre-evidence range:
`4b4df925a0a1cf3d1187cf6f4fb351595a5a02b3..71bf9b1a65c3abac4d9df4e3b805c16fa617dc58`

## Method and boundary

Each implementation task received a specification-conformance review and a
quality review before the next task. Review agents were read-only. When a
quality lane stalled without material output, the main session reclaimed the
bounded review, recorded that fallback in the workflow receipt, and applied
the same P0-P3 criteria. This file records findings and repairs completed
before the candidate exact-head gate; it does not claim that the later six
fresh lenses or independent verifier have passed.

## Findings and repairs

| Priority | Lens | Finding | Repair | Result |
|---|---|---|---|---|
| P1 | Stability/testing | The first isolated-wheel fixture asserted the missing audit build during setup, producing collection/setup errors instead of intentional RED failures | Capture the build once and assert it first inside each audit-dependent test; keep non-audit subprocesses fail-fast | Closed in `9ffe2ba` |
| P1 | Integration | The default meta proof was coupled to the optional audit wheel, so the negative core-only contract could not run when audit was absent | Derive the default wheelhouse independently from meta/core artifacts | Closed in `83cbb4d` |
| P1 | Developer/API | A six-name exact installed export assertion would reject legitimate staged values before their owning tasks reached GREEN | Use an ordered six-error prefix plus attribute resolution during staging, then replace it with the exact final eleven-name tuple in Task 6 | Closed in `c17eb12`, finalized in `9371eb6` |
| P2 | Testing accuracy | Oversized hostile-marker payload inputs mixed disclosure and exact boundary concerns | Separate short disclosure markers from exact hard-ceiling and limit+1 probes | Closed in `3b880b2` |
| P1 | Stability/API | Initial event coverage did not prove every stored field participated in structural equality | Add a field-by-field inequality matrix over all nine event fields | Closed in `349fc61` |
| P1 | Security/operations | Documentation needed to distinguish caller assertions from trusted codec routes and configurable limits from package ceilings | Require adapter allowlisting before parser/header use, reject unsupported pairs before parsing, version adapter-owned limits, and forbid rejected-value logs or metadata policy injection | Closed in `be29264` |
| P2 | Visual quality | Comic Mono rendered middle-dot separators as tofu glyphs in the first PNG | Replace detail-line separators with ASCII slashes, rerender, rerun all audits, and inspect original pixels | Closed in `be29264` |
| P2 | User/caller | The first Korean contract test encouraged repeated parenthetical English literals | Split security assertions by locale and keep the identical executable Python example while using natural Korean semantic wording | Closed in `be29264` |
| P1 | Release safety/integration | The first full workspace replay found that the resilience-owned exhaustive publication set did not classify the new distribution, although the benchmark-owned set and release preflight did | Add `bluetape-audit` to the second fail-closed set and rerun both classification suites | Closed in `64b0bee` |
| P2 | Stability/testing | A test named total validator order proved only that `event_id` won when everything failed, and constructor adjacency stopped after three transitions | Parameterize all 14 validator outcomes by relaxing preceding categories and all eight constructor adjacency pairs | Closed in `71bf9b1` |
| P2 | Operator/docs | Package READMEs showed registry install commands without the root README's current PyPI publication hold | Add bilingual hold guidance, current workspace sync/focused build commands, and a README contract RED/GREEN | Closed in `71bf9b1` |

## Per-task convergence

| Task | Final local evidence before Task 8 | P0 | P1 | P2 | P3 |
|---|---|---:|---:|---:|---:|
| Package/errors/isolation | `25 passed`; reconstructed RED `4 failed` in test bodies | 0 | 0 | 0 | 0 |
| Values/limits | `320 passed`; staged wheel export proof repaired | 0 | 0 | 0 | 0 |
| Event snapshot | `378 passed`; all-field equality matrix present | 0 | 0 | 0 | 0 |
| Adapter validation | `401 passed`; main-session quality fallback after two stalled lanes | 0 | 0 | 0 | 0 |
| Testing helpers | `436 passed`; main-session quality fallback after a stalled lane | 0 | 0 | 0 | 0 |
| Final wheel isolation | `441 passed`, 19 distribution builds, lock current | 0 | 0 | 0 | 0 |
| Docs and diagram | `441 passed`; diagram PASS 19/N/A 2, all audit failures zero | 0 | 0 | 0 | 0 |
| Workspace publication classification repair | First candidate replay `1 failed, 2281 passed, 9 deselected`; focused repair `11 passed` | 0 | 0 | 0 | 0 |
| First exact-head review repairs | Stability P2 and Ops P2 repaired; focused README/event/validation set `102 passed` | 0 | 0 | 0 | 0 |

## Pre-head six-lens readiness

| Lens | Evidence ready for the fresh immutable-head review | Known open P0/P1 before freeze |
|---|---|---:|
| Performance | No payload scan/copy, one bounded metadata copy/pass, fixed datetime key, no runtime I/O | 0 |
| Stability/reliability | Declaration-order validation, private publish-last snapshot, closed precedence, isolated rollback | 0 |
| Security/privacy | Constant error/repr shapes, hostile-marker matrices, bounded safe attributes, no package logging | 0 |
| Operator/Ops | Versioned caller limits, reader/producer compatibility, removal smoke, core-only default, no migration claim | 0 |
| Developer/public API | Exact exports/signatures/decorators, strict built-ins, stdlib-only wheel, submodule-only helpers | 0 |
| User/caller | Identical installed-wheel example, bilingual ownership guidance, SVG+PNG visual, adoption/rollback | 0 |

Fresh independent lens verdicts must be produced at the unchanged committed
candidate head and recorded outside the repository after this ledger commit.
