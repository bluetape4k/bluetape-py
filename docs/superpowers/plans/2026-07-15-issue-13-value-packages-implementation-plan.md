# Issue #13 ID, Measure, and Money Implementation Plan

**Goal:** Deliver three independent stdlib-only Python value distributions for
UUID/ULID identifiers, runtime dimension-checked linear measures, and
exact-decimal money values.

**Architecture:** Each focused distribution owns only its domain values and
private validation. `bluetape-id` owns process-local clocks/entropy boundaries;
`bluetape-measure` owns immutable linear units; `bluetape-money` owns a
provenanced generated ISO 4217 snapshot and `Decimal` arithmetic. The meta
distribution exposes opt-in extras without changing its core-only default.

**Approved spec:**
`docs/superpowers/specs/2026-07-15-issue-13-value-packages-design.md`

## Execution Rules

- Work only in `.worktrees/feat/issue-13-id-measure-money` on
  `feat/issue-13-id-measure-money`.
- Apply `$bluetape-py-patterns` and the mandatory test-first micro-cycle to every
  behavior family.
- Every named test is first run RED for the intended missing behavior, then
  rerun GREEN after the smallest implementation, followed by the owning file.
- Do not introduce runtime dependencies, hidden network calls, root
  `bluetape/__init__.py`, production placeholders, or cross-package imports.
- Each commit follows the Lore protocol and includes exact validation evidence.
- PR creation is included in approved scope; merge remains a separate fresh
  approval gate.

## Artifact Map

| Area | Owning files |
|---|---|
| ID | `packages/bluetape-id/**` |
| Measure | `packages/bluetape-measure/**` |
| Money | `packages/bluetape-money/**`, `scripts/update-iso4217.py` |
| Workspace/meta | root and `packages/bluetape/pyproject.toml`, `uv.lock` |
| User docs | root/meta/package README locale pairs, package layout, WIP, changelog |
| Diagram | `docs/images/readme-diagrams/value-packages-boundary.svg` and `.png` |
| Evidence | issue #13 research/spec/plan/review/verifier/lesson files |

## Spec Coverage

| Requirement | Tasks |
|---|---|
| Three independent stdlib-only distributions and exact exports | 1-5 |
| UUIDv4/v7 and random/monotonic ULID behavior | 2 |
| Runtime dimension-checked linear length/time/mass values | 3 |
| Provenanced ISO 4217 current data | 4 |
| Decimal money, formatting, serialization, caller rates | 5 |
| Workspace/meta/default-install/release classification | 1, 6 |
| Bilingual docs and SVG/PNG | 7 |
| Compatibility, persistence, rollback, and deferred dispositions | 7-8 |
| Full tests, six-lens reviews, verifier, lesson, exact head | 8-9 |

## Task 1: Lock package registration and public-contract tests

**Depends on:** approved spec and P0/P1 spec/plan review

**Complexity:** Medium

**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- Create package directories, minimal English/Korean build-valid READMEs, and
  exact `pyproject.toml` files for all three.
- Create package test directories and uniquely named package-local
  `test_id_packaging.py`, `test_measure_packaging.py`, and
  `test_money_packaging.py` files so default pytest collection cannot collide
  on a shared top-level `test_packaging` module name.
- Modify root `pyproject.toml`, `packages/bluetape/pyproject.toml`, `uv.lock`,
  `docs/release/pypi-preflight.md`, and
  `packages/bluetape-benchmark/tests/test_benchmark_packaging.py`.

Each package uses one of these literal metadata records; the common build-system
and backend records follow all three exactly:

```toml
# packages/bluetape-id/pyproject.toml
[project]
name = "bluetape-id"
version = "0.1.0"
description = "Python-native UUID and ULID value helpers for bluetape."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.id"
```

```toml
# packages/bluetape-measure/pyproject.toml
[project]
name = "bluetape-measure"
version = "0.1.0"
description = "Python-native immutable measurement values for bluetape."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.measure"
```

```toml
# packages/bluetape-money/pyproject.toml
[project]
name = "bluetape-money"
version = "0.1.0"
description = "Python-native exact-decimal money values for bluetape."
readme = "README.md"
requires-python = ">=3.13"
dependencies = []

[build-system]
requires = ["uv_build>=0.11.28,<0.12"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "bluetape.money"
```

Root `project.dependencies`, `tool.uv.sources`, and `tool.uv.workspace.members`
receive `bluetape-id`, then `bluetape-measure`, then `bluetape-money` in
alphabetical position. Meta extras are literal singleton lists `id =
["bluetape-id==0.1.0"]`, `measure = ["bluetape-measure==0.1.0"]`, and `money =
["bluetape-money==0.1.0"]`; `values` is those three entries in that order, and
the same three entries are inserted alphabetically into both `dev` and `all`.
The meta `[tool.uv.sources]` table gets the same three workspace mappings. The
default `dependencies = ["bluetape-core==0.1.0"]` remains byte-for-value.

- [ ] Add RED tests for distribution/import names, Python floor, zero runtime
  dependencies, empty initial `__all__`, and absence of root
  `bluetape/__init__.py`. Exact final exports, public values, and signatures are
  introduced and locked only in the task that implements their real owners.
- [ ] Add RED tests that the default meta dependency is still exactly core,
  focused extras are isolated, aggregate `values` contains exactly the three
  packages, and all three join `dev`/`all`.
- [ ] Register workspace dependencies, sources, members, package metadata, and
  meta extras. Use the implicit `bluetape` root namespace: create no root
  initializer and do not call `pkgutil.extend_path`; each leaf has only a typed
  empty `__all__: list[str] = []` until its owning task adds real names.
- [ ] In the same RED/GREEN cycle, add all three names to the executable
  `PUBLISHABLE` set in
  `packages/bluetape-benchmark/tests/test_benchmark_packaging.py` and matching
  rows in `docs/release/pypi-preflight.md`, preserve the historical `v0.1.0`
  target table and HOLD, and make
  `packages/bluetape-benchmark/tests/test_benchmark_packaging.py::test_every_workspace_distribution_is_publishable_or_private`
  pass before committing.
- [ ] Run `uv lock`, `uv sync --all-packages --all-extras --python 3.13.14
  --locked`, the exact package/classifier nodes in the command registry, Ruff,
  format, and all three package builds. Expect positive selection, zero
  failures/skips, and three build-valid focused distributions.
- [ ] Commit an artifact/setup unit with Lore trailers and `Tested:` evidence.

Rollback: revert this commit as one unit and rerun `uv lock` if any package
cannot build/import independently.

## Task 2: Implement `bluetape-id` test-first

**Depends on:** Task 1

**Complexity:** High

**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- `packages/bluetape-id/src/bluetape/id/__init__.py`
- private `_errors.py`, `_entropy.py`, `_uuid.py`, `_ulid.py`
- tests `test_uuid.py`, `test_ulid.py`, `test_concurrency.py`,
  and `test_serialization.py`

- [ ] RED/GREEN UUIDv4 tests: stdlib UUID return, version/variant, uniqueness,
  and no custom global encoder.
- [ ] RED/GREEN UUIDv7 vector tests: 48-bit time, version/variant, random field,
  timestamp extraction, exact canonical string grammar, and invalid
  version/variant/type/brace/URN/uppercase/hyphenless/whitespace forms.
- [ ] RED/GREEN UUIDv7 state tests: injected callbacks not called at
  construction, new-tick random counter seed, same-tick increment, rollback,
  counter overflow logical tick, timestamp overflow, short/wrong entropy, and
  callback exceptions. Prove callbacks run outside the state lock, failure does
  not advance state, and error messages never include entropy bytes.
- [ ] Pin one 10-byte entropy request per UUIDv7 call, big-endian 12-bit seed
  and 62-bit `rand_b` masks, fresh `rand_b`, ignored same-tick seed, and
  overflow-to-logical-new-tick seed reuse with deterministic vectors/call logs.
- [ ] RED/GREEN ULID tests: canonical alphabet/length/max, random generation,
  parse normalization rejection, timestamp extraction, same-tick and rollback
  monotonic increments, 80-bit overflow, entropy failures.
- [ ] Prove per-instance and module convenience behavior under a deterministic
  thread barrier: no duplicates; shared UUIDv7 values are strictly ordered by
  generator acquisition order without claiming caller-thread order.
- [ ] Prove random ULID concurrent uniqueness and shared monotonic ULID strict
  lock-order monotonicity, callback-outside-lock cleanup, rollback/overflow,
  and explicit no process/fork/restart continuity.
- [ ] Run all ID tests, exact-signature nodes, Ruff/format, source import, and
  `uv build --package bluetape-id`. Isolated installed-wheel proof belongs to
  Task 6.
- [ ] Commit the complete ID package with Lore evidence. Do not include measure
  or money production code.

Rollback: revert only the ID commit; workspace scaffold remains valid.

## Task 3: Implement `bluetape-measure` test-first

**Depends on:** Task 1

**Complexity:** Medium

**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- `packages/bluetape-measure/src/bluetape/measure/__init__.py`
- private `_errors.py`, `_core.py`, `_units.py`, `_parse.py`
- tests `test_units.py`, `test_measure.py`, `test_parse.py`,
  and `test_serialization.py`

- [ ] RED/GREEN unit tests for exact fields/signatures, immutability, trimmed
  names/symbols, dimension types, positive finite ratios, booleans, exact
  immutable `BUILTIN_UNITS` order, and built-in definitions.
- [ ] RED/GREEN conversion tests for length/time/mass base and boundary values,
  left-unit-preserving add/subtract, incompatible dimensions, finite scalars,
  division by zero, and no operand mutation.
- [ ] RED/GREEN `equivalent_to()` tests for exact defaults, cross-unit success,
  incompatible-dimension `False`, and boolean/negative/nonfinite tolerances.
- [ ] RED/GREEN parse/format tests for exact symbols, whitespace grammar,
  ASCII signs/decimal/exponent, tab separation, duplicate symbol rejection,
  empty/extra tokens, surrounding whitespace/newlines/underscores/Unicode
  digits/case changes, finite values, 256 input/unit bounds, caller unit sets,
  format specs, exact output, and no locale dependency.
- [ ] RED/GREEN primitive serialization tests for exact keys, repr round-trip,
  missing/extra/wrong types, unknown/duplicate/custom units, one-shot iterable
  materialization, and no registry mutation.
- [ ] Run all measure tests, exact-signature nodes, Ruff/format, build, and a small
  repeated conversion stability loop. Performance threshold is N/A unless
  evidence shows a hot-path regression.
- [ ] Commit the complete measure package with Lore evidence.

Rollback: revert only the measure commit; no other package imports it.

## Task 4: Generate and verify the ISO 4217 snapshot

**Depends on:** Task 1

**Complexity:** High

**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- `scripts/update-iso4217.py`
- `packages/bluetape-money/src/bluetape/money/_iso4217.py`
- `packages/bluetape-money/tests/fixtures/iso4217-list-one-sample.xml`
- `docs/research/sources/iso4217/2026-07-15-list-one.xml`
- `docs/research/sources/iso4217/2026-07-15-list-one.provenance.json`
- tests `test_iso4217_generation.py`, `test_iso4217_data.py`

- [ ] Download the current SIX List One XML explicitly and never execute it as
  code. Use canonical endpoint
  `https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml`
  with HTTPS-only bounded fail-fast curl: `--fail --show-error --silent
  --location --proto '=https' --tlsv1.2 --connect-timeout 10 --max-time 30`.
  Persist canonical/effective URL, UTC timestamp, bytes, SHA-256, source rows,
  unique currencies, exclusions, and output path in the manifest/header.
- [ ] Preserve a copyright-safe Korean summary of the ISO/RFC/ULID decisions in
  `~/work/bluetape4k/bluetape4k-wiki/research/`, including source URLs,
  retrieval metadata, implications, and follow-up recommendations. Validate
  with `git diff --check`, `gno update`, `gno embed --collection
  bluetape4k-wiki`, and a representative `gno search`; commit and push the wiki
  artifact separately because it is durable cross-session research evidence.
- [ ] RED tests for deterministic offline generation from the committed sample,
  stable sorting, entity-row deduplication by alphabetic code, numeric-code
  uniqueness, identical duplicate metadata, conflict rejection, exact
  provenance constants, nullable minor units, and XML schema drift fail-closed
  behavior. Bound input to 2 MiB, source rows to 1,024, unique currencies to
  512, reject DTD/entity markers,
  reject output/input aliasing, and prove an existing output remains unchanged
  on every failure.
- [ ] Implement the stdlib `ElementTree` maintainer script with required
  `--input`, `--output`, `--source-url`, and `--retrieved-date`; no implicit URL
  fetch. Write a same-directory temporary file, flush/close, then `os.replace`;
  clean the temp on validation, serialization, replacement, interruption, and
  cleanup failures while preserving the old output.
- [ ] Generate the package table from current List One, review changes for
  `EUR`/`USD`/`KRW`/`JPY`/`CNY`, reject `XXX`/`XTS` as money currencies, and
  verify alphabetic/numeric uniqueness. Public Currency lookup belongs only to
  Task 5 so this data-only task ends green without placeholder exports.
- [ ] Run deterministic regeneration to a temporary path and byte-compare,
  data-generation tests, Ruff/format, and diff check.
- [ ] Prove hermeticity with socket/URL access forced to fail, source-scan
  production/build paths for network clients, and run `UV_OFFLINE=1 uv build
  --package bluetape-money` after dependency preparation; require zero attempted
  connections.
- [ ] Define stable non-zero diagnostic categories for size/schema/conflict/
  bounds/alias/serialization/replace failures. Success prints only bounded
  provenance/count/output metadata; stderr never prints XML rows/source content.
- [ ] Commit ISO provenance, generator, table, and currency values with Lore
  evidence.

Rollback: revert the data commit; never retain partially generated output.

## Task 5: Implement exact-decimal money and exchange rates test-first

**Depends on:** Task 4

**Complexity:** High

**Pattern skill:** `$bluetape-py-patterns`

**Files:**

- private `_errors.py`, `_currency.py`, `_decimal.py`, `_money.py`,
  `_exchange.py`, `_parse.py`
- public `packages/bluetape-money/src/bluetape/money/__init__.py`
- tests `test_money.py`, `test_exchange.py`, `test_parse.py`,
  `test_serialization.py`, and `test_currency.py`

- [ ] RED/GREEN construction tests for Decimal/int/string, explicit rejection
  of every float/bool/nonfinite/malformed value, immutable fields, and currency
  validation. Cover 512-character input, 256 coefficient digits, exponent
  bounds, Unicode digits, underscores, surrounding whitespace, arithmetic
  result bounds, and payload-free error messages.
- [ ] RED/GREEN Currency exact-row construction, alphabetic/numeric lookup,
  five constants, forged metadata, whitespace/case/numeric boundaries,
  `XXX`/`XTS`, missing codes, and nullable minor units.
- [ ] RED/GREEN arithmetic tests for same-currency add/subtract/compare,
  negation/abs, exact scalar multiply/divide, zero division, mismatches, large
  exponent/context boundaries, and no automatic quantization. Prove a fixed
  package-local precision-256 context with `Emin/Emax` bounds, ambient-context
  non-mutation/non-influence, and exact exception mapping.
- [ ] RED/GREEN minor-unit and quantize tests for 0/2/3-digit currencies,
  half-even default, caller rounding override, exact-only extraction, missing
  minor units, negative amounts, and overflow-free Python integers. Missing
  minor units always raise `InvalidCurrencyError`, even with rounding supplied.
- [ ] RED/GREEN canonical parse/format/serialization tests for exact key/space
  grammar, fixed-point output, exponent input, extra/missing keys, numeric code,
  `XXX`/`XTS`, and float-shaped JSON values.
- [ ] RED/GREEN exchange tests for positive finite exact rates, same-currency
  identity, both directions, unrelated currency, package-local Decimal context
  isolation, unquantized result, and zero/negative/float rates.
- [ ] RED/GREEN `sum_money` empty and mixed-value behavior.
- [ ] Run all money tests, exact-signature nodes, Ruff/format, build, and
  repeated arithmetic/parse stability matrix. Isolated installed-wheel proof
  belongs to Task 6.
- [ ] Commit money values and rates with Lore evidence.

Rollback: revert only the money behavior commit; retain reviewed ISO data if
currency tests still pass.

## Task 6: Verify packaging, default isolation, and release classification

**Depends on:** Tasks 2-5

**Complexity:** Medium

**Pattern skill:** `$bluetape-py-patterns`

- [ ] Reverify that every workspace member is exactly one of publishable/private
  and the three packages remain excluded from historical `v0.1.0` targets.
- [ ] Add `scripts/verify-value-wheels.sh`. Reuse/extract common logic from
  `scripts/verify-observability-wheels.sh` only where duplication is concrete;
  otherwise record why domain-specific probes remain separate. Build every
  workspace wheel into one temporary directory. For each clean environment,
  first use `uv export --locked --no-emit-local` for the selected meta extra and
  `uv pip sync --require-hashes` in an explicit network-enabled dependency
  preparation phase. Record each locked external name, version, and hash. Then
  disable network, install the required workspace wheels with `--no-deps
  --no-index --find-links <dist>`, and verify direct focused installs, each meta
  extra, aggregate `values`, `dev`, `all`, and the default meta wheel. Require
  exact wheel counts, `uv pip check`, `python -I` outside the worktree, and
  module-origin assertions. The default must expose none of the three imports.
  Compact JSON records the lock digest, external artifacts, local wheel hashes,
  environment/extra, origins, and network-free probe result. No resolver may
  access an index after the preparation boundary.
- [ ] Assert wheel metadata has no runtime dependency for each focused package
  and no package contains a root namespace initializer.
- [ ] Confirm generic CI covers the paths and no dedicated workflow is needed;
  run `actionlint` after any workflow edit.
- [ ] Enumerate workflows and record evidence-backed N/A for Nightly, examples,
  and coverage aggregation: generic pytest/build discovery owns these pure
  packages and no additional registration chain exists.
- [ ] Commit packaging/release integration with Lore evidence.

## Task 7: Synchronize bilingual docs and create SVG+PNG architecture

**Depends on:** Tasks 2-6

**Complexity:** Medium

**Pattern skills:** `$bluetape-py-patterns`, `$bluetape-diagram`

- [ ] Update all three package README English/Korean pairs with install,
  selection, examples, failure/ownership behavior, data provenance, and
  non-goals. Update root/meta README pairs, package layout, WIP, changelog,
  research indexes, and verify release-preflight parity without first enabling
  classification here.
- [ ] Add source-equivalent executable EN/KO examples and marker/link/section
  parity tests. Cover focused/meta installs, IDs-not-secrets/distributed-order,
  measure strict parsing/custom units/equivalence, and money float rejection,
  minor-unit rounding, and both FX directions. Extract and execute snippets
  from installed wheels in clean environments.
- [ ] In every applicable package README locale, pin generator-state reset,
  exact versionless schemas, custom-unit registry ownership, current-ISO
  non-archival limits, focused/extra uninstall rollback, and deferred KSUID/
  Snowflake/measure/locale/FX dispositions. Update WIP with the same triggers
  and make locale section-parity tests assert these headings/contracts.
- [ ] Create `value-packages-boundary.svg` from implementing source, not an old
  render. Use the approved diagram fonts/theme and show independent package
  boundaries, stdlib/data sources, meta extras, and caller-owned inputs.
- [ ] Invoke `$bluetape-diagram`, embed the PNG in root `README.md` and
  `README.ko.md`, link the SVG source beside it, and record
  `docs/review/2026-07-15-issue-13-value-packages-diagram-review.md`.
- [ ] Run `xmllint`, CairoSVG at 2x, connector/geometry/endpoint/mixed-corner
  audits, fallback entity/relationship counts, and `git diff --check`.
- [ ] Inspect the full-size PNG for clipping, alignment, unexplained colors,
  connectors, arrowheads, and whitespace. Record exact evidence in a diagram
  review file, including asset hashes, root EN/KO link targets, 2x render
  reproduction, fallback entity/relationship counts, and original-detail
  inspection.
- [ ] Commit synchronized docs and both generated assets with Lore evidence.

## Task 8: Full verification, review convergence, and lesson gate

**Depends on:** Tasks 1-7

**Complexity:** High

**Pattern skills:** `$bluetape-py-patterns`, `$verification-before-completion`

- [ ] Fetch and rebase onto current `origin/develop` before final convergence.
  After conflicts or lock regeneration, invalidate all pre-rebase review,
  verifier, diagram, and acceptance claims.
- [ ] Run targeted suites, then generic CI-equivalent pytest excluding provider
  markers, the focused observability lanes, Ruff check/format, all-package
  build, actionlint, and diff check from a clean sync.
- [ ] Use these exact generic commands after the clean sync:

  ```bash
  uv sync --all-packages --extra fory --python 3.13.14 --locked
  uv run --package bluetape-serde --extra fory --python 3.13.14 pytest \
    --strict-markers \
    -m "not testcontainers and not native_compression and not observability_sdk"
  uv run ruff check .
  uv run ruff format --check .
  uv build --all-packages
  actionlint
  git diff --check
  ```
- [ ] Re-establish every invalidated specialized claim after the rebase with
  these exact commands, before review convergence:

  ```bash
  uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests -q
  uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests -q
  uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests -q

  iso_tmp="$(mktemp)"
  trap 'rm -f "$iso_tmp"' EXIT
  uv run python scripts/update-iso4217.py \
    --input docs/research/sources/iso4217/2026-07-15-list-one.xml \
    --output "$iso_tmp" \
    --source-url https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml \
    --retrieved-date 2026-07-15
  cmp "$iso_tmp" packages/bluetape-money/src/bluetape/money/_iso4217.py
  UV_OFFLINE=1 uv run --package bluetape-money --python 3.13.14 \
    pytest packages/bluetape-money/tests/test_iso4217_generation.py::test_money_build_and_import_are_network_free -q

  scripts/verify-value-wheels.sh
  uv run pytest packages/bluetape/tests/test_value_readmes.py::test_value_readme_examples_execute_from_installed_wheels -q
  uv run pytest packages/bluetape/tests/test_value_readmes.py::test_value_readme_locale_sections_and_links_match -q

  xmllint --noout docs/images/readme-diagrams/value-packages-boundary.svg
  cairosvg docs/images/readme-diagrams/value-packages-boundary.svg \
    -o docs/images/readme-diagrams/value-packages-boundary.png -s 2
  python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" \
    docs/images/readme-diagrams/value-packages-boundary.svg
  python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" \
    --fail-diagonal docs/images/readme-diagrams/value-packages-boundary.svg
  python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" \
    docs/images/readme-diagrams/value-packages-boundary.svg
  python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" \
    docs/images/readme-diagrams/value-packages-boundary.svg
  sha256sum docs/images/readme-diagrams/value-packages-boundary.svg \
    docs/images/readme-diagrams/value-packages-boundary.png
  git diff --exit-code -- docs/images/readme-diagrams/value-packages-boundary.png
  ```
- [ ] Then run the existing focused observability API and SDK marker commands
  from `.github/workflows/ci.yml`; require positive selected-test counts and
  zero failures/errors/skips for the SDK-selected JUnit report.
- [ ] Run performance/stability scan: ID concurrency/overflow, measure repeated
  conversions, money Decimal context/rounding, no background work/network,
  and bounded parsing/data generation.
- [ ] Run six independent code-review perspectives and integrate all findings.
  P0/P1 must be zero; P2/P3 are fixed or explicitly deferred with issue/rationale.
- [ ] Run verifier checklist against the exact worktree head and acceptance map.
- [ ] Write the required Type A lesson. Include the initial baseline environment
  false failure, CI-marker correction, and worktree-path repair as reusable
  evidence without recording secrets.
- [ ] Commit evidence and lesson with Lore trailers.
- [ ] Capture the evidence-commit HEAD, rerun both the generic and specialized
  Task 8 blocks above without edits, assert HEAD is unchanged, and bind wheel,
  README, ISO regeneration, diagram, review, verifier, and every acceptance
  artifact to that exact SHA.

## Task 9: Exact-head PR creation and CI verification

**Depends on:** Task 8

**Complexity:** Medium

**Pattern skill:** `$bluetape-workflow`

- [ ] Without rebasing or editing after Task 8, push
  `feat/issue-13-id-measure-money` and create a PR to `develop` in
  `bluetape4k/bluetape-py`; assign `debop`, milestone `0.2.0`, label
  `enhancement`.
- [ ] Use an English PR body ending with `## DoD Status`, linking issue #13,
  exact tests, P0/P1 evidence, diagrams, lesson, and known N/A items.
- [ ] Verify live PR head equals local head, CI checks pass, reviews/threads are
  resolved, and required human-review artifacts apply to the same head.
- [ ] Report merge-ready exact-head evidence and stop for a fresh merge approval.

Post-approval closeout: rebase merge, verify merged SHA/issue/milestone state,
sync local `develop`, rerun proportionate smoke checks, then remove the merged
worktree and local/remote feature branch.

## Forward Rollback Matrix

Use history-preserving `git revert`; never rewrite shared history or reuse
evidence from a pre-rollback head.

| Reverted unit | Required downstream reconciliation |
|---|---|
| ID package | Remove ID meta/workspace/classifier/docs/diagram claims, regenerate lock, rerun wheel/full reviews |
| Measure package | Remove measure registration/docs/diagram claims, regenerate lock, rerun custom-unit/full reviews |
| Money ISO data | Revert dependent money behavior or restore a reviewed snapshot; rerun provenance/hermetic/full gates |
| Money behavior | Remove money meta/workspace/classifier/docs/diagram claims, regenerate lock, rerun wheel/full reviews |
| Packaging/docs | Reconcile all registrations and lock, then regenerate diagram/review/verifier/PR artifacts |

Every rollback invalidates later acceptance, lesson, PR-body, and exact-head
artifacts until regenerated against the new HEAD.

## Exact Task Command Registry

Each RED node must fail only for its named missing assertion; each GREEN command
must select at least one test with zero failures/errors/skips. The TDD ledger
records node ID, intended RED message, fixture/input, GREEN count, owning-file
count, wheel path, temp environment, and module origin.

```bash
uv run pytest packages/bluetape-id/tests/test_id_packaging.py -q
uv run pytest packages/bluetape-measure/tests/test_measure_packaging.py -q
uv run pytest packages/bluetape-money/tests/test_money_packaging.py -q
uv run pytest packages/bluetape-benchmark/tests/test_benchmark_packaging.py::test_every_workspace_distribution_is_publishable_or_private -q

uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_uuid.py -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_ulid.py packages/bluetape-id/tests/test_concurrency.py -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests -q
uv build --package bluetape-id

uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_units.py packages/bluetape-measure/tests/test_measure.py -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_parse.py packages/bluetape-measure/tests/test_serialization.py -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests -q
uv build --package bluetape-measure

uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_iso4217_generation.py packages/bluetape-money/tests/test_iso4217_data.py -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_currency.py packages/bluetape-money/tests/test_money.py packages/bluetape-money/tests/test_exchange.py -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_parse.py packages/bluetape-money/tests/test_serialization.py -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests -q
UV_OFFLINE=1 uv build --package bluetape-money

scripts/verify-value-wheels.sh

xmllint --noout docs/images/readme-diagrams/value-packages-boundary.svg
cairosvg docs/images/readme-diagrams/value-packages-boundary.svg \
  -o docs/images/readme-diagrams/value-packages-boundary.png -s 2
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-connector-audit.py" \
  docs/images/readme-diagrams/value-packages-boundary.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-geometry-audit.py" \
  --fail-diagonal docs/images/readme-diagrams/value-packages-boundary.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-endpoint-audit.py" \
  docs/images/readme-diagrams/value-packages-boundary.svg
python3 "${CODEX_HOME:-$HOME/.codex}/skills/bluetape-diagram/scripts/diagram-mixed-corner-audit.py" \
  docs/images/readme-diagrams/value-packages-boundary.svg
sha256sum docs/images/readme-diagrams/value-packages-boundary.svg \
  docs/images/readme-diagrams/value-packages-boundary.png
```

### Stable RED/GREEN node contracts

The following nodes, fixtures, initial RED reasons, and GREEN assertions are
fixed before implementation. Each exact node command below must select one test
and change only from the named RED to GREEN; the owning-file commands above must
then pass with no skips.

| Full node ID | Concrete fixture/input | Intended initial RED | Required GREEN assertion |
|---|---|---|---|
| `packages/bluetape-id/tests/test_id_packaging.py::test_distribution_metadata_is_stdlib_only` | literal ID TOML/import | package absent | exact metadata, empty deps, implicit namespace |
| `packages/bluetape-measure/tests/test_measure_packaging.py::test_distribution_metadata_is_stdlib_only` | literal Measure TOML/import | package absent | exact metadata, empty deps, implicit namespace |
| `packages/bluetape-money/tests/test_money_packaging.py::test_distribution_metadata_is_stdlib_only` | literal Money TOML/import | package absent | exact metadata, empty deps, implicit namespace |
| `packages/bluetape/tests/test_value_packaging.py::test_meta_value_extras_are_exact_and_default_stays_core_only` | parsed root/meta TOML | extras absent | exact singleton/values/dev/all ordering and core-only default |
| `packages/bluetape-benchmark/tests/test_benchmark_packaging.py::test_every_workspace_distribution_is_publishable_or_private` | workspace metadata | new packages unclassified | exact publishable/private partition and preflight rows |
| `packages/bluetape-id/tests/test_uuid.py::test_uuid4_delegates_to_stdlib_contract` | patched stdlib UUID factory plus 128-call sample | wrapper absent | stdlib UUID values, v4/RFC variant, delegated call, uniqueness |
| `packages/bluetape-id/tests/test_uuid.py::test_uuid7_public_signatures_are_exact` | `inspect.signature` expected map | names absent | exports and signatures equal spec |
| `packages/bluetape-id/tests/test_uuid.py::test_uuid7_rfc_vector` | clock `0x0123456789AB`, entropy `0x0ABC` + 62-bit vector | constructor absent | exact UUID bits/version/variant/timestamp |
| `packages/bluetape-id/tests/test_uuid.py::test_uuid7_same_tick_rollback_and_overflow` | clocks same/rollback and counter `0xFFF` | state logic absent | lock-order monotonic logical ticks and overflow behavior |
| `packages/bluetape-id/tests/test_uuid.py::test_uuid7_entropy_mapping_and_failure_is_atomic` | 10-byte log plus short/raising entropy | mapping absent | one call, exact masks, unchanged state, payload-free error |
| `packages/bluetape-id/tests/test_ulid.py::test_random_ulid_and_module_convenience_contract` | fixed clock, two 10-byte entropy vectors, patched shared generator | APIs absent | exact canonical values, one entropy call each, module delegation, no monotonic claim |
| `packages/bluetape-id/tests/test_ulid.py::test_ulid_canonical_boundaries` | zero/max/ambiguous/lowercase/overflow strings | parser absent | exact canonical acceptance and rejection |
| `packages/bluetape-id/tests/test_concurrency.py::test_monotonic_ulid_shared_instance_is_lock_ordered` | barrier, fixed clock, deterministic entropy | generator absent | unique lexically ordered results by lock acquisition |
| `packages/bluetape-id/tests/test_concurrency.py::test_module_convenience_concurrency_contracts` | thread barriers around shared `uuid7()` and random `ulid()` | shared generators absent | UUIDv7 unique/lock-ordered; random ULID unique only; no caller-thread-order claim |
| `packages/bluetape-measure/tests/test_units.py::test_measure_public_signatures_are_exact` | executable declaration/`inspect.signature` map | API absent | import succeeds and signatures equal spec |
| `packages/bluetape-measure/tests/test_units.py::test_builtin_units_are_immutable_and_ordered` | authoritative ten-row spec table | constants absent | enum values and every tuple field/order match exactly |
| `packages/bluetape-measure/tests/test_measure.py::test_conversion_and_arithmetic_reject_dimensions` | `1 km`, `250 m`, `1 s` | behavior absent | conversions/arithmetic exact; cross-dimension rejected |
| `packages/bluetape-measure/tests/test_measure.py::test_equivalent_to_contract` | `1 km`, `1000 m`, invalid tolerances | method absent | defaults/signature, true equivalence, false dimension, validation |
| `packages/bluetape-measure/tests/test_parse.py::test_parse_measure_ascii_grammar` | boundary table including `1.5e2\tcm` and Unicode/space failures | parser absent | exact grammar, 256-char bound, symbols, finite amount |
| `packages/bluetape-measure/tests/test_serialization.py::test_custom_unit_serialization_requires_registry` | one-shot custom-unit iterable and duplicate symbols | codec absent | exact dict round-trip, one materialization, no global mutation |
| `packages/bluetape-money/tests/test_iso4217_generation.py::test_iso4217_generation_is_deterministic` | committed sample and two temp outputs | updater absent | byte-identical sorted output |
| `packages/bluetape-money/tests/test_iso4217_generation.py::test_iso4217_conflicts_and_schema_drift_fail_closed` | duplicate/conflict/DTD/2-MiB/1,024-row/512-code cases | validation absent | stable diagnostic category and no output mutation |
| `packages/bluetape-money/tests/test_iso4217_generation.py::test_iso4217_atomic_replace_preserves_previous_output` | preexisting sentinel plus injected replace/cleanup faults | atomic writer absent | old bytes preserved; temp removed |
| `packages/bluetape-money/tests/test_iso4217_data.py::test_iso4217_provenance_matches_source` | committed XML/JSON/generated header | snapshot absent | URL/date/count/SHA and exclusions agree exactly |
| `packages/bluetape-money/tests/test_iso4217_generation.py::test_money_build_and_import_are_network_free` | denied socket/URL hooks plus offline build | hermetic proof absent | zero attempted connections and successful import/build |
| `packages/bluetape-money/tests/test_currency.py::test_money_public_signatures_are_exact` | `inspect.signature` expected map | API absent | exports and signatures equal spec |
| `packages/bluetape-money/tests/test_currency.py::test_currency_requires_exact_generated_row` | USD/numeric/case plus forged/XXX/XTS rows | Currency absent | generated-row identity and boundary rejection |
| `packages/bluetape-money/tests/test_money.py::test_money_rejects_float_and_unbounded_decimal` | float/bool/nonfinite/257-digit/exponent-257 table | validation absent | only bounded exact Decimal/int/ASCII string accepted |
| `packages/bluetape-money/tests/test_money.py::test_money_arithmetic_and_context_contract` | hostile ambient context and same/mixed currencies | arithmetic absent | local context result, ambient unchanged, exact errors |
| `packages/bluetape-money/tests/test_money.py::test_minor_unit_and_rounding_contract` | JPY/USD/KWD and no-minor-unit row | minor-unit API absent | 0/2/3 digit behavior; `None` always invalid |
| `packages/bluetape-money/tests/test_exchange.py::test_exchange_rate_both_directions` | USD/EUR rate and reverse/unrelated/identity cases | FX absent | exact both-direction conversion and validation |
| `packages/bluetape-money/tests/test_money.py::test_sum_money_empty_and_mixed_contract` | empty, same-currency, mixed-currency, wrong-type iterables | aggregator absent | zero in requested currency, exact sum, mismatch/type rejection |
| `packages/bluetape-money/tests/test_serialization.py::test_money_primitive_schema_is_exact` | exact dicts plus missing/extra/float-shaped values | codec absent | versionless schema round-trip and strict rejection |
| `packages/bluetape/tests/test_value_packaging.py::test_value_wheel_verifier_reports_exact_origins_and_isolation` | verifier compact JSON | verifier absent | lock/hash/origin/network/default isolation fields exact |
| `packages/bluetape/tests/test_value_readmes.py::test_value_readme_examples_execute_from_installed_wheels` | extracted EN/KO marker pairs | examples absent | source-equivalent snippets pass outside checkout |
| `packages/bluetape/tests/test_value_readmes.py::test_value_readme_locale_sections_and_links_match` | required headings/link targets | sections absent | locale contract headings and PNG/SVG targets match |

Exact per-node invocations:

```bash
uv run pytest packages/bluetape-id/tests/test_id_packaging.py::test_distribution_metadata_is_stdlib_only -q
uv run pytest packages/bluetape-measure/tests/test_measure_packaging.py::test_distribution_metadata_is_stdlib_only -q
uv run pytest packages/bluetape-money/tests/test_money_packaging.py::test_distribution_metadata_is_stdlib_only -q
uv run pytest packages/bluetape/tests/test_value_packaging.py::test_meta_value_extras_are_exact_and_default_stays_core_only -q
uv run pytest packages/bluetape-benchmark/tests/test_benchmark_packaging.py::test_every_workspace_distribution_is_publishable_or_private -q

uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_uuid.py::test_uuid4_delegates_to_stdlib_contract -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_uuid.py::test_uuid7_public_signatures_are_exact -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_uuid.py::test_uuid7_rfc_vector -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_uuid.py::test_uuid7_same_tick_rollback_and_overflow -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_uuid.py::test_uuid7_entropy_mapping_and_failure_is_atomic -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_ulid.py::test_random_ulid_and_module_convenience_contract -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_ulid.py::test_ulid_canonical_boundaries -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_concurrency.py::test_monotonic_ulid_shared_instance_is_lock_ordered -q
uv run --package bluetape-id --python 3.13.14 pytest packages/bluetape-id/tests/test_concurrency.py::test_module_convenience_concurrency_contracts -q

uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_units.py::test_measure_public_signatures_are_exact -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_units.py::test_builtin_units_are_immutable_and_ordered -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_measure.py::test_conversion_and_arithmetic_reject_dimensions -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_measure.py::test_equivalent_to_contract -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_parse.py::test_parse_measure_ascii_grammar -q
uv run --package bluetape-measure --python 3.13.14 pytest packages/bluetape-measure/tests/test_serialization.py::test_custom_unit_serialization_requires_registry -q

uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_iso4217_generation.py::test_iso4217_generation_is_deterministic -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_iso4217_generation.py::test_iso4217_conflicts_and_schema_drift_fail_closed -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_iso4217_generation.py::test_iso4217_atomic_replace_preserves_previous_output -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_iso4217_data.py::test_iso4217_provenance_matches_source -q
UV_OFFLINE=1 uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_iso4217_generation.py::test_money_build_and_import_are_network_free -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_currency.py::test_money_public_signatures_are_exact -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_currency.py::test_currency_requires_exact_generated_row -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_money.py::test_money_rejects_float_and_unbounded_decimal -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_money.py::test_money_arithmetic_and_context_contract -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_money.py::test_minor_unit_and_rounding_contract -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_exchange.py::test_exchange_rate_both_directions -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_money.py::test_sum_money_empty_and_mixed_contract -q
uv run --package bluetape-money --python 3.13.14 pytest packages/bluetape-money/tests/test_serialization.py::test_money_primitive_schema_is_exact -q

uv run pytest packages/bluetape/tests/test_value_packaging.py::test_value_wheel_verifier_reports_exact_origins_and_isolation -q
uv run pytest packages/bluetape/tests/test_value_readmes.py::test_value_readme_examples_execute_from_installed_wheels -q
uv run pytest packages/bluetape/tests/test_value_readmes.py::test_value_readme_locale_sections_and_links_match -q
```

The ISO byte proof is the literal updater/`cmp` block in Task 8. The wheel and
README nodes consume their generated compact JSON and installed-wheel snippet
evidence rather than trusting exit status alone. The TDD ledger records the
observed RED text, GREEN count, owning-file count, wheel path, temporary
environment, module origin, and artifact hashes without changing this contract.
