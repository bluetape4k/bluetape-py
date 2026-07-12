# Issue #59 Compressor Contracts Spec Review

- Artifact: `docs/superpowers/specs/2026-07-12-issue-59-compressor-contracts-design.md`
- Artifact kind: spec
- Work type: Type A - Full Feature
- Review date: 2026-07-12
- Result: `P0=0 P1=0`

## Review execution

The workflow's six independent lenses were applied to the same spec and repository evidence.
The active collaboration surface cannot attach the OMX-required native `agent_type`, so spawning
untyped agents would violate the workspace routing rule. The main session therefore performed
the documented local-equivalent lanes separately and integrated them only after all six passes.

Provider behavior was also probed against the exact proposed versions in isolated `uv` runs:

- `cramjam==2.11.0` reports raw decompressed length and rejects tested trailing bytes.
- `lz4==4.4.5` exposes bounded frame decoding, `eof`, and `unused_data`.
- `zstandard==0.25.0` exposes bounded incremental decoding, `eof`, and `unused_data`.

These probes are design evidence, not a substitute for committed RED/GREEN contract tests.

## Initial findings and repairs

| Priority | Lens | Evidence | Required edit | Rerun lane |
|---|---|---|---|---|
| P1 | Stability | Native module allowed dependency failure at construction or first operation. | Make class-name imports provider-free but require provider validation at construction. | Stability |
| P1 | Security | Broad `Exception` translation did not account for `MemoryError` being an `Exception` subclass; `from None` alone does not guarantee an absent `__context__`. | Re-raise `MemoryError` first and raise translated errors outside the provider handler with no cause/context. | Security |
| P1 | Developer/API | Compression-level validation was delegated to an unspecified provider range. | Record exact stdlib/LZ4 ranges and a stable positive Zstd range for the pinned version. | Developer/API |
| P1 | Developer/API | Validation used `--extra native`, but the root meta distribution exposes `compression-native`. | Correct the full sync command to `--extra compression-native`. | Developer/API |
| P2 | Security | Payload-release wording implied that an active Python traceback never retains function arguments. | Scope the guarantee to library-owned attributes/context/state and test release after clearing the ordinary traceback. | Security |
| P2 | User/caller | Focused-extra smoke wording conflicted with provider-free import of all native class names. | Specify that names import safely, the selected class constructs, and an uninstalled class fails on construction. | User/caller |
| P2 | Stability | Snappy trailing-data rejection depended on provider behavior rather than an explicit maintained condition. | Add a pinned-provider contract test gate and reject upgrades that lose strictness without a parser. | Stability |

All required edits were applied to the reviewed spec. No finding was deferred or filed as a
follow-up.

## Lens reruns

### Performance

No P0/P1 finding. The spec forbids unbounded decompression materialization, defines exact-limit
and one-byte-over behavior, requires incremental native paths, and calls out the near-`sys.maxsize`
budget edge. Compression itself operates on caller-provided in-memory bytes and does not promise
an input-memory ceiling.

### Stability

No P0/P1 finding after repair. Instances are immutable and call-stateless; malformed, truncated,
trailing, concatenated, missing-provider, and incompatible-provider states have deterministic
outcomes. Construction now establishes provider availability before an instance is usable.

### Security

No P0/P1 finding after repair. Output bombs are bounded, format auto-detection is prohibited,
provider diagnostics and payload logging are excluded, fatal failures propagate, and translated
provider exceptions expose neither cause nor context. The traceback-retention guarantee now
matches Python runtime behavior.

### Operator/Ops

No P0/P1 finding. Provider pins, isolated base/focused/aggregate install checks, a dedicated native
CI path, compatibility fixtures for upgrades, additive rollout, and native-first rollback are
specified. There is no service lifecycle, shared state, retry, or runbook surface in this package.

### Developer/API

No P0/P1 finding after repair. `Protocol` enables structural typing without forced inheritance;
the six frozen/slotted implementations, stable algorithm identifiers, exact configuration
validation, module boundaries, extras, and validation commands are concrete and testable. Existing
function APIs and wire behavior remain intact.

### User/caller

No P0/P1 finding after repair. The spec explains install choices, import-versus-construction
behavior, empty-input semantics, error categories, migration from functions, metadata-preserving
serializer order, and the explicit non-goals of wire compatibility and auto-detection. English and
Korean documentation parity is part of acceptance.

## Main-session integration

- Boundaries: #59 owns compressor contracts and providers; #54 owns Redis envelopes and serializer
  composition implementation.
- Alternatives: functions-only and nominal ABC designs are evaluated against the chosen structural
  `Protocol`.
- Compatibility: existing stdlib functions, payloads, root namespace behavior, and default meta
  dependencies are preserved.
- Testability: every safety and packaging claim maps to a contract, isolation, or full-suite gate.
- Release readiness: lockfile, wheel metadata, isolated installs, CI, bilingual docs, changelog,
  review evidence, and PR DoD are included.
- Open decisions: none remain for the approved #59 scope.

Final integrated result: `P0=0 P1=0`.
