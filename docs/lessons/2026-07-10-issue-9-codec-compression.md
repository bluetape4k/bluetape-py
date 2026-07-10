# Issue #9 Codec and Compression Boundaries

## Context

Issue #9 added focused codec and compression distributions while preserving the
thin default `bluetape` install.

## Decision

- Decode URL-safe Base64 only after strict ASCII/form validation and a
  canonical re-encode comparison.
- Treat `zlib.Decompress.flush(length)` as unsafe for a public output limit:
  its length is not a hard cap. Bound every `decompress(..., max_length)` call
  instead and fail on no-progress truncated input.
- Do not expose raw gzip/zlib backend messages or context because they can
  contain input bytes.
- Lazy-load optional stdlib `zlib` so the compression namespace remains
  importable on constrained Python builds.

## Outcome

Focused pytest coverage proves canonical codec rejection, gzip multi-member
limits, chunk-boundary/trailing handling, bounded expansion, and unavailable
backend behavior.

## Directive

Future streaming APIs need their own EOF, truncated-final-input, post-terminal,
and double-terminal-call contract; do not retrofit them into these byte helpers.
