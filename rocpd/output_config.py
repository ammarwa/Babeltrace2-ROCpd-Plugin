"""
Minimal output configuration
---------------------------

This module defines a very small substitute for the upstream
``rocpd.output_config`` class.  Its primary role is to hold the
``output_file`` and ``output_path`` attributes that determine where
converted traces are written.  Additional properties recognised by
conversion modules will simply be set as instance attributes.  The
helper functions ``add_args`` and ``process_args`` integrate with
``argparse`` to expose these options on the command line.

If you require the full behaviour of the official ROCpd output
configuration (including agent indexing options and advanced kernel
naming), please install the complete ROCpd SDK and use its Python API
instead.
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, Iterable, List, Tuple

__all__ = ["output_config", "add_args", "process_args", "add_generic_args", "process_generic_args"]


class output_config:
    """Simple container for output parameters.

    Parameters
    ----------
    output_file: str, optional
        Base name for output files.  Defaults to ``"out"``.
    output_path: str, optional
        Directory in which output files will be created.  Defaults to
        ``"./rocpd-output-data"``.
    **kwargs: dict
        Arbitrary additional attributes.  These will be set as
        attributes on the instance.
    """

    def __init__(self, output_file: str = None, output_path: str = None, **kwargs):
        # Use environment variables as fallbacks similar to upstream API
        self.output_file: str = output_file or os.environ.get("ROCPD_OUTPUT_NAME", "out")
        self.output_path: str = output_path or os.environ.get("ROCPD_OUTPUT_PATH", "./rocpd-output-data")
        self.update(**kwargs)

    def update(self, **kwargs) -> "output_config":
        """Update attributes from keyword arguments and return self."""
        for key, value in kwargs.items():
            setattr(self, key, value)
        return self


def check_file_exists(filename: str) -> str:
    """Argparse helper that checks for the existence of a file."""
    if not os.path.exists(filename):
        raise argparse.ArgumentTypeError(f"File '{filename}' does not exist.")
    return filename


def add_args(parser: argparse.ArgumentParser) -> List[str]:
    """Register common output options on a parser.

    Returns a list of option names corresponding to the values set on
    the resulting namespace.
    """
    group = parser.add_argument_group("I/O options")
    group.add_argument(
        "-o",
        "--output-file",
        help="Base output file name (default: 'out')",
        default=None,
        type=str,
    )
    group.add_argument(
        "-d",
        "--output-path",
        help="Directory to store output files (default: ./rocpd-output-data)",
        default=None,
        type=str,
    )
    return ["output_file", "output_path"]


def process_args(args: argparse.Namespace, valid_args: Iterable[str]) -> Dict[str, object]:
    """Extract recognised output configuration values from argparse namespace."""
    ret = {}
    for name in valid_args:
        if hasattr(args, name):
            value = getattr(args, name)
            if value is not None:
                ret[name] = value
    return ret


def add_generic_args(parser: argparse.ArgumentParser) -> List[str]:
    """In the full ROCpd implementation this adds agent indexing options.

    This minimal version exposes a single ``--agent-index-value`` option
    purely for compatibility with scripts that may expect it.  The
    resulting value is stored and ignored by the CTF emitter.
    """
    group = parser.add_argument_group("Generic options")
    group.add_argument(
        "--agent-index-value",
        choices=("absolute", "relative", "type-relative"),
        help="Device identification format in other output formats (ignored by CTF)",
        default=None,
    )
    return ["agent_index_value"]


def process_generic_args(args: argparse.Namespace, valid_args: Iterable[str]) -> Dict[str, object]:
    ret = {}
    for name in valid_args:
        if hasattr(args, name):
            value = getattr(args, name)
            if value is not None:
                ret[name] = value
    return ret