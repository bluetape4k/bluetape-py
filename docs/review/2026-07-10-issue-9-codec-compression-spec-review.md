# Issue #9 Codec and Compression Spec Review

## Scope

Reviewed `docs/superpowers/specs/2026-07-10-issue-9-codec-compression-design.md`
for the `bluetape-codec` and `bluetape-compression` v1 contract before
implementation planning.

## Result

P0: 0

P1: 0

Verdict: PASS

## Evidence

| Review lane | Result | Coverage |
|---|---:|---|
| Performance | PASS | Bounded `decompress()` output, no `flush()`, no-progress termination, `Py_ssize_t` range |
| Stability | PASS | Chunk-boundary trailing data, member transitions, truncation, no partial result |
| Security | PASS | Canonical Base64url, decompression-bomb bound, payload-free error contract |
| Operator | PASS | Thin default install, lazy optional-zlib availability, rollback and wheel smoke checks |
| Developer | PASS | Public API feasibility, lazy backend contract, package layout, testability |
| User | PASS | Defaults, error expectations, wire formats, README and install clarity |

The initial adversarial review found an unsafe assumption: `zlib.Decompress.flush()`
does not impose a hard output bound. The contract now prohibits it and requires
only `max_length=remaining + 1` `decompress()` calls. It also specifies the
no-progress terminal state so malformed truncated input cannot loop forever,
rejects unread bytes after a zlib/raw-deflate terminal member, and shares one
remaining-output counter across every gzip member.

The specification now constrains `max_output_size` through `sys.maxsize - 1`
to keep `remaining + 1` valid for the C API. Compression errors have fixed,
payload-free messages with suppressed context, avoiding accidental payload
exposure through chained gzip/zlib errors. Because `zlib` is an optional Python
stdlib module, the package lazy-loads its backend: import remains available on
a zlib-free build and helper calls fail with the documented fixed
`CompressionError`.

## Non-blocking Notes

- v1 intentionally omits `max_input_size`: the byte input is already owned by
  the caller, and an input cap would not make a bytes-returning API a process
  memory ceiling. Streaming and file APIs remain separate work.
- Native optional backends and a compressor registry remain explicitly out of
  scope.
