#!/usr/bin/env python3

"""
ctf.py
~~~~~~~~

This module provides a simple wrapper for converting ROCpd SQLite databases to
the Common Trace Format (CTF).  The existing ROCpd Python API exposes
conversion routines for CSV, Perfetto and OTF2 via the native ``libpyrocpd``
library.  Unfortunately there is no equivalent native routine for emitting
CTF directly.  To bridge this gap this file integrates the high level
emitter provided by the open source project
`Babeltrace2‑ROCpd‑Plugin <https://github.com/ammarwa/Babeltrace2-ROCpd-Plugin>`_.

The emitter script (``barectf_emit.py``) included in this repository
implements a fast and feature complete conversion path.  It reads one or
more ROCpd SQLite databases using only the Python standard library and
emits a CTF trace using a small C bridge (``librocpd_barectf.so``).  The
bridge must be built ahead of time by invoking ``make`` in the
``barectf`` directory of the original plugin.  See the upstream project
for detailed build instructions.

At runtime ``write_ctf`` locates the input databases, constructs an
appropriate output directory based on the configured output path and base
file name, and then forwards the request to the embedded emitter.  Any
additional keyword arguments are passed through to the emitter via its
command line interface.  Note that time windowing is handled prior to
invoking the emitter – only events within the selected window are
collected from the database.

Due to the dependency on the external bridge this conversion routine is
provided on a best effort basis.  If the bridge is missing or the
``barectf_emit`` module cannot be imported the routine will emit a
helpful error message and return ``False``.
"""

from __future__ import annotations

import os
import sys
import pathlib
from typing import Iterable, List, Optional

from .importer import RocpdImportData
from .time_window import apply_time_window
from . import output_config


def _run_emitter(db_files: Iterable[str], out_dir: str, **kwargs) -> bool:
    """Internal helper to invoke the embedded barectf emitter.

    Parameters
    ----------
    db_files: Iterable[str]
        One or more paths to ROCpd SQLite database files.
    out_dir: str
        Directory into which the CTF metadata and stream files will be
        written.  The directory will be created if it does not exist.
    **kwargs:
        Additional keyword arguments accepted by the underlying emitter.
        These are mapped to command line options.  For example,
        ``packet_bytes=131072`` becomes ``--packet-bytes 131072``.  See
        ``barectf_emit.py`` for a full list of options.

    Returns
    -------
    bool
        ``True`` on success, ``False`` otherwise.
    """
    try:
        # Import lazily so that users not interested in CTF conversion don't
        # pay the cost of loading the emitter or fail if dependencies are
        # missing.
        from . import barectf_emit
    except Exception as exc:
        sys.stderr.write(
            "CTF conversion requested but the barectf emitter could not be "
            "imported. Make sure that 'barectf_emit.py' and the compiled "
            "bridge library 'librocpd_barectf.so' are present in the rocpd "
            "package.\n"
        )
        sys.stderr.write(f"Import error: {exc}\n")
        sys.stderr.flush()
        return False

    # Build argument list for the emitter.  The emitter expects one or
    # more ``--db`` options (comma separated lists are also accepted)
    # followed by ``--out`` to specify the output directory.  We also
    # support a subset of optional keyword arguments by converting them
    # from snake_case to the emitter's expected hyphenated form.
    argv: List[str] = []
    for db in db_files:
        argv.extend(["--db", db])
    argv.extend(["--out", out_dir])
    # Map additional keyword arguments to command line options
    for key, value in kwargs.items():
        # Convert snake_case to kebab-case (e.g. packet_bytes -> packet-bytes)
        opt = key.replace("_", "-")
        # Boolean flags are added without a value when True
        if isinstance(value, bool):
            if value:
                argv.append(f"--{opt}")
        else:
            argv.extend([f"--{opt}", str(value)])

    # Preserve the original sys.argv so we can restore it after invoking
    # the emitter's main function.  The emitter reads from sys.argv
    # directly when parsing its arguments.
    saved_argv = sys.argv[:]
    try:
        sys.argv = ["barectf_emit"] + argv
        barectf_emit.main()
        return True
    except SystemExit as exc:
        # Argparse calls sys.exit() on error which raises SystemExit.
        # Capture this and treat any non-zero code as failure.
        return exc.code == 0
    finally:
        sys.argv = saved_argv


def write_ctf(importData: RocpdImportData, config: Optional[output_config.output_config] = None, **kwargs) -> bool:
    """Write a Common Trace Format (CTF) trace from ROCpd data.

    Parameters
    ----------
    importData: RocpdImportData
        Instance encapsulating one or more ROCpd databases.  The
        ``filenames`` attribute is inspected to determine the original
        input files.  When multiple databases are provided a separate
        stream is created for each.
    config: output_config.output_config, optional
        Configuration object controlling the output destination.  If
        omitted a new configuration is constructed from any additional
        keyword arguments.
    **kwargs:
        Extra configuration options forwarded to ``output_config`` and
        then on to the emitter.  Unrecognised options are ignored by
        ``output_config`` but may be used by the emitter.  See
        ``barectf_emit.py`` for supported flags.

    Returns
    -------
    bool
        ``True`` if the conversion succeeded, ``False`` otherwise.
    """
    # Determine output configuration
    if config is None:
        cfg = output_config.output_config(**kwargs)
    else:
        cfg = config.update(**kwargs)
    # Determine base output path and file name.  The rocpd API uses
    # ``output_path`` and ``output_file`` to control where files are
    # written.  Mirror this behaviour here.
    base_path = getattr(cfg, "output_path", None) or os.getcwd()
    base_name = getattr(cfg, "output_file", None) or "out"
    # Compose output directory.  Use pathlib for clarity.
    out_dir = pathlib.Path(base_path) / base_name
    out_dir.mkdir(parents=True, exist_ok=True)
    # Gather database filenames.  If ``importData`` encapsulates
    # multiple databases it may create a temporary in-memory database
    # (``:memory:``).  The ``filenames`` attribute exposes the list of
    # original input files in this case.
    db_files: List[str] = []
    # The underlying rocprofiler API populates ``filenames`` on the
    # connection object.  Use this if available.  Otherwise assume
    # ``importData.connection`` is a direct SQLite connection to a
    # single database and use its associated filename.
    try:
        filenames_attr = getattr(importData, "filenames", None)
        if filenames_attr:
            db_files = list(filenames_attr)
    except Exception:
        pass
    if not db_files:
        # Fallback: use the input argument(s) from the RocpdImportData
        # constructor.  The connection property may expose a list of
        # attached filenames via the private ``_filenames`` attribute.
        try:
            db_files = list(getattr(importData, "_filenames", []))
        except Exception:
            pass
    # If still empty raise an error
    if not db_files:
        sys.stderr.write(
            "Could not determine input database filenames for CTF conversion.\n"
        )
        sys.stderr.flush()
        return False
    # Invoke the emitter.  Pass any remaining kwargs through (for
    # example ``packet_bytes`` or ``streaming``).  Unknown options
    # silently propagate to the emitter.
    return _run_emitter(db_files, os.fspath(out_dir), **kwargs)


def execute(input: Iterable[str], config: Optional[output_config.output_config] = None, window_args: Optional[dict] = None, **kwargs) -> None:
    """High level entry point mirroring the other output modules.

    Parameters
    ----------
    input: Iterable[str]
        One or more ROCpd SQLite database filenames.  These are passed
        through to ``RocpdImportData`` and ultimately determine the
        contents of the emitted trace.
    config: output_config.output_config, optional
        Pre‑existing configuration object.  Additional keyword
        arguments override values stored in the configuration.
    window_args: dict, optional
        Arguments specifying a time window.  Events outside this
        window are excluded.  Supported keys include ``start`` and
        ``end`` which may be specified as absolute nanosecond values
        or percentages (e.g. ``"30%"``).  See
        ``time_window.apply_time_window`` for details.
    **kwargs:
        Extra configuration options passed to the emitter.  See
        ``write_ctf`` for details.
    """
    # Create a RocpdImportData instance from the input database list.
    importData = RocpdImportData(input)
    # Apply a time window if requested.  Note that the emitter operates
    # directly on the databases so this effectively trims the tables
    # prior to emitting the events.
    if window_args:
        apply_time_window(importData, **window_args)
    # Determine configuration.  ``output_config.output_config`` stores
    # generic output options like ``output_path`` and ``output_file``.
    cfg = config if config is not None else output_config.output_config()
    # Execute the conversion.  Additional keyword arguments override
    # values on ``cfg`` and are forwarded to the emitter.
    write_ctf(importData, cfg, **kwargs)


def add_args(parser) -> List[str]:
    """Add CTF specific command line arguments.

    The CTF emitter currently mirrors the arguments accepted by the
    upstream barectf emitter.  Recognised options include ``packet_bytes``,
    ``stream_name``, ``debug``, ``no_sort``, ``split_on_decrease``,
    ``no_progress``, ``collect_threads``, ``streaming`` and
    ``fetch_chunk``.  See the upstream documentation for details.

    This function registers these options on an existing ``argparse``
    parser and returns a list of argument names so that the
    corresponding values can be extracted from the parsed arguments.
    """
    ctf_options = parser.add_argument_group("CTF options")
    ctf_options.add_argument(
        "--packet-bytes",
        dest="packet_bytes",
        type=int,
        help="Barectf packet size in bytes (default: 262144)",
        default=None,
    )
    ctf_options.add_argument(
        "--stream-name",
        dest="stream_name",
        type=str,
        help="Base name for CTF stream files (default: stream)",
        default=None,
    )
    ctf_options.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Print debug information from the emitter",
        default=False,
    )
    ctf_options.add_argument(
        "--no-sort",
        dest="no_sort",
        action="store_true",
        help="Do not globally sort events before emitting",
        default=False,
    )
    ctf_options.add_argument(
        "--split-on-decrease",
        dest="split_on_decrease",
        action="store_true",
        help="Start a new stream when timestamps decrease",
        default=False,
    )
    ctf_options.add_argument(
        "--no-progress",
        dest="no_progress",
        action="store_true",
        help="Disable progress bar output",
        default=False,
    )
    ctf_options.add_argument(
        "--collect-threads",
        dest="collect_threads",
        type=int,
        help="Number of threads to use when collecting events",
        default=None,
    )
    ctf_options.add_argument(
        "--streaming",
        dest="streaming",
        action="store_true",
        help="Low memory streaming mode (no full event list)",
        default=False,
    )
    ctf_options.add_argument(
        "--fetch-chunk",
        dest="fetch_chunk",
        type=int,
        help="Row batch size for streaming mode fetchmany()",
        default=None,
    )
    return [
        "packet_bytes",
        "stream_name",
        "debug",
        "no_sort",
        "split_on_decrease",
        "no_progress",
        "collect_threads",
        "streaming",
        "fetch_chunk",
    ]


def process_args(args, valid_args: Iterable[str]) -> dict:
    """Extract recognised CTF options from parsed arguments."""
    ret = {}
    for name in valid_args:
        if hasattr(args, name):
            val = getattr(args, name)
            if val is not None:
                ret[name] = val
    return ret


def main(argv: Optional[List[str]] = None) -> None:
    """Command line entry point for stand alone use.

    This function mirrors the behaviour of the ``otf2`` and ``csv``
    modules.  It parses arguments, constructs an output configuration and
    invokes ``execute``.
    """
    import argparse
    from .time_window import add_args as add_args_time_window
    from .time_window import process_args as process_args_time_window
    from .output_config import add_args as add_args_output_config
    from .output_config import process_args as process_args_output_config
    from .output_config import add_generic_args, process_generic_args

    parser = argparse.ArgumentParser(
        description="Convert ROCpd data to CTF format",
        allow_abbrev=False,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    required_params = parser.add_argument_group("Required arguments")
    required_params.add_argument(
        "-i",
        "--input",
        required=True,
        type=output_config.check_file_exists,
        nargs="+",
        help="Input path and filename to one or more database(s), separated by spaces",
    )
    # Register generic output arguments
    valid_out_config_args = add_args_output_config(parser)
    valid_generic_args = add_generic_args(parser)
    valid_ctf_args = add_args(parser)
    valid_time_window_args = add_args_time_window(parser)
    args_ns = parser.parse_args(argv)
    # Process argument namespaces into dictionaries
    out_cfg_args = process_args_output_config(args_ns, valid_out_config_args)
    generic_out_cfg_args = process_generic_args(args_ns, valid_generic_args)
    ctf_args = process_args(args_ns, valid_ctf_args)
    window_args = process_args_time_window(args_ns, valid_time_window_args)
    # Merge dictionaries
    all_args = {**out_cfg_args, **generic_out_cfg_args, **ctf_args}
    # Invoke conversion
    execute(args_ns.input, window_args=window_args, **all_args)


if __name__ == "__main__":
    main()