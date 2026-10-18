"""PyKV integration plugin for PyStack.

Bridge PyKV's key-value store into Pebble so kids can store and retrieve
data by key, list all keys, and delete entries from their Pebble programs.

A key-value store is like a giant phonebook -- you look up a name (key)
and get back the phone number (value).

Pebble module name: ``kv``

Example Pebble usage::

    import "kv"
    kv_set("name", "Alice")
    let who = kv_get("name")
    print(who)
"""

from pathlib import Path

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pykv.persistence import load_store, save_store
from pykv.store import BasicStore

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method

_STORE_FILE = "store.json"


class KVPlugin(Plugin):
    """Integrate PyKV key-value store functions into PyStack.

    Register get/set/delete/keys functions in Pebble's ``kv`` stdlib
    module and shell commands for interactive use.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._store: BasicStore | None = None

    def _get_store(self) -> BasicStore:
        """Return this plugin's store, creating it on first use."""
        if self._store is None:
            self._store = BasicStore()
        return self._store

    @pebble_method
    def kv_set(self, args: list[PebbleValue]) -> PebbleValue:
        """Store a value under a key."""
        key = str(args[0])
        value = str(args[1])
        self._get_store().set(key, value)
        return "ok"

    @pebble_method
    def kv_get(self, args: list[PebbleValue]) -> PebbleValue:
        """Retrieve a value by key, or 'not found' if missing."""
        key = str(args[0])
        store = self._get_store()
        try:
            return str(store.get(key))
        except Exception:  # noqa: BLE001
            return "not found"

    @pebble_method
    def kv_delete(self, args: list[PebbleValue]) -> PebbleValue:
        """Delete a key from the store."""
        key = str(args[0])
        if not self._get_store().delete(key):
            return f"error: key '{key}' not found"
        return "ok"

    @pebble_method
    def kv_keys(self, args: list[PebbleValue]) -> PebbleValue:  # noqa: ARG002 -- Pebble passes args
        """Return all keys in the store as a list."""
        store = self._get_store()
        result: list[PebbleValue] = list(store.keys())
        return result

    def load_state(self, folder: Path) -> None:
        """Load the saved store, if there is one."""
        path = folder / _STORE_FILE
        if path.exists():
            self._store = load_store(path)

    def save_state(self, folder: Path) -> None:
        """Save the store, if this run used or loaded one."""
        if self._store is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        save_store(self._store, folder / _STORE_FILE)

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyKV",
            description="Key-value store for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "kv"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the kv stdlib module with get/set/delete/keys functions."""
        return StdlibModule(
            functions={
                "kv_set": (2, self.kv_set),
                "kv_get": (1, self.kv_get),
                "kv_delete": (1, self.kv_delete),
                "kv_keys": (0, self.kv_keys),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the kv shell commands."""

        def _kv_set_cmd(args: list[str]) -> str:
            """Set a key-value pair."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: kv-set <key> <value>"
            key, value = args[0], " ".join(args[1:])
            self._get_store().set(key, value)
            return f"Set '{key}' = '{value}'"

        def _kv_get_cmd(args: list[str]) -> str:
            """Get a value by key."""
            if not args:
                return "Usage: kv-get <key>"
            try:
                return str(self._get_store().get(args[0]))
            except Exception:  # noqa: BLE001
                return f"Key '{args[0]}' not found"

        def _kv_delete_cmd(args: list[str]) -> str:
            """Delete a key."""
            if not args:
                return "Usage: kv-delete <key>"
            if not self._get_store().delete(args[0]):
                return f"Key '{args[0]}' not found"
            return f"Deleted '{args[0]}'"

        def _kv_keys_cmd(args: list[str]) -> str:  # noqa: ARG001
            """List all keys."""
            keys = list(self._get_store().keys())
            return ", ".join(keys) if keys else "(no keys)"

        return [
            ShellCommand(name="kv-set", handler=_kv_set_cmd, help_text="Set a key-value pair"),
            ShellCommand(name="kv-get", handler=_kv_get_cmd, help_text="Get value by key"),
            ShellCommand(name="kv-delete", handler=_kv_delete_cmd, help_text="Delete a key"),
            ShellCommand(name="kv-keys", handler=_kv_keys_cmd, help_text="List all keys"),
        ]
