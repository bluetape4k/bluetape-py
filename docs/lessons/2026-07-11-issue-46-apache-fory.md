# Issue #46 Apache Fory Integration Lessons

Date: 2026-07-11

## Context

Issue #46 added a CPython 3.13-only Apache Fory adapter to the existing serde
contracts without widening the default install or allowing payload-selected
type/codec behavior.

## Decisions and Outcome

- Keep provider-independent error codes in `bluetape.serde`, but import
  `pyfory` only from the explicit `bluetape.serde.fory` module.
- Put a fixed 20-byte `BTFY` envelope around Fory bytes so metadata, schema,
  type, length, and root-header gates run before reconstruction.
- Treat `(schema_id, schema_version, type_id)` as application-owned route
  configuration. A schema change creates a new route; it never mutates the
  meaning of an existing tuple.
- Use varint mappings and explicit field IDs in every language. Removing the
  Python/Go/Rust/Kotlin annotations produced superficially similar types but
  weakened the cross-language identity contract.
- Translate provider encode/decode/registration failures at fresh public error
  boundaries. Preserve direct provider initialization failures where the API
  contract requires diagnosis, but never include payload or provider exception
  text in serde domain failures.
- Use the public Fory `Buffer` reader index to prove exact body consumption.
  Length equality alone cannot detect a decoder that stops before trailing
  bytes.
- Bound provider access with a semaphore in front of `ThreadSafeFory`; prove
  permit release and same-runtime reuse after ordinary failures with barriers
  and identity assertions rather than sleeps.

## Verification Evidence

- 339 focused contract, Fory, and packaging tests passed.
- 5 performance/allocation/RSS observations passed.
- 737 workspace tests passed on CPython 3.13.14.
- Python, Go, Rust, and Kotlin generated fresh deterministic fixtures and
  verified the Python artifact; Python verified every producer artifact.
- Ruff, all-package build, actionlint, manifest verification, and diff checks
  passed.

## Review Misses and Future Guards

- A focused feature suite can miss a stale shared export assertion. Always run
  the full workspace suite before Step 6-R.
- A prior `uv sync` is not an adequate CI contract. Every provider command must
  state the package, extra, and exact Python version itself.
- Examples in approved specs are part of the public contract. Compare them
  against the final callable signature during API review.
- Keep committed fixtures, canonical manifest metadata, runtime-generated
  artifacts, and downloaded executable verifiers as separate proofs. Do not
  replace artifact verification with recompilation in the final CI job.
