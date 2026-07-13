"""Internal command-line interface for paired benchmark comparison."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ._comparison import compare_reports
from ._json import _comparison_to_dict, read_report, write_comparison


def parser() -> argparse.ArgumentParser:
    """Build the strict comparison argument parser."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--baseline", required=True)
    result.add_argument("--candidate", required=True)
    result.add_argument("--output", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Compare two reports and return stable process status."""
    arguments = parser().parse_args(argv)
    try:
        comparison = compare_reports(
            read_report(Path(arguments.baseline)), read_report(Path(arguments.candidate))
        )
        if arguments.output == "-":
            json.dump(_comparison_to_dict(comparison), sys.stdout, sort_keys=True, indent=2)
            sys.stdout.write("\n")
        else:
            write_comparison(Path(arguments.output), comparison)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return 2
    return 0 if comparison.comparable else 4


if __name__ == "__main__":
    raise SystemExit(main())
