"""Plugin base class and protocol for PyStack extensions.

A plugin is a component that can hook into PyStack's three layers:
the PyOS shell (commands), the Pebble VM (stdlib modules), and the
web UI (Flask routes). Each hook is optional -- implement only what
your plugin needs.

Think of plugins like expansion packs for a board game. The base
game (PyStack) works on its own, but each expansion adds new pieces.
"""

import functools
from collections.abc import Callable
from dataclasses import dataclass

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule

# Type alias for a Pebble handler function (takes args, returns a value).
type PebbleHandler = Callable[[list[PebbleValue]], PebbleValue]


def pebble_handler(fn: PebbleHandler) -> PebbleHandler:
    """Wrap a Pebble handler so exceptions become ``"error: ..."`` strings.

    Every Pebble stdlib function needs to catch errors and return a
    friendly message instead of crashing the VM.  This decorator does
    that automatically -- like a safety net under a trapeze artist.

    Usage::

        @pebble_handler
        def _my_func(args: list[PebbleValue]) -> PebbleValue:
            return do_something(args[0])

    If ``do_something`` raises, the caller gets ``"error: <message>"``
    instead of an unhandled exception.
    """

    @functools.wraps(fn)
    def _wrapper(args: list[PebbleValue]) -> PebbleValue:
        try:
            return fn(args)
        except Exception as exc:  # noqa: BLE001
            return f"error: {exc}"

    return _wrapper


@dataclass
class ShellCommand:
    """A command to register in the PyOS shell.

    Args:
        name: The command name (e.g., "httpd").
        handler: A callable taking ``list[str]`` args and returning ``str``.
        help_text: One-line description for help output.

    """

    name: str
    handler: Callable[[list[str]], str]
    help_text: str = ""


@dataclass
class PluginInfo:
    """Metadata about a plugin.

    Args:
        name: Human-readable name (e.g., "PyWeb").
        description: One-line summary.
        version: Semantic version string.

    """

    name: str
    description: str = ""
    version: str = "0.1.0"


class Plugin:
    """Base class for PyStack plugins.

    Subclass this and override the hooks you need. The plugin registry
    calls each hook during boot to wire your plugin into the platform.

    """

    def info(self) -> PluginInfo:
        """Return metadata about this plugin.

        Returns:
            A PluginInfo with name, description, and version.

        """
        return PluginInfo(name=type(self).__name__)

    def shell_commands(self) -> list[ShellCommand]:
        """Return shell commands to register in PyOS.

        Returns:
            A list of ShellCommand objects (empty by default).

        """
        return []

    def pebble_stdlib(self) -> StdlibModule | None:
        """Return a Pebble stdlib module to register.

        Returns:
            A StdlibModule, or None if this plugin has no Pebble bindings.

        """
        return None

    def pebble_module_name(self) -> str:
        """Return the name for the Pebble stdlib module.

        Only called if ``pebble_stdlib()`` returns a module.

        Returns:
            The import name (e.g., "web" for ``import "web"``).

        """
        return self.info().name.lower()

    def on_boot(self) -> None:
        """Run custom initialization after the plugin is registered.

        Override this for setup that needs the full environment running.
        """
