"""
Minimal time window filtering
----------------------------

In the full ROCpd SDK the ``time_window`` module allows users to
select a sub‑range of the trace by specifying start and end values as
absolute nanoseconds or as percentages.  It constructs temporary views
of the underlying SQLite database(s) so that only events within the
specified interval are considered during conversion.

This simplified implementation does not inspect or modify any
databases.  It merely accepts the same command line arguments and
returns them untouched.  The :func:`apply_time_window` function is a
no‑op which exists for API compatibility.
"""

from __future__ import annotations

import argparse
from typing import Dict, Iterable, List


def add_args(parser: argparse.ArgumentParser) -> List[str]:
    """Register time window arguments on the given parser.

    In this minimal implementation the arguments are accepted but have
    no effect on the emitted trace.  They are included so that
    command lines written for the upstream ROCpd CLI continue to
    function.
    """
    group = parser.add_argument_group("Time window options")
    group.add_argument(
        "--start",
        help="Start time of the window (ns or percentage, ignored in minimal build)",
        default=None,
        type=str,
    )
    group.add_argument(
        "--end",
        help="End time of the window (ns or percentage, ignored in minimal build)",
        default=None,
        type=str,
    )
    return ["start", "end"]


def process_args(args: argparse.Namespace, valid_args: Iterable[str]) -> Dict[str, object]:
    """Return a dictionary of provided time window parameters."""
    ret = {}
    for name in valid_args:
        if hasattr(args, name):
            value = getattr(args, name)
            if value is not None:
                ret[name] = value
    return ret


def apply_time_window(importData, **kwargs) -> None:
    """No‑op function for applying a time window.

    In the upstream implementation this manipulates temporary tables in
    the SQLite connection to restrict events.  Here we simply ignore
    the parameters.
    """
    # Nothing to do in minimal build
    return None