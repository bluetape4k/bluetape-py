# Issue #57 Redis Testcontainers Wrapper Lessons

## Context

Issue #57 added a focused `bluetape-testcontainers` distribution and an
ecosystem-owned Redis 8 test server. The hard boundary was not starting Redis;
it was making every hidden provider step obey the public timeout, diagnostics,
and cleanup contract while keeping the default `bluetape` install provider-free.

## Decisions

- Build on Testcontainers core `DockerContainer`, not its Redis module, so the
  ecosystem owns the `redis:8` compatibility line, readiness command, dynamic
  port, and connection details without adding redis-py.
- Check the local image first and run a missing-image pull in a bounded child
  process. Docker SDK `images.pull()` hardcodes an unbounded request path even
  when its surrounding client has a timeout.
- Skip Testcontainers Ryuk for this wrapper. Ryuk performs a separate image
  acquisition and connection loop outside `startup_timeout`; the wrapper
  instead starts the core container through the bounded Docker client, labels
  it, and owns explicit cleanup.
- Suppress provider exception chaining with `from None`. A redacted public
  message alone is insufficient because a chained traceback can still expose
  daemon paths, registry responses, or credentials.
- Retain the container reference after termination failure. Both startup and
  context-manager cleanup paths tell the caller to retry `close()`.
- Keep Docker-backed verification serial and separate from the provider-free
  default wheel smoke test.

## Outcome and evidence

- Unit tests cover validation, lifecycle transitions, cleanup retry, provider
  redaction, bounded pull, no-Ryuk startup, IPv6 URLs, and package isolation.
- A real Docker test starts two sequential Redis 8 servers, performs RESP
  `PING`/`SET`/`GET`, and proves stale state does not cross lifecycles.
- The resolved local compatibility image was
  `redis@sha256:2838d5524559494f6f1cd66e97e76b200d64a633a8614200620755ed395daf32`.
- Full-suite, Ruff, all-package build, workflow lint, diff hygiene, and isolated
  default-wheel checks are recorded in the verifier artifact.

## Review misses and future guards

- Provider startup code must be read end to end. A public `start()` method can
  initialize support containers before the requested resource and invalidate a
  wrapper-level timeout claim.
- Test package names can collide across a multi-distribution workspace. Use a
  unique nested test package instead of several top-level `tests` packages.
- Dynamic connection URLs must format IPv6 authorities with brackets.
- Validate non-empty tags and digests, not merely the presence of `:` or
  `@sha256:`.
- Keep the container configuration contract test synchronized with provider
  upgrades, especially private attributes used by the bounded start path.
- Keep README examples directly executable and document explicit pytest fixture
  ownership; no automatic plugin should silently choose resource scope.
