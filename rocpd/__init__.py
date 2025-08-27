"""
Minimal ROCpd Python interface with CTF support
------------------------------------------------

This package provides a very small subset of the original ROCpd Python API
found in the ROCm ``rocprofiler-sdk`` project.  The goal of this minimal
implementation is to support conversion of ROCprofiler v3 SQLite trace
databases into the Common Trace Format (CTF) without requiring the full
ROCpd C++ extension library.  It exposes a handful of convenience
functions analogous to those in the upstream package and delegates the
heavy lifting of CTF emission to :mod:`rocpd.ctf`.

The upstream ROCpd API also supports generating CSV, perfetto and OTF2
outputs via a native shared library called ``libpyrocpd``.  That library is
not shipped with this minimal reproduction, so the corresponding
conversion functions implemented here are stubs which simply inform the
user that the feature is unavailable.  Should you wish to enable those
formats you will need to build and install the full ROCpd SDK from source.

Example usage
-------------

To convert one or more SQLite databases to CTF you can invoke the
:func:`convert` entry point from the command line via the ``rocpd``
module:

.. code-block:: console

   python3 -m rocpd convert -i db0.db db1.db --output-format ctf

Alternatively you can call the high level API directly from Python:

.. code-block:: python

   from rocpd import connect, write_ctf
   db = connect(["db0.db", "db1.db"])
   write_ctf(db, output_file="trace", output_path="/tmp/ctf-output")

This will create a directory ``/tmp/ctf-output/trace`` containing
``metadata`` and ``stream`` files compliant with the Common Trace Format.

Note that this implementation delegates CTF generation to
``rocpd.barectf_emit``.  That module is a thin wrapper around the emitter
from the `Babeltrace2-ROCpd-Plugin` project and requires a separate
native bridge library called ``librocpd_barectf.so``.  See
``rocpd/barectf_emit.py`` for details.
"""

from .importer import RocpdImportData
# Import the output_config module rather than the class to avoid name collisions
from . import output_config as _output_config
from .ctf import write_ctf as _write_ctf

__all__ = [
    "connect",
    "write_csv",
    "write_pftrace",
    "write_otf2",
    "write_ctf",
    "RocpdImportData",
]

def connect(input, *args, **kwargs):
    """Create a :class:`RocpdImportData` instance from the given input.

    The ``input`` parameter may be a single filename (``str``) or a list of
    filenames.  In the latter case each database is considered part of
    the aggregate and events from them will be merged during CTF
    emission.
    """
    return RocpdImportData(input, *args, **kwargs)


def write_csv(importData, config=None, **kwargs):
    """Stub implementation of CSV conversion.

    The real ROCpd SDK uses a C extension to write CSV.  This
    minimal build does not include the native ``libpyrocpd`` library,
    so this function simply informs the caller and returns ``False``.
    """
    import sys
    sys.stderr.write(
        "CSV output is not available in this minimal ROCpd build. "
        "Please install the full rocprofiler-sdk to enable CSV conversion.\n"
    )
    sys.stderr.flush()
    return False


def write_pftrace(importData, config=None, **kwargs):
    """Stub implementation of Perfetto (pftrace) conversion.

    See the note in :func:`write_csv`.  Returns ``False``.
    """
    import sys
    sys.stderr.write(
        "Perfetto output is not available in this minimal ROCpd build. "
        "Please install the full rocprofiler-sdk to enable Perfetto conversion.\n"
    )
    sys.stderr.flush()
    return False


def write_otf2(importData, config=None, **kwargs):
    """Stub implementation of OTF2 conversion.

    See the note in :func:`write_csv`.  Returns ``False``.
    """
    import sys
    sys.stderr.write(
        "OTF2 output is not available in this minimal ROCpd build. "
        "Please install the full rocprofiler-sdk to enable OTF2 conversion.\n"
    )
    sys.stderr.flush()
    return False


def write_ctf(importData, config=None, **kwargs):
    """Write a Common Trace Format (CTF) trace from ROCpd data.

    This is a thin wrapper around :func:`rocpd.ctf.write_ctf` which
    constructs a default output configuration if necessary and forwards
    additional keyword arguments to the emitter.
    """
    cfg = (
        _output_config.output_config(**(kwargs or {}))
        if config is None
        else config.update(**kwargs)
    )
    return _write_ctf(importData, cfg, **kwargs)
