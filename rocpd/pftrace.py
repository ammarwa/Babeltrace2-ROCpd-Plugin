"""
Perfetto (pftrace) output stub
------------------------------

The upstream ROCpd SDK can produce Perfetto traces via the native
``libpyrocpd`` library.  This minimal implementation does not
include that functionality.  When invoked it simply informs the user
that the feature is unavailable and returns False.
"""

from __future__ import annotations

from typing import Iterable, List, Dict

def write_pftrace(importData, config=None, **kwargs):
    import sys
    sys.stderr.write(
        "Perfetto conversion is not implemented in this minimal ROCpd build.\n"
    )
    sys.stderr.flush()
    return False


def execute(input: Iterable[str], config=None, window_args: Dict[str, object] | None = None, **kwargs) -> None:
    write_pftrace(None, config)


def add_args(parser) -> List[str]:
    return []


def process_args(args, valid_args: Iterable[str]) -> Dict[str, object]:
    return {}
