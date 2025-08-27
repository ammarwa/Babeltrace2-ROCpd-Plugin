"""
CSV output stub
----------------

The real ROCpd SDK includes a native extension that can convert
ROCPD SQLite databases to CSV.  This stub exists to satisfy imports
from the command line interface and to provide informative feedback
when a user requests the ``csv`` output format.  No files will be
written.
"""

from __future__ import annotations

from typing import Iterable, List, Dict

def write_csv(importData, config=None, **kwargs):
    """Notify the user that CSV conversion is unavailable.

    Always returns False to indicate failure.
    """
    import sys
    sys.stderr.write(
        "CSV conversion is not implemented in this minimal ROCpd build.\n"
    )
    sys.stderr.flush()
    return False


def execute(input: Iterable[str], config=None, window_args: Dict[str, object] | None = None, **kwargs) -> None:
    """Execute CSV conversion.  In this stub it does nothing."""
    write_csv(None, config)


def add_args(parser) -> List[str]:
    """CSV has no additional command line options in this stub."""
    return []


def process_args(args, valid_args: Iterable[str]) -> Dict[str, object]:
    return {}
