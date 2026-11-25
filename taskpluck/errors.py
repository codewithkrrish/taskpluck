"""Errors for taskpluck.

One exception type for everything the user can fix: a missing file, a bad
date, an output file that already exists. The CLI catches it and prints a
plain message instead of a traceback.
"""

from __future__ import annotations


class TaskpluckError(Exception):
    """A user-facing error: bad input, bad flag, or a refused write."""
