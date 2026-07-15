# Issue #13 value packages TDD evidence

Date: 2026-07-15 KST
Issue: #13, milestone `0.2.0`
Implementation evidence head: `76e89614a96e4ab7ea3af37adfc5fb626f0e4981`

## Approved inputs

- Spec SHA-256:
  `0988eef8463eca44f485b91a472fe2958d3dbdf419a783a0c24a53de9f48923e`
- Spec review SHA-256:
  `46509900064343f131d20b224c3eba7c051c063466f8c412e760ded6b8a9de9f`
- Plan SHA-256:
  `81ededc7b59a0d21c2ad9da5727288012fb8a18df60c99e86a1c4bad7c2da812`
- Plan review SHA-256:
  `50d67a09e41d40440a8e362db09b5b2b0c619dacb3d0f6640898bf642c5997b2`

## Captured RED to GREEN transitions

| Boundary | RED evidence | GREEN evidence | Commit |
|---|---|---|---|
| Workspace and distribution scaffolds | Package imports, workspace members, meta extras, release classification, and lock entries were absent | Three stdlib-only distributions build independently; default meta install stays core-only | `1801e1c` |
| UUIDv7 and ULID | Public imports and generators did not exist | 15 tests pass, including parsing, serialization, concurrency, and 5,000-value ordering/uniqueness runs | `991e3bc` |
| Measure and units | Dimension-safe values, parsing, registries, and conversions did not exist | 18 tests pass, including invalid dimensions and 10,000 conversion round trips | `a0e593d` |
| ISO 4217 data | No reproducible currency snapshot or offline generator existed | 7 data/generator tests pass; regenerated `_iso4217.py` is byte-identical | `92cc035` |
| Money | Exact amount, parsing, allocation, exchange, and serialization APIs did not exist | 80 tests pass, including exact signatures, invalid inputs, and 10,000 arithmetic/rounding stability iterations | `7153694` |
| Wheel and meta isolation | No isolated-wheel proof covered focused packages or new extras | All 18 workspace wheels build once; ten Python 3.13.14 environments prove focused, extra, aggregate, dev/all, and default absence contracts | `2c39ae1` |
| Bilingual docs and diagram | Installed-wheel quickstarts, package boundary visual, and locale/link checks were absent | Two README contract tests pass; final SVG/PNG audits find zero crossings, intrusions, geometry, endpoint, or corner failures | `1de187c` |

Only observed failing tests or missing-import collection failures are described
as RED. Review-driven changes that passed existing behavior are not relabeled as
retroactive RED.

## Review-driven workspace repair

The first repository-wide collection found duplicate bare module names across
the three new non-package test directories. The first CI-shaped rerun then
found that the resilience fail-closed classifier did not know the new
distributions. Commit `977b3b0` gave the five colliding test modules
package-specific names and added all three distributions to the remaining
classifier. The repaired CI-shaped command passed `1705` tests with `139`
intentional marker deselections.

The six-lens implementation review then found that Decimal context rounding
could silently change accepted wide values and that a truncated or structurally
nested canonical ISO source could pass generation. New RED tests isolated
multiplication, non-terminating division, FX, accumulation, invalid rounding
priority, empty/missing/nested XML, canonical count bounds, full provenance,
and socket-denied wheel imports. Commit `76e8961` closed every finding; three
independent re-reviews converged at P0=0, P1=0, P2=0.

## Validation convergence

- Package targets: ID `15`, measure `18`, money `85`, meta/docs `6` passed.
- CI-shaped workspace: `1710 passed, 139 deselected`.
- Focused OpenTelemetry SDK lane: `8 passed, 58 deselected` after its dedicated
  dependency sync, proving the earlier missing SDK errors were environmental.
- Static quality: Ruff lint passed; Ruff format checked `165` files; actionlint
  and `git diff --check` passed.
- Packaging: all `18` distributions built as sdist and wheel.
- Value-wheel verifier: all `18` wheels appeared exactly once; focused ID,
  measure, and money metadata had no runtime requirements or root namespace
  initializer; ten isolated environments passed offline, hashed, origin, and
  absence checks.
- Diagram: XML and deterministic CairoSVG rendering passed; the final PNG is
  `2600x1600`; connector, geometry, endpoint, and mixed-corner audits passed.

The evidence commit is intentionally not self-referential. Its SHA and the
fresh post-commit rerun belong to the delivery report and workflow receipt.
