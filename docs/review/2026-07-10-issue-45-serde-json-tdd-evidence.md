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
- Current GREEN result: exit 0, `140 passed`.

## Task 3 bounded JSON encoding

- RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'serialize or encode'`
- Captured initial RED result: exit 2 during collection because
  `DEFAULT_MAX_INPUT_SIZE` was not exported before production implementation.
- Captured executable RED rerun: exit 1, `55 failed, 2 deselected`; calls failed
  because the `json_serialize` API was still absent.
- Historical GREEN command for the Task 3 implementation and review closure
  (`47dea05`, `5577ad8`):
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'serialize or encode'`
- Historical GREEN result at `5577ad8`: exit 0, `63 passed, 2 deselected`.
- Current non-overlapping encode command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k '(json_serialize or encode) and not (json_deserialize or decode)'`
- Current non-overlapping encode result: exit 0, `63 passed, 85 deselected`.

## Task 4 strict bounded JSON decoding

- RED command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'deserialize or decode or depth'`
- Captured RED result: exit 2 during collection because the public
  `json_deserialize` API was absent before production implementation. Pytest
  reported one collection error with `ImportError: cannot import name
  'json_deserialize' from 'bluetape.serde'`.
- GREEN command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'deserialize or decode or depth'`
- Current GREEN result: exit 0, `92 passed, 56 deselected`.
- Review-gap fixture command:
  `uv run pytest packages/bluetape-serde/tests/test_json.py -q -k 'large_valid_escaped_string'`
- Review-gap fixture result: exit 0, `1 passed, 147 deselected`; the prebuilt
  1 MiB valid JSON payload decoded at its exact byte limit with quoted
  structural characters and explicit odd/even backslash runs.
- Full serde regression command:
  `uv run pytest packages/bluetape-serde/tests -q`
- Current full serde result: exit 0, `288 passed`.

## Baseline reproducibility check

The Task 2 test tree from commit `f71d637` was run with `PYTHONPATH` pointed at
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

- `uv run pytest packages/bluetape-serde/tests -q`: exit 0, `288 passed`.
- `uv run ruff check packages/bluetape-serde`: exit 0.
- `uv run ruff format --check packages/bluetape-serde`: exit 0.
- `git diff --check`: exit 0.
