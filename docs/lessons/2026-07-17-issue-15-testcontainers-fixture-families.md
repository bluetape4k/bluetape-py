# Issue #15 Testcontainers Fixture Families Lessons

## Context and decision

Issue #15 extended the existing Redis-only fixture distribution without turning
it into a generic container framework. PostgreSQL and LocalStack use their
official Testcontainers modules, while Bluetape owns a smaller immutable details,
validation, error, loopback-binding, and cleanup contract.

## Reusable findings

### Advertise only provider-supported timeouts

PostgreSQL provider readiness has no public timeout input in Testcontainers
4.14.2, so the wrapper exposes no false total-deadline promise. LocalStack's
timeout is passed only to its public readiness-log wait; image pull and container
creation remain provider-owned phases.

### Optional providers must be lazy at the public import boundary

`testcontainers.localstack` imports boto3 at module import. Importing the
Bluetape package root therefore loads only the thin adapter module; the official
provider loads inside `start()`, where missing boto3 becomes a sanitized
`dependency-missing` category with the focused install command.

### Selected services and loopback bindings are security and capacity contracts

LocalStack's provider default starts all services, and Docker's ordinary dynamic
publishing can bind wildcard interfaces. The wrappers forward the normalized
service tuple exactly once, request an ephemeral loopback binding, and verify the
actual runtime binding before exposing connection details.

### Provider-owned support containers are not wrapper-owned resources

The adapters do not mutate global Ryuk configuration. Verification distinguishes
the wrapper-owned PostgreSQL/LocalStack service container, which must be removed,
from provider-owned process-wide Ryuk, which may remain until process shutdown.

## Verification evidence

- Docker-free tests cover validation, lifecycle, failure redaction, cleanup
  retry, optional-import isolation, selected services, ambient credentials, and
  URL encoding.
- Serial Docker tests cover Redis, a real PostgreSQL 18 query, a LocalStack S3
  round trip, loopback bindings, and service-container removal.
- Focused wheel smokes prove base, PostgreSQL, AWS, and all-provider install
  shapes without changing the root meta extra.
- The verifier artifact records full pytest, Ruff, build, actionlint, diff, and
  exact-head review evidence.

## Future guard

On provider upgrades, re-check constructor imports, readiness timeout ownership,
port-binding conversion, selected-service forwarding, Ryuk behavior, error
classification, and wheel extras before changing the pinned compatibility line.
