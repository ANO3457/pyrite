"""Shared classification of SQLite storage failures, without service imports."""

import sqlite3

from ..exceptions import StorageBusyError, StorageError

#: SQLite's primary result codes for a transient lock: another connection
#: holds the database (SQLITE_BUSY) or a table (SQLITE_LOCKED).
_TRANSIENT_SQLITE_CODES = frozenset({sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED})

#: The same faults by message, for an error that lost ``sqlite_errorcode``
#: (constructed by a wrapper rather than raised by SQLite).
_TRANSIENT_SQLITE_MARKERS = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
    "database is busy",
)


def _is_transient(error: sqlite3.Error) -> bool:
    """Could the same call succeed if made again? Only for a lock (#431)."""
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        # Extended codes (SQLITE_BUSY_SNAPSHOT, ...) carry the primary code in
        # the low byte.
        return (code & 0xFF) in _TRANSIENT_SQLITE_CODES
    lowered = str(error).lower()
    return any(marker in lowered for marker in _TRANSIENT_SQLITE_MARKERS)


def storage_error_from(error: sqlite3.Error, what: str = "Search failed") -> StorageError:
    """The ``StorageError`` for a sqlite failure that is not the caller's query.

    A lock becomes ``StorageBusyError`` (retryable); schema drift, a missing
    table and corruption stay a plain ``StorageError`` (not retryable).
    """
    cls = StorageBusyError if _is_transient(error) else StorageError
    return cls(f"{what}: {error}")
