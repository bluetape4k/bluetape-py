# Issue #25 audit contracts TDD evidence

Date: 2026-07-16 KST
Issue: #25, milestone `0.2.0`
Pre-evidence implementation head: `460e8c5e85593785bc4fe713c9a1586233a3561d`

This ledger records observed task evidence before the final evidence commit.
The candidate exact head and fresh canonical replay belong to the workflow
receipt and PR body after this file is committed; this file does not claim that
the later exact-head gate has passed.

## Approved inputs

- Spec SHA-256:
  `31e175cebeb6954d096c9af56930fd9c9542d35a2761cbd73d53d8cd4e46119d`
- Spec review SHA-256:
  `aec6deb0d2a1bee697db78e22f5cf37394e3c4ed6a7cac8d0a8198f42469cb98`
- Plan SHA-256:
  `07803a1bc61d84a68a27e56d86f24a49af15cce87917b25036de0566a2e8f300`
- Plan review SHA-256:
  `5762753ce4aeaa983325b243be329cf389949d658104d1b860701e0fd627c16d`

## Captured RED to GREEN transitions

| Behavior family | Exact RED command and observed reason | GREEN and refactor rerun | Production/evidence commits |
|---|---|---|---|
| Package registration and initial error surface | `uv run pytest packages/bluetape-audit/tests/test_audit_packaging.py packages/bluetape-audit/tests/test_audit_errors.py packages/bluetape/tests/test_audit_wheel_isolation.py -v`; reconstructed at approved plan base with `4 failed` in test bodies because the audit project, wheel, and import did not exist | Registration/error scaffold passed `12` targeted tests after locked all-package/all-extra sync; Task 1 converged with `25 passed` across audit, isolation, and benchmark packaging | `4e46ea2`, final Task 1 `83cbb4d` |
| Fixed-message errors | `uv run pytest packages/bluetape-audit/tests/test_audit_errors.py packages/bluetape-audit/tests/test_audit_packaging.py -v`; `4 failed` because invalid errors had empty/default messages | `11 passed`; the pickle/copy RED then produced `5` reconstruction failures and the explicit-reduction rerun passed `16` | `6d742c4`, `c445d5a` |
| Focused/meta/default wheel isolation | The Task 1 RED command above intentionally failed in test bodies on the missing focused wheel. Fixture-level build assertions were rejected because they produced setup errors rather than missing-feature failures | Final package/isolation set passed `10`; focused and meta-extra imports came from offline wheels, default audit stayed absent, removal preserved namespace/core, and `uv pip check` passed | `1d96591`, `9ffe2ba`, `83cbb4d`, exact final exports `9371eb6` |
| Identity, payload, and limits | `uv run pytest packages/bluetape-audit/tests/test_audit_values.py -v`; failed on missing `AuditIdentity` (the first required value), with payload and limits still absent | `300` value tests and `311` error+value tests passed; the staged installed-wheel rerun passed `320` audit/isolation tests | `e45b6e0`; boundary repair `3b880b2`; staged wheel repair `c17eb12` |
| Immutable event snapshot | `uv run pytest packages/bluetape-audit/tests/test_audit_event.py -v`; `1 failed, 48 skipped` because `AuditEvent` was missing | Initial `49` event tests, `360` owning tests, and `369` audit/isolation tests passed; field-by-field equality refactor reran `58` event and `369` owning tests; integration reached `378` | RED `dbed8f7`; GREEN `562f5e8`; equality coverage `349fc61` |
| Equal-or-stricter adapter validation | `uv run pytest packages/bluetape-audit/tests/test_audit_validation.py -v`; `1 failed, 22 skipped` because `validate_audit_event` was missing | `23` validator tests, `397` package tests, and `401` audit/isolation tests passed | RED `d56cc3b`; GREEN `c15197f` |
| Deterministic testing helpers | `uv run pytest packages/bluetape-audit/tests/test_audit_testing.py -v`; `1 failed, 33 skipped` because `bluetape.audit.testing` was missing | `34` helper tests, `432` package tests, and `436` audit/isolation tests passed; focused sdist and wheel built | RED `cc9e483`; GREEN `8466202` |
| Bilingual docs and SVG+PNG | `uv run pytest packages/bluetape/tests/test_audit_readmes.py -v`; `4 failed` because the marked example, final sections, security/rollout guidance, embeds, and assets were missing | Final README/source-model suite passed `5`; integrated audit/isolation/docs set passed `441`; all SVG audits reported zero failures and the PNG rendered at `2600x1600` | RED `165db5a`; GREEN/assets/ledger `be29264` |
| Fail-closed workspace publication classification | The first candidate replay of `uv run pytest -m 'not observability_sdk and not observability_workspace'` produced `1 failed, 2281 passed, 9 deselected`; the resilience-owned exhaustive publication set omitted `bluetape-audit` while the benchmark-owned set and release preflight already included it | The existing failing test and its benchmark counterpart passed together as `11 passed`; Ruff and diff checks passed before the repair commit | Repair `64b0bee` |
| Publication-hold install guidance | A fresh package README contract asserted the English/Korean publication hold plus workspace sync and focused build commands; it failed because both package READMEs presented registry commands without the current hold | Both locales now distinguish current workspace/build commands from post-publication registry shape; the README contract plus event/validation review repairs passed `102` tests | Repair `71bf9b1` |
| Total validation-order evidence | Review found that one all-invalid validator case proved only the first category and constructor adjacency stopped after three transitions | Parameterized validator cases now relax every preceding category and prove all 14 outcomes; constructor cases prove all eight adjacent declaration-order pairs | Repair `71bf9b1` |
| Distribution-level rollback evidence | Review found that namespace imports after audit removal could still pass if only `bluetape-core` remained | The default/removal probe now requires `bluetape` and `bluetape-core` version `0.1.0` metadata and requires `bluetape-audit` metadata to be absent; the isolated wheel suite passed `4` tests | Repair `4c28d60` |
| Root distribution and install visibility | A new root-doc contract required the audit inventory row, meta/focused install commands, package-layout public registration, and WIP current inventory; it failed because those root authorities omitted the new distribution | EN/KO root docs, package layout, and WIP now agree; all six README/source-model tests passed | Repair `460e8c5` |

Only observed missing-surface or wrong-behavior failures are called RED.
Task 6 finalized an already-owned Task 1 installation contract and is not
relabeled as a new production RED cycle.

## Bounded-operation and performance proof

| Operation | Source and executable proof | Bound |
|---|---|---|
| Payload construction | `AuditPayload.__init__` performs an exact `bytes` type check, truth/`len()` bounds, then retains the original object; `test_payload_accepts_exact_hard_ceiling_without_copy` proves the 1,048,576-byte object is retained by identity | No byte scan or copy; constant Python-level checks plus label validation |
| Policy payload validation | `validate_audit_event` reads only `len(event.payload.data)` and returns the same event; boundary/limit+1 and same-object tests cover the path | No byte iteration, parsing, serialization, or retention |
| Metadata snapshot | `AuditEvent.__init__` prechecks length, performs exactly one built-in shallow `dict.copy`, rechecks the private length, validates only the private mapping, and publishes last; seam tests prove copy-only validation and failed-construction atomicity | One shallow copy and one validation pass over at most 64 entries |
| Datetime equality | `_datetime_key` builds a fixed tuple of seven wall-time scalars, offset, and fold; equality tests cover offset/fold distinctions and every stored event field | Fixed-size scalar key with no UTC normalization or external I/O; offset calculation is delegated to the accepted stdlib timezone object |
| Packaging cost | `uv build --package bluetape-audit` built focused sdist/wheel; `uv build --all-packages` built all 19 workspace distributions | Build-time evidence only; no runtime I/O introduced |

Wall-clock microbenchmarks are deliberately rejected. These operations are
stdlib-only, non-I/O, and source/test-proven by hard ceilings; timing small
Python constructors would add noisy machine-dependent numbers without proving
the no-scan, one-copy, 64-entry, or fixed-key contracts.

## Pre-head validation convergence

- Task 7 final focused set: `441 passed`.
- The first candidate workspace replay exposed the duplicated publication-set
  omission; the bounded repair rerun passed `11` packaging tests at `64b0bee`.
- The next exact-head review found two non-blocking P2 evidence/documentation
  gaps; their RED/GREEN and ordered-test repair passed `102` tests at `71bf9b1`.
- The following review removed a timezone-cost overclaim and strengthened the
  rollback probe to distribution metadata; the wheel suite passed `4` tests at
  `4c28d60`.
- The next Ops review found root visibility drift; its documentation contract
  failed before the repair and all `6` README/source-model tests passed at
  `460e8c5`.
- Static checks: targeted Ruff lint and format passed; `git diff --check`
  passed after the final documentation repair.
- Packaging: all 19 workspace distributions built; `uv lock --check` passed.
- Diagram: `markers=4 connectors=5 cards=6 intrusions=0 crossings=0`,
  `geometry_failures=0`, endpoint PASS, and mixed-corner
  `paths=5 q_bends=2 failures=0`.

Fresh full canonical validation at the committed candidate head remains the
next gate.
