# Issue #15 Testcontainers Fixture Families Code Review

## Scope and method

- Review range: `origin/develop...a88a81da8c3335494782d4a460ca3f5cc19b60c9`
- Review target: PostgreSQL and LocalStack fixture families, shared lifecycle support,
  Redis compatibility, extras and wheel metadata, service CI, bilingual documentation,
  and the mandatory Type A lesson.
- Review method: six deliberately separated main-session lenses followed by an
  integration pass. A native performance-review lane was reclaimed after it made no
  material progress for 5,356.6 seconds; no child-agent result was used. The fallback
  follows the bounded-wait rule and keeps the final judgment with the main session.

## Severity summary

| Severity | Count | Result |
| --- | ---: | --- |
| P0 | 0 | Pass |
| P1 | 0 | Pass |
| P2 | 0 | Pass |
| P3 | 2 | Deferred with rationale |

## Six-lens review

### 1. Performance and resource use

**PASS.** Each wrapper owns one provider container, exposes no background worker or
global registry, and performs synchronous start/stop work only. LocalStack normalizes
the selected services once in `LocalStackServer.__init__` and forwards them once via
`with_services(*services)`. The integration job serializes Redis, PostgreSQL, and
LocalStack under one 30-minute cap instead of multiplying Docker pressure.

### 2. Stability and lifecycle correctness

**PASS.** The shared state/error contract preserves Redis symbol identity while the
new wrappers reject restart-after-close, make repeated `start()`/`close()` safe, clear
details before cleanup, preserve a caller exception when cleanup also fails, and retain
the provider handle when cleanup must be retried. Start failures attempt cleanup before
publishing a typed error. Unit matrices and real-container tests cover success, invalid
input, start failure, cleanup failure, and abnormal context-exit behavior.

### 3. Security and isolation

**PASS.** Image references require an explicit non-`latest` tag or a complete SHA-256
digest and reject URIs, whitespace, controls, and credential-shaped digests. Published
ports are requested and verified as loopback-only. PostgreSQL passwords and LocalStack
credentials are excluded from representations; PostgreSQL URLs percent-encode caller
values. LocalStack ignores ambient AWS credentials and returns only wrapper-owned
synthetic credentials.

### 4. Operations and CI

**PASS.** Every wrapper applies a service-specific Docker label. The service job runs a
Docker preflight, installs the locked `all` extra plus focused test group, runs all three
integration paths serially, and has `timeout-minutes: 30`. English and Korean runbooks
document label inspection, confirmed removal, Ryuk ownership, image defaults, and
provider-specific timeout ownership.

### 5. Developer API and packaging

**PASS.** Public root exports are explicit and provider objects stay private. Optional
provider imports are lazy, so base import does not load boto3, Psycopg, SQLAlchemy, or
the PostgreSQL/LocalStack provider modules. The `postgres`, `aws`, and `all` extras are
focused; caller clients stay in the test group. Wheel metadata and namespace coexistence
are asserted, and the root `bluetape` default/meta-extra contract is unchanged.

### 6. Caller experience and documentation

**PASS.** Paired English/Korean documentation agrees on install choices, supported
services, image defaults, explicit ownership, examples, CI serialization, cleanup, and
Redis-only compatibility. Connection detail objects are immutable; secrets are redacted
from repr while remaining available to caller-owned clients. Failure categories are
stable and service/image context is actionable without exposing raw provider diagnostics.

## Deferred P3 observations

1. **Upstream LocalStack readiness deprecation warning.** Testcontainers 4.14.2 emits a
   warning because its LocalStack provider still uses the deprecated `wait_for_logs`
   helper. Bluetape does not call that helper directly, and all real-service behavior
   passes. Defer removal until a compatible Testcontainers upgrade; the lesson requires
   rerunning the provider, wheel, and serial Docker gates for such upgrades.
2. **Focused environment pytest-asyncio configuration warning.** The package-focused
   `test` group intentionally omits pytest-asyncio because this synchronous package does
   not need it, while the workspace configuration declares `asyncio_mode`. Pytest reports
   the unknown option in that isolated environment, but all 114 focused tests pass. Adding
   an unrelated runtime test dependency would weaken isolation, so retain the warning.

## Integration judgment

The implemented diff satisfies the approved acceptance criteria with no known P0, P1,
or P2 defect. The two P3 observations are external/tooling warnings with explicit,
bounded follow-up conditions and do not weaken the fixture contracts. Final result:
**P0=0, P1=0, P2=0, P3=2; merge-ready subject to exact-head GitHub CI and review-thread
verification.**
