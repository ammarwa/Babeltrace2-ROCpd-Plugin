#!/usr/bin/env python3
"""
Command line entry point for the minimal ROCpd converter.

Only the ``convert`` subcommand is provided.  The full upstream ROCpd
package also supports querying and summarising trace databases, but
those features depend on the native ``libpyrocpd`` library and
additional Python modules which are not included here.  This
implementation therefore focuses solely on format conversion.  Of the
available formats, only Common Trace Format (CTF) is functional in
this minimal build.  CSV, Perfetto and OTF2 outputs will emit a
message indicating that the feature is unavailable.

Example usage::

    # Convert two databases into a CTF trace
    python3 -m rocpd convert -i db0.db db1.db --output-format ctf \
        -o trace_name -d /tmp/output

See :mod:`rocpd.ctf` for details on CTF emission and additional
options.
"""

from __future__ import annotations

import argparse

from .importer import RocpdImportData
from . import csv_format as csv_mod
from . import pftrace as pftrace_mod
from . import otf2 as otf2_mod
from . import ctf as ctf_mod
from . import output_config
from . import time_window


def main(argv: list[str] | None = None, config: output_config.output_config | None = None) -> int:
    """Parse arguments and execute a conversion.

    Parameters
    ----------
    argv: list[str], optional
        Command line arguments.  If ``None`` (default) the arguments
        will be taken from ``sys.argv``.
    config: output_config.output_config, optional
        Existing configuration object.  Keyword arguments will
        override values stored in this configuration.

    Returns
    -------
    int
        Exit status (0 on success, non‑zero on failure).
    """
    parser = argparse.ArgumentParser(
        prog="rocpd",
        description="Aggregate and/or convert ROCm profiling data",
        allow_abbrev=False,
    )

    subparsers = parser.add_subparsers(dest="command")

    # Only conversion is supported in this minimal implementation
    converter = subparsers.add_parser(
        "convert",
        description="Convert rocPD data into another data format",
        allow_abbrev=False,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Required arguments for conversion
    conv_req = converter.add_argument_group("Required options")
    conv_req.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        help="Input path and filename to one or more database(s)",
    )
    conv_req.add_argument(
        "-f",
        "--output-format",
        help=(
            "For adding output format (supported formats: csv, pftrace, otf2, ctf)"
        ),
        nargs="+",
        default=None,
        choices=("csv", "pftrace", "otf2", "ctf"),
        required=True,
    )

    # Output path/name arguments
    valid_out_cfg_args = output_config.add_args(converter)
    valid_generic_args = output_config.add_generic_args(converter)

    # Per‑format arguments
    valid_csv_args = csv_mod.add_args(converter)
    valid_pftrace_args = pftrace_mod.add_args(converter)
    valid_otf2_args = otf2_mod.add_args(converter)
    valid_ctf_args = ctf_mod.add_args(converter)

    # Time window arguments
    valid_time_window_args = time_window.add_args(converter)

    args = parser.parse_args(argv)

    if args.command != "convert":
        parser.print_help()
        return 1

    # Import the data.  The minimal RocpdImportData simply records filenames.
    importData = RocpdImportData(args.input)

    # Apply optional time window (no-op in minimal implementation)
    window_args = time_window.process_args(args, valid_time_window_args)
    if window_args:
        time_window.apply_time_window(importData, **window_args)

    # Process output configuration and per‑format options
    out_cfg_args = output_config.process_args(args, valid_out_cfg_args)
    generic_out_cfg_args = output_config.process_generic_args(args, valid_generic_args)
    csv_args = csv_mod.process_args(args, valid_csv_args)
    pftrace_args = pftrace_mod.process_args(args, valid_pftrace_args)
    otf2_args = otf2_mod.process_args(args, valid_otf2_args)
    ctf_args = ctf_mod.process_args(args, valid_ctf_args)

    # Merge args for configuration.  Each format may override output_file/path etc.
    config_kwargs = {**out_cfg_args, **generic_out_cfg_args}
    config_obj = (
        output_config.output_config(**config_kwargs)
        if config is None
        else config.update(**config_kwargs)
    )

    # Map format names to their writer functions and option dictionaries
    handlers = {
        "csv": (csv_mod.write_csv, csv_args),
        "pftrace": (pftrace_mod.write_pftrace, pftrace_args),
        "otf2": (otf2_mod.write_otf2, otf2_args),
        "ctf": (ctf_mod.write_ctf, ctf_args),
    }

    for fmt in args.output_format:
        if fmt not in handlers:
            print(f"Warning: Unsupported output format '{fmt}'")
            continue
        writer, fmt_args = handlers[fmt]
        print(f"Converting database(s) to {fmt} format...")
        # For CTF writer we pass through additional keyword arguments
        try:
            success = writer(importData, config_obj, **fmt_args)
        except TypeError:
            # Some writers expect no **fmt_args (stub functions ignore extra)
            success = writer(importData, config_obj)
        if not success:
            print(f"{fmt.upper()} conversion failed or is unavailable.")

    return 0


if __name__ == "__main__":
    main()