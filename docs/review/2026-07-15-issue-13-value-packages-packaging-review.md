# Issue #13 Value Packages Packaging Review

Date: 2026-07-15

## Verified Integration

- `bluetape-id`, `bluetape-measure`, and `bluetape-money` are each classified
  as publishable workspace distributions.
- The historical `v0.1.0` target table remains limited to its original four
  distributions; the three value packages are not release targets.
- `scripts/verify-value-wheels.sh` builds exactly one wheel for every workspace
  distribution and verifies focused installs, `id`, `measure`, `money`,
  `values`, `dev`, `all`, and default meta environments.
- External dependencies are prepared from `uv export --locked --no-emit-local`
  with hashes. Workspace wheels are installed only after switching to
  `UV_OFFLINE=1`, `--offline`, `--no-index`, and `--no-deps`.
- Every environment passes `uv pip check` and a `python -I` module-origin
  probe outside the checkout. The default meta environment exposes only
  `bluetape.core` and none of the three value modules.
- Focused wheel metadata has no runtime dependency and none of the focused
  wheels contains `bluetape/__init__.py`.

## Workflow Registration Review

The repository contains only `.github/workflows/ci.yml` and
`.github/workflows/fory-conformance.yml`. Generic CI has no path filter and
already runs workspace Ruff, pytest discovery, and `uv build --all-packages`.
No workflow file changed.

- Dedicated value-package workflow: N/A; the packages are stdlib/data-only and
  generic discovery executes their tests and builds.
- Nightly registration: N/A; there is no nightly workflow or external service,
  container, clock, or provider matrix owned by these packages.
- Example registration: N/A at this task; installed-wheel README examples are
  added and verified in the documentation task.
- Coverage aggregation: N/A; the repository has no coverage aggregation
  workflow or registration chain, and this change does not introduce one.
- `actionlint`: N/A for this task because no workflow file changed.

## Duplication Decision

The value-wheel verifier keeps domain-specific probes separate from
`verify-observability-wheels.sh`. Both scripts share only generic shell setup,
wheel counting, and isolated import concepts. The observability verifier owns
OpenTelemetry API/SDK and Redis observer behavior; the value verifier owns
three-way focused/meta-extra/default absence matrices, lock hashes, every
workspace wheel hash, and stdlib-only focused metadata. Extracting a common
framework would add a new abstraction without a stable shared contract.
