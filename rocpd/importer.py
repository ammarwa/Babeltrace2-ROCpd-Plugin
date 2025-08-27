"""
Minimal Rocpd database importer
------------------------------

The upstream ROCpd SDK defines a complex :class:`RocpdImportData` class
which attaches one or more SQLite databases, builds temporary views and
exposes hundreds of SQL queries.  That implementation also requires the
native ``libpyrocpd`` library.  For the purposes of CTF conversion we
only need to remember which database filenames were provided by the
user.  This simplified :class:`RocpdImportData` records the list of
inputs and provides a dummy context manager so that it can be used with
``with`` statements.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Iterable, List


class RocpdImportData:
    """Lightweight stand‑in for the upstream RocpdImportData.

    Parameters
    ----------
    input: str or Iterable[str]
        One or more paths to SQLite databases produced by rocprofv3.

    Notes
    -----
    This implementation does **not** open or inspect the SQLite files.  It
    merely retains the filenames so that downstream conversion modules
    know where to read data from.  Attempting to pass a live
    ``sqlite3.Connection`` object will raise an error because this
    simplified importer cannot wrap existing connections.
    """

    def __init__(self, input: str | Iterable[str]):
        if isinstance(input, RocpdImportData):
            # Copy constructor: shallow clone filenames
            self._filenames = list(input._filenames)
        elif isinstance(input, sqlite3.Connection):
            raise ValueError(
                "RocpdImportData does not accept existing sqlite3 connections in this minimal build"
            )
        elif isinstance(input, str):
            self._filenames = [input]
        elif isinstance(input, Iterable):
            # Convert to list and ensure all elements are strings
            self._filenames = []
            for fn in input:
                if not isinstance(fn, str):
                    raise ValueError(
                        f"Input list must contain file names (str), found {type(fn).__name__}"
                    )
                self._filenames.append(fn)
        else:
            raise ValueError(
                f"Unsupported input type {type(input).__name__}; expected str or list of str"
            )

        # In the full implementation this would hold a sqlite3.Connection
        self.connection = None

    # Provide backwards compatibility alias used by rocpd.ctf.write_ctf
    @property
    def filenames(self) -> List[str]:
        """Return the list of underlying database filenames."""
        return list(self._filenames)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # No connection to close in this minimal implementation
        return False