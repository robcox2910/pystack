"""PyColDB integration plugin for PyStack.

Bridge PyColDB's column-family store into Pebble so kids can set, get,
and delete columns from their Pebble programs.

A column-family store is like a spreadsheet where every row can have
different column headers -- each row stores only the columns it needs.

Pebble module name: ``coldb``

Example Pebble usage::

    import "coldb"
    col_set("grades", "alice", "math", "A+")
    let grade = col_get("grades", "alice", "math")
    print(grade)
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pycoldb.column import Column
from pycoldb.keyspace import Keyspace

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_keyspace: Keyspace | None = None


def _get_keyspace() -> Keyspace:
    """Return the shared Keyspace instance, creating it if needed."""
    global _keyspace  # noqa: PLW0603
    if _keyspace is None:
        _keyspace = Keyspace(name="default")
    return _keyspace


def _ensure_cf(name: str) -> None:
    """Ensure a column family exists, creating it if needed."""
    ks = _get_keyspace()
    if name not in ks.column_families:
        ks.create_column_family(name)


@pebble_handler
def _col_set(args: list[PebbleValue]) -> PebbleValue:
    """Set a column value in a column family."""
    family = str(args[0])
    row_key = str(args[1])
    col_name = str(args[2])
    value = str(args[3])
    _ensure_cf(family)
    ks = _get_keyspace()
    ks.put(family, row_key, Column(name=col_name, value=value))
    return "ok"


@pebble_handler
def _col_get(args: list[PebbleValue]) -> PebbleValue:
    """Get a column value from a column family."""
    family = str(args[0])
    row_key = str(args[1])
    col_name = str(args[2])
    ks = _get_keyspace()
    try:
        column = ks.get_column(family, row_key, col_name)
        return str(column.value)
    except Exception:  # noqa: BLE001
        return "not found"


@pebble_handler
def _col_delete(args: list[PebbleValue]) -> PebbleValue:
    """Delete a column from a column family."""
    family = str(args[0])
    row_key = str(args[1])
    col_name = str(args[2])
    ks = _get_keyspace()
    try:
        cf = ks.get_column_family(family)
        cf.delete_column(row_key, col_name)
        return "ok"
    except Exception:  # noqa: BLE001
        return "not found"


def reset_coldb_state() -> None:
    """Reset all module-level state for testing."""
    global _keyspace  # noqa: PLW0603
    _keyspace = None


class ColDBPlugin(Plugin):
    """Integrate PyColDB column-family store functions into PyStack.

    Register set/get/delete functions in Pebble's ``coldb`` stdlib
    module and shell commands for interactive use.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyColDB",
            description="Column-family store for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "coldb"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the coldb stdlib module with set/get/delete functions."""
        return StdlibModule(
            functions={
                "col_set": (4, _col_set),
                "col_get": (3, _col_get),
                "col_delete": (3, _col_delete),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the col shell commands."""

        def _col_cmd(args: list[str]) -> str:
            """Handle col subcommands: set, get."""
            if not args:
                return "Usage: col <set|get> <family> <row> <col> [value]"

            sub = args[0]
            min_set_args = 5
            min_get_args = 4

            if sub == "set" and len(args) >= min_set_args:
                family = args[1]
                row_key = args[2]
                col_name = args[3]
                value = " ".join(args[4:])
                _ensure_cf(family)
                _get_keyspace().put(family, row_key, Column(name=col_name, value=value))
                return f"Set {family}/{row_key}/{col_name} = '{value}'"

            if sub == "get" and len(args) >= min_get_args:
                family = args[1]
                row_key = args[2]
                col_name = args[3]
                try:
                    column = _get_keyspace().get_column(family, row_key, col_name)
                    return str(column.value)
                except Exception:  # noqa: BLE001
                    return "Not found"

            return "Usage: col <set|get> <family> <row> <col> [value]"

        return [
            ShellCommand(
                name="col", handler=_col_cmd, help_text="Column-family store operations"
            ),
        ]
