"""Plugin registry -- discover and activate plugins.

The registry loads plugins, calls their hooks, and wires them into
the PyStack environment. Plugins are registered manually via
``register()`` or discovered via Python entry points.
"""

import importlib.metadata
from pathlib import Path

from pebble import StdlibModule
from py_os.shell import Shell

from pystack.plugins.base import Plugin, PluginInfo, shell_handler

ENTRY_POINT_GROUP = "pystack.plugins"


class PluginRegistry:
    """Manage plugin lifecycle: registration, activation, and listing.

    Plugins register shell commands, Pebble stdlib modules, and can
    run custom boot logic.

    """

    __slots__ = ("_pebble_modules", "_plugins")

    def __init__(self) -> None:
        """Create an empty plugin registry."""
        self._plugins: list[Plugin] = []
        self._pebble_modules: dict[str, StdlibModule] = {}

    @property
    def plugins(self) -> list[Plugin]:
        """Return all registered plugins."""
        return list(self._plugins)

    def register(self, plugin: Plugin) -> None:
        """Register a plugin manually.

        Args:
            plugin: The plugin instance to register.

        """
        self._plugins.append(plugin)

    def discover(self) -> int:
        """Discover and register plugins via Python entry points.

        Scans ``pystack.plugins`` entry point group. Each entry point
        should resolve to a Plugin subclass.

        Returns:
            The number of plugins discovered.

        """
        count = 0
        eps = importlib.metadata.entry_points()
        for ep in eps.select(group=ENTRY_POINT_GROUP):
            plugin_cls = ep.load()
            if isinstance(plugin_cls, type) and issubclass(plugin_cls, Plugin):
                self.register(plugin_cls())
                count += 1
        return count

    def activate_all(self, shell: Shell | None = None, data_dir: Path | None = None) -> None:
        """Activate all registered plugins.

        Registers shell commands and Pebble modules, then calls each
        plugin's ``load_state()`` (when there is a data folder) and
        ``on_boot()`` hooks.

        Args:
            shell: The PyOS shell to register commands in (optional).
            data_dir: The environment's data folder; each plugin loads from
                ``data_dir / plugin.pebble_module_name()``. ``None`` skips
                loading.

        """
        for plugin in self._plugins:
            # Register shell commands, each wrapped in a safety net so a bad
            # argument prints an error instead of crashing the shell.
            if shell is not None:
                for cmd in plugin.shell_commands():
                    shell._commands[cmd.name] = shell_handler(cmd.handler)  # noqa: SLF001

            # Collect the plugin's Pebble module. It's handed to Pebble with
            # each run (never written into Pebble's shared table), so two
            # environments can't see each other's modules.
            stdlib = plugin.pebble_stdlib()
            if stdlib is not None:
                self._pebble_modules[plugin.pebble_module_name()] = stdlib

            # Load saved data, then run custom boot logic.
            if data_dir is not None:
                plugin.load_state(data_dir / plugin.pebble_module_name())
            plugin.on_boot()

    def save_all(self, data_dir: Path) -> list[tuple[str, Exception]]:
        """Ask every plugin to save, carrying on past failures.

        Args:
            data_dir: The environment's data folder.

        Returns:
            ``(plugin module name, error)`` for each plugin that failed.

        """
        failures: list[tuple[str, Exception]] = []
        for plugin in self._plugins:
            name = plugin.pebble_module_name()
            try:
                plugin.save_state(data_dir / name)
            except Exception as exc:  # noqa: BLE001 -- reported by the caller
                failures.append((name, exc))
        return failures

    def shutdown_all(self) -> list[tuple[str, Exception]]:
        """Call every plugin's ``on_shutdown()``, carrying on past failures.

        Returns:
            ``(plugin module name, error)`` for each plugin that failed.

        """
        failures: list[tuple[str, Exception]] = []
        for plugin in self._plugins:
            try:
                plugin.on_shutdown()
            except Exception as exc:  # noqa: BLE001 -- reported by the caller
                failures.append((plugin.pebble_module_name(), exc))
        return failures

    def pebble_modules(self) -> dict[str, StdlibModule]:
        """Return the Pebble modules of every activated plugin, by import name.

        Returns:
            A new dict mapping each module name (e.g. ``"kv"``) to its module.

        """
        return dict(self._pebble_modules)

    def list_plugins(self) -> list[PluginInfo]:
        """Return info for all registered plugins.

        Returns:
            A list of PluginInfo objects.

        """
        return [p.info() for p in self._plugins]
