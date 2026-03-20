"""Plugin registry -- discover and activate plugins.

The registry loads plugins, calls their hooks, and wires them into
the PyStack environment. Plugins are registered manually via
``register()`` or discovered via Python entry points.
"""

import importlib.metadata

from pebble.stdlib import STDLIB_MODULES
from py_os.shell import Shell

from pystack.plugins.base import Plugin, PluginInfo

ENTRY_POINT_GROUP = "pystack.plugins"


class PluginRegistry:
    """Manage plugin lifecycle: registration, activation, and listing.

    Plugins register shell commands, Pebble stdlib modules, and can
    run custom boot logic.

    """

    __slots__ = ("_plugins",)

    def __init__(self) -> None:
        """Create an empty plugin registry."""
        self._plugins: list[Plugin] = []

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

    def activate_all(self, shell: Shell | None = None) -> None:
        """Activate all registered plugins.

        Registers shell commands, Pebble stdlib modules, and calls
        each plugin's ``on_boot()`` hook.

        Args:
            shell: The PyOS shell to register commands in (optional).

        """
        for plugin in self._plugins:
            # Register shell commands.
            if shell is not None:
                for cmd in plugin.shell_commands():
                    shell._commands[cmd.name] = cmd.handler  # noqa: SLF001

            # Register Pebble stdlib module.
            stdlib = plugin.pebble_stdlib()
            if stdlib is not None:
                module_name = plugin.pebble_module_name()
                STDLIB_MODULES[module_name] = stdlib

            # Run custom boot logic.
            plugin.on_boot()

    def list_plugins(self) -> list[PluginInfo]:
        """Return info for all registered plugins.

        Returns:
            A list of PluginInfo objects.

        """
        return [p.info() for p in self._plugins]
