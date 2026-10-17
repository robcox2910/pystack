"""Pebble ↔ PyDB adapter.

Build a ``db`` module for Pebble so that Pebble programs can
query and modify a PyDB database using functions like ``db_query()``
and ``db_execute()``.

This is the bridge between a programming language and a database --
just like how Python programs talk to SQLite or PostgreSQL.
"""

from datetime import date

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pydb.database import Database
from pydb.executor import execute
from pydb.record import Value as PyDBValue
from pydb.sql_parser import parse_sql
from pydb.types import to_iso


def _pydb_to_pebble(value: PyDBValue) -> PebbleValue:
    """Convert a PyDB value to a Pebble value.

    Text, numbers and booleans pass straight through. Dates and timestamps
    become readable ISO text (``2026-10-17`` or ``2026-10-17T07:30:00Z``),
    because Pebble has no date type of its own.
    """
    return to_iso(value) if isinstance(value, date) else value


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


def make_db_module(database: Database) -> StdlibModule:
    """Build a ``db`` module wired to one particular database.

    Each environment keeps its own copy, so two environments never end up
    reading (or deleting) each other's tables.
    """
    return _make_db_query(database)
