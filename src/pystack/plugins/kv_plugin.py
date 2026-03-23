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

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pykv.store import BasicStore

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_store: BasicStore | None = None


def _get_store() -> BasicStore:
    """Return the shared BasicStore instance, creating it if needed."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = BasicStore()
    return _store


@pebble_handler
def _kv_set(args: list[PebbleValue]) -> PebbleValue:
    """Store a value under a key."""
    key = str(args[0])
    value = str(args[1])
    _get_store().set(key, value)
    return "ok"


@pebble_handler
def _kv_get(args: list[PebbleValue]) -> PebbleValue:
    """Retrieve a value by key, or 'not found' if missing."""
    key = str(args[0])
    store = _get_store()
    try:
        return str(store.get(key))
    except Exception:  # noqa: BLE001
        return "not found"


@pebble_handler
def _kv_delete(args: list[PebbleValue]) -> PebbleValue:
    """Delete a key from the store."""
    key = str(args[0])
    store = _get_store()
    try:
        store.delete(key)
    except Exception:  # noqa: BLE001
        return f"error: key '{key}' not found"
    return "ok"


@pebble_handler
def _kv_keys(args: list[PebbleValue]) -> PebbleValue:  # noqa: ARG001
    """Return all keys in the store as a list."""
    store = _get_store()
    result: list[PebbleValue] = list(store.keys())
    return result


def reset_kv_state() -> None:
    """Reset all module-level state for testing."""
    global _store  # noqa: PLW0603
    _store = None


class KVPlugin(Plugin):
    """Integrate PyKV key-value store functions into PyStack.

    Register get/set/delete/keys functions in Pebble's ``kv`` stdlib
    module and shell commands for interactive use.
    """

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
                "kv_set": (2, _kv_set),
                "kv_get": (1, _kv_get),
                "kv_delete": (1, _kv_delete),
                "kv_keys": (0, _kv_keys),
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
            _get_store().set(key, value)
            return f"Set '{key}' = '{value}'"

        def _kv_get_cmd(args: list[str]) -> str:
            """Get a value by key."""
            if not args:
                return "Usage: kv-get <key>"
            try:
                return str(_get_store().get(args[0]))
            except Exception:  # noqa: BLE001
                return f"Key '{args[0]}' not found"

        def _kv_delete_cmd(args: list[str]) -> str:
            """Delete a key."""
            if not args:
                return "Usage: kv-delete <key>"
            try:
                _get_store().delete(args[0])
            except Exception:  # noqa: BLE001
                return f"Key '{args[0]}' not found"
            return f"Deleted '{args[0]}'"

        def _kv_keys_cmd(args: list[str]) -> str:  # noqa: ARG001
            """List all keys."""
            keys = list(_get_store().keys())
            return ", ".join(keys) if keys else "(no keys)"

        return [
            ShellCommand(name="kv-set", handler=_kv_set_cmd, help_text="Set a key-value pair"),
            ShellCommand(name="kv-get", handler=_kv_get_cmd, help_text="Get value by key"),
            ShellCommand(
                name="kv-delete", handler=_kv_delete_cmd, help_text="Delete a key"
            ),
            ShellCommand(name="kv-keys", handler=_kv_keys_cmd, help_text="List all keys"),
        ]
