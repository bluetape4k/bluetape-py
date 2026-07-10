# Issue #10 Serialization Strategy Review

## Scope

Review the durable Python serialization decision, source attribution, and
follow-up issues #45 and #46.

## Evidence

- Official Python `json` and `pickle` documentation.
- Primary project documentation for orjson, msgpack-python, Pydantic, cbor2,
  and Apache Fory.
- Local `bluetape-go`, `bluetape-rs`, and `bluetape4k` serialization contracts.
- `git diff --check`, source-link inspection, and live GitHub issue metadata.

## Review Result

| Tier | Focus | P0 | P1 | Result |
| --- | --- | ---: | ---: | --- |
| Architecture | package split and semantic interoperability | 0 | 0 | #45 owns core contracts; #46 is a blocked explicit Fory extra with schema/type-id conformance. |
| Security | untrusted decoding and unsafe formats | 0 | 0 | Repaired before approval: finite byte/depth limits, UTF-8 boundary, structural depth preflight, no pickle fallback, and Fory trusted-only initial decode. |
| Performance | bounded parse and adapter selection | 0 | 0 | JSON and MessagePack limits are explicit; no auto-detection or retry registry is proposed. |
| Stability | typed failures and version behavior | 0 | 0 | Metadata/version/trust/limit/malformed cases are explicit typed errors; no silent `None` or fallback path. |
| Operator | packaging and external source claims | 0 | 0 | The meta default remains core-only; extras and source links are explicit. |
| Developer | implementable acceptance criteria | 0 | 0 | #45 specifies UTF-8/depth tests; #46 specifies the cross-language fixture and safety gate. |
| User | documented scope and next actions | 0 | 0 | The research index, WIP, and linked follow-up issues expose the chosen path. |

## Outcome

`P0=0`, `P1=0`. The research is ready for documentation PR validation. Future
Fory work remains blocked on #45 and its own conformance/security gates.
