"""Pebble ↔ PyDB adapter.

Register a ``db`` stdlib module in Pebble so that Pebble programs can
query and modify a PyDB database using functions like ``db_query()``
and ``db_execute()``.

This is the bridge between a programming language and a database --
just like how Python programs talk to SQLite or PostgreSQL.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import STDLIB_MODULES, StdlibModule
from pydb.database import Database
from pydb.executor import execute
from pydb.record import Value as PyDBValue
from pydb.sql_parser import parse_sql


def _pydb_to_pebble(value: PyDBValue) -> PebbleValue:
    """Convert a PyDB value to a Pebble value.

    PyDB values (str, int, float, bool) are a subset of Pebble values,
    so this is a direct pass-through.
    """
    return value


def _row_to_pebble_dict(row: dict[str, PyDBValue]) -> dict[str, PebbleValue]:
    """Convert a PyDB result row to a Pebble dict."""
    return {k: _pydb_to_pebble(v) for k, v in row.items()}


def _make_db_query(database: Database) -> StdlibModule:
    """Build the handler functions that wrap PyDB operations.

    Args:
        database: The PyDB database instance to query.

    Returns:
        A Pebble StdlibModule with db_query, db_execute, and db_tables.

    """

    def _db_query(args: list[PebbleValue]) -> PebbleValue:
        """Execute a SQL SELECT and return results as a list of dicts."""
        sql = str(args[0])
        parsed = parse_sql(sql)
        results = execute(parsed, database)
        return [_row_to_pebble_dict(row) for row in results]

    def _db_execute(args: list[PebbleValue]) -> PebbleValue:
        """Execute a SQL write statement and return a status message."""
        sql = str(args[0])
        parsed = parse_sql(sql)
        results = execute(parsed, database)
        if results and "result" in results[0]:
            return str(results[0]["result"])
        return f"{len(results)} rows returned"

    def _db_tables(_args: list[PebbleValue]) -> PebbleValue:
        """Return a list of all table names in the database."""
        names: list[PebbleValue] = list(database.table_names())
        return names

    return StdlibModule(
        functions={
            "db_query": (1, _db_query),
            "db_execute": (1, _db_execute),
            "db_tables": (0, _db_tables),
        },
        constants={},
    )


def register_db_module(database: Database) -> None:
    """Register the ``db`` stdlib module in Pebble's module registry.

    After calling this, Pebble programs can ``import "db"`` and use
    ``db_query()``, ``db_execute()``, and ``db_tables()``.

    Args:
        database: The PyDB database instance to make available.

    """
    STDLIB_MODULES["db"] = _make_db_query(database)


def unregister_db_module() -> None:
    """Remove the ``db`` stdlib module from Pebble's registry."""
    STDLIB_MODULES.pop("db", None)


def make_db_module(database: Database) -> StdlibModule:
    """Build a ``db`` module wired to one particular database.

    Each environment keeps its own copy, so two environments never end up
    reading (or deleting) each other's tables.
    """
    return _make_db_query(database)


# Pebble keeps one shared shelf of modules for the whole process. Only one
# environment may put its ``db`` on that shelf at a time.
_DB_SHELF_LOCK = threading.RLock()


@contextmanager
def bound_db_module(module: StdlibModule) -> Iterator[None]:
    """Put ``module`` on Pebble's shelf as ``db`` just while a program runs.

    Like borrowing the classroom's only microphone: you take it, speak, and
    hand back whatever was there before -- so whoever spoke last can't walk
    off with everyone else's microphone.
    """
    with _DB_SHELF_LOCK:
        previous = STDLIB_MODULES.get("db")
        STDLIB_MODULES["db"] = module
        try:
            yield
        finally:
            if previous is None:
                STDLIB_MODULES.pop("db", None)
            else:
                STDLIB_MODULES["db"] = previous
