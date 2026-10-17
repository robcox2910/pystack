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

from pathlib import Path

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pycoldb.column import Column
from pycoldb.keyspace import Keyspace
from pycoldb.persistence import load_keyspace, save_keyspace

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method

_KEYSPACE_FILE = "keyspace.json"


class ColDBPlugin(Plugin):
    """Integrate PyColDB column-family store functions into PyStack.

    Register set/get/delete functions in Pebble's ``coldb`` stdlib
    module and shell commands for interactive use.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._keyspace: Keyspace | None = None

    def _get_keyspace(self) -> Keyspace:
        """Return this plugin's Keyspace, creating it on first use."""
        if self._keyspace is None:
            self._keyspace = Keyspace(name="default")
        return self._keyspace

    def _ensure_cf(self, name: str) -> None:
        """Ensure a column family exists, creating it if needed."""
        ks = self._get_keyspace()
        if name not in ks.column_families:
            ks.create_column_family(name)

    @pebble_method
    def col_set(self, args: list[PebbleValue]) -> PebbleValue:
        """Set a column value in a column family."""
        family = str(args[0])
        row_key = str(args[1])
        col_name = str(args[2])
        value = str(args[3])
        self._ensure_cf(family)
        ks = self._get_keyspace()
        ks.put(family, row_key, Column(name=col_name, value=value))
        return "ok"

    @pebble_method
    def col_get(self, args: list[PebbleValue]) -> PebbleValue:
        """Get a column value from a column family."""
        family = str(args[0])
        row_key = str(args[1])
        col_name = str(args[2])
        ks = self._get_keyspace()
        try:
            column = ks.get_column(family, row_key, col_name)
            return str(column.value)
        except Exception:  # noqa: BLE001
            return "not found"

    @pebble_method
    def col_delete(self, args: list[PebbleValue]) -> PebbleValue:
        """Delete a column from a column family."""
        family = str(args[0])
        row_key = str(args[1])
        col_name = str(args[2])
        ks = self._get_keyspace()
        try:
            cf = ks.get_column_family(family)
            cf.delete_column(row_key, col_name)
            return "ok"
        except Exception:  # noqa: BLE001
            return "not found"

    def load_state(self, folder: Path) -> None:
        """Load the saved keyspace, if there is one."""
        path = folder / _KEYSPACE_FILE
        if path.exists():
            self._keyspace = load_keyspace(path)

    def save_state(self, folder: Path) -> None:
        """Save the keyspace, if this run used or loaded one."""
        if self._keyspace is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        save_keyspace(self._keyspace, folder / _KEYSPACE_FILE)

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
                "col_set": (4, self.col_set),
                "col_get": (3, self.col_get),
                "col_delete": (3, self.col_delete),
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
                self._ensure_cf(family)
                self._get_keyspace().put(family, row_key, Column(name=col_name, value=value))
                return f"Set {family}/{row_key}/{col_name} = '{value}'"

            if sub == "get" and len(args) >= min_get_args:
                family = args[1]
                row_key = args[2]
                col_name = args[3]
                try:
                    column = self._get_keyspace().get_column(family, row_key, col_name)
                    return str(column.value)
                except Exception:  # noqa: BLE001
                    return "Not found"

            return "Usage: col <set|get> <family> <row> <col> [value]"

        return [
            ShellCommand(name="col", handler=_col_cmd, help_text="Column-family store operations"),
        ]
