"""Internal command-line interface for paired benchmark comparison."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ._comparison import compare_reports
from ._json import _comparison_to_dict, read_report, write_comparison


class _ComparisonCliError(RuntimeError):
    def __init__(self, category: str, exit_code: int, phase: str) -> None:
        self.category = category
        self.exit_code = exit_code
        self.phase = phase


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise _ComparisonCliError("input-invalid", 2, "comparison")


def parser() -> argparse.ArgumentParser:
    """Build the strict comparison argument parser."""
    result = _SafeArgumentParser(description=__doc__)
    result.add_argument("--baseline", required=True)
    result.add_argument("--candidate", required=True)
    result.add_argument("--output", required=True)
    return result


def _diagnostic(error: _ComparisonCliError) -> str:
    value = {
        "case_id": None,
        "category": error.category,
        "code": "BTBENCH_" + error.category.upper().replace("-", "_"),
        "mode": None,
        "phase": error.phase,
        "repetition": None,
        "scenario_id": None,
    }
    return "bluetape-benchmark-error " + json.dumps(value, sort_keys=True, separators=(",", ":"))


def main(argv: Sequence[str] | None = None) -> int:
    """Compare two reports and return stable process status."""
    try:
        arguments = parser().parse_args(argv)
        comparison = compare_reports(
            read_report(Path(arguments.baseline)), read_report(Path(arguments.candidate))
        )
    except _ComparisonCliError as error:
        print(_diagnostic(error), file=sys.stderr)
        return error.exit_code
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        error = _ComparisonCliError("input-invalid", 2, "comparison")
        print(_diagnostic(error), file=sys.stderr)
        return error.exit_code
    except Exception:
        error = _ComparisonCliError("provider-failed", 3, "comparison")
        print(_diagnostic(error), file=sys.stderr)
        return error.exit_code
    try:
        if arguments.output == "-":
            json.dump(_comparison_to_dict(comparison), sys.stdout, sort_keys=True, indent=2)
            sys.stdout.write("\n")
        else:
            write_comparison(Path(arguments.output), comparison)
    except (OSError, TypeError, ValueError):
        error = _ComparisonCliError("artifact-write-failed", 6, "write")
        print(_diagnostic(error), file=sys.stderr)
        return error.exit_code
    if not comparison.comparable:
        error = _ComparisonCliError("not-comparable", 4, "comparison")
        print(_diagnostic(error), file=sys.stderr)
        return error.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
