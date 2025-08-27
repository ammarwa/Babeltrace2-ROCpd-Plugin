"""
OTF2 output stub
----------------

This module provides a stub for OTF2 conversion.  The real ROCpd SDK
relies on a C extension to produce OTF2 trace files.  In this
minimal build the function simply returns False and prints a
message indicating that the feature is unavailable.
"""

from __future__ import annotations

from typing import Iterable, List, Dict

def write_otf2(importData, config=None, **kwargs):
    import sys
    sys.stderr.write(
        "OTF2 conversion is not implemented in this minimal ROCpd build.\n"
    )
    sys.stderr.flush()
    return False


def execute(input: Iterable[str], config=None, window_args: Dict[str, object] | None = None, **kwargs) -> None:
    write_otf2(None, config)


def add_args(parser) -> List[str]:
    return []


def process_args(args, valid_args: Iterable[str]) -> Dict[str, object]:
    return {}
