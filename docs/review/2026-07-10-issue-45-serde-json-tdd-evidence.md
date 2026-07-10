# Issue 45 serde JSON TDD evidence

## Evidence status

The historical RED entries below are captured implementation-run summaries,
not verbatim terminal logs. The separate reconstruction only checks that the
recorded pre-production failure remains reproducible; it is not presented as
historical proof.

## Task 2 contracts

- RED command: `uv run pytest packages/bluetape-serde/tests/test_contracts.py -q`
- Captured RED result: nonzero collection failure before contract production
  implementation. The observed API failure was an import error for the missing
  `ContentTypeMismatchError` public contract.
- Current GREEN command:
  `uv run pytest packages/bluetape-serde/tests/test_contracts.py -q`
- Current GREEN result: exit 0, `144 passed`.

## Task 3 bounded JSON encoding

- RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'serialize or encode'`
- Captured initial RED result: exit 2 during collection because
  `DEFAULT_MAX_INPUT_SIZE` was not exported before production implementation.
- Captured executable RED rerun: exit 1, `55 failed, 2 deselected`; calls failed
  because the `json_serialize` API was still absent.
- Historical GREEN command for the Task 3 implementation and review closure
  (`d8b5a20`, `6cf73dc`):
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'serialize or encode'`
- Historical GREEN result at `6cf73dc`: exit 0, `63 passed, 2 deselected`.
- Current non-overlapping encode command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k '(json_serialize or encode) and not (json_deserialize or decode)'`
- Current non-overlapping encode result: exit 0, `97 passed, 121 deselected`.

## Task 4 strict bounded JSON decoding

- RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'deserialize or decode or depth'`
- Captured RED result: exit 2 during collection because the public
  `json_deserialize` API was absent before production implementation. Pytest
  reported one collection error with `ImportError: cannot import name
  'json_deserialize' from 'bluetape.serde'`.
- Historical pre-retention-fix GREEN selector at `38eacbb`:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'deserialize or decode or depth'`
- Historical selector result: exit 0, `92 passed, 56 deselected`, composed of
  83 decode cases plus 9 encode-depth cases.
- Traceback-retention RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'input_limit_traceback or nesting_limit_traceback'`
- Captured traceback-retention RED result: exit 1, `2 failed, 148 deselected`;
  INPUT_LIMIT retained payload/data and NESTING_LIMIT retained
  payload/data/text plus the scanner frame.
- Current traceback-retention GREEN result for the same command: exit 0,
  `2 passed, 216 deselected`.
- Current disjoint decode command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k '(json_deserialize or decode)'`
- Current disjoint decode result: exit 0, `119 passed, 99 deselected`.
- Current encode-depth-only command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'depth and not (json_deserialize or decode)'`
- Current encode-depth-only result: exit 0, `11 passed, 207 deselected`.
- Current aggregate Task 4 selector result: exit 0, `130 passed, 88 deselected`,
  composed of 119 decode cases plus 11 encode-depth cases.
- Review-gap fixture command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'large_valid_escaped_string'`
- Review-gap fixture result: exit 0, `1 passed, 149 deselected`; the prebuilt
  1 MiB valid JSON payload decoded at its exact byte limit with quoted
  structural characters and explicit odd/even backslash runs.
- Full serde regression command:
  `uv run pytest packages/bluetape-serde/tests -q`
- Current full serde result: exit 0, `362 passed`.

## Baseline reproducibility check

The Task 2 test tree from commit `4fa5243` was run with `PYTHONPATH` pointed at
its parent commit's placeholder serde source, using:

```text
PYTHONPATH=<parent-archive>/packages/bluetape-serde/src \
  .venv/bin/python -m pytest \
  <task2-archive>/packages/bluetape-serde/tests/test_contracts.py -q
```

Result: nonzero collection failure with the first missing public import
reported as `ContentTypeMismatchError`. This is a reconstruction, not a
verbatim record of the original RED run.

## Current regression gates

- `uv run pytest packages/bluetape-serde/tests -q`: exit 0, `362 passed`.
- `uv run ruff check packages/bluetape-serde`: exit 0.
- `uv run ruff format --check packages/bluetape-serde`: exit 0.
- `git diff --check`: exit 0.

## Step 6-R corrective TDD

- Traceback and high-chunk allocation RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'high_chunk_count or metadata_errors_do_not_retain or preflight_errors_do_not_retain or circular_error_does_not_retain or accepts_exact_output_limit or translates_encoder_failures'`
- RED result: exit 1, `15 failed, 146 deselected`. The 200,001-byte
  high-chunk output peaked at 12,503,354 traced bytes, and every reviewed
  metadata/preflight/output/translated traceback retained prohibited caller or
  derived locals.
- GREEN result for the same command after incremental `bytearray` assembly and
  fresh type/code error cloning: exit 0, `15 passed, 146 deselected`.
- Integer public-contract RED command:
  `uv run pytest packages/bluetape-serde/tests/test_contracts.py packages/bluetape-serde/tests/test_json.py -q -k 'public_contract or contract_enums or integer'`
- Initial RED result: exit 2 with two collection errors because
  `MAX_JSON_INTEGER_DIGITS` was not exported.
- After staging only the constant/code surface, the behavior RED result was
  exit 1, `13 failed, 18 passed, 298 deselected`: 641-digit encode reached the
  encoder, and decode either accepted the value or returned `INVALID_JSON`
  depending on CPython's global integer-string setting.
- GREEN result after arithmetic encode preflight and the bounded `parse_int`
  hook, including CPython limit settings 640/default/disabled for both paths:
  exit 0, `43 passed, 302 deselected`.
- Native configuration traceback RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'configuration_errors_do_not_retain_caller_sources'`
- RED result: exit 1, `11 failed, 201 deselected`. Exact-type and range
  validation failures retained encode/decode caller arguments in the public
  adapter frame.
- GREEN result for the same command after copying only exact native exception
  type/message and clearing caller arguments outside the handler: exit 0,
  `11 passed, 201 deselected`.
- Combined security/configuration selector: exit 0,
  `51 passed, 167 deselected`, including native fatal-exception identity
  preservation on both adapter paths.
- Full serde GREEN after complementary metadata traceback cases: exit 0,
  `362 passed`.
- Final exact performance selector: exit 0, `3 passed, 215 deselected` for
  preflight O(depth), high-chunk encode allocation, and decode scanner constant
  auxiliary-state tests.
- Final workspace GREEN: exit 0, `508 passed`.
- Final static/build gates: `uv lock --check`, locked all-package sync, Ruff
  check, Ruff format check, all-package build, branch/current diff checks,
  focused-wheel isolated roundtrip, 21-export/17-code assertion, four README
  wheel-snippet checks, and regex scan all exited 0.

## Post-PR shared-DAG correction

- RED selector:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'auxiliary_memory or shared_dag or output_visit_guard or greater_depth'`
- RED result against completed-container memoization: exit 1, `3 failed, 3
  passed, 231 deselected`; the private preflight lacked the output visit bound,
  the encoder was reached for a tiny shared-DAG budget, and the distinct-wide-
  sibling memory case could not exercise the approved contract.
- Intermediate GREEN design: active container IDs and iterator frames retain only the
  current path. A scalar counter raises `OUTPUT_LIMIT` once validated value
  occurrences exceed `max_output_size`; current-node unsupported, cycle, and
  depth validation runs before the guard.
- GREEN results: the exact selector passed `6 passed, 231 deselected`; the full
  serde suite passed `381 passed`; the full workspace passed `527 passed`.

## Post-PR shared-value scan correction

- RED selector:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'large_shared or string_lower_bound'`
- RED result against the one-byte occurrence guard: exit 1, `2 failed, 6
  passed, 237 deselected`; the same 1,024-scalar shared string was validated 12
  times and the same 4,096-character shared dict key was validated 8 times.
- GREEN design: accumulate a conservative encoded-byte lower bound. String
  validation returns two quotes plus UTF-8 scalar widths; dict iteration adds
  key lower bounds plus a colon lazily. Containers and other scalars retain a
  safe one-byte minimum, and current-node validation still precedes the guard.
- GREEN results: the exact selector passed `8 passed, 237 deselected`; the full
  serde suite passed `389 passed`; the full workspace passed `535 passed`.
