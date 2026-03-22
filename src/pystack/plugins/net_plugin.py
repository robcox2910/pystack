"""PyNet integration plugin for PyStack.

Bridge PyNet's networking utilities into Pebble so kids can resolve
DNS names, parse URLs, and encode/decode Base64 from their Pebble
programs.

Pebble module name: ``net``

Example Pebble usage::

    import "net"
    let encoded = base64_encode("Hello, world!")
    print(encoded)

    let decoded = base64_decode(encoded)
    print(decoded)
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pynet.base64 import b64_decode, b64_encode
from pynet.dns import resolve

from pystack.plugins._shared import url_parse as _url_parse
from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler


@pebble_handler
def _dns_lookup(args: list[PebbleValue]) -> PebbleValue:
    """Resolve a hostname to an IPv4 address."""
    hostname = str(args[0])
    return resolve(hostname)


@pebble_handler
def _base64_encode(args: list[PebbleValue]) -> PebbleValue:
    """Encode a text string to Base64."""
    return b64_encode(str(args[0]))


@pebble_handler
def _base64_decode(args: list[PebbleValue]) -> PebbleValue:
    """Decode a Base64 string back to plain text."""
    return b64_decode(str(args[0]))


class NetPlugin(Plugin):
    """Integrate PyNet networking utilities into PyStack.

    Register DNS, URL parsing, and Base64 functions in Pebble's ``net``
    stdlib module, and a ``dns`` shell command.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyNet",
            description="DNS, URL parsing, and Base64 for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "net"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the net stdlib module with dns, url, and base64 functions."""
        return StdlibModule(
            functions={
                "dns_lookup": (1, _dns_lookup),
                "url_parse": (1, _url_parse),
                "base64_encode": (1, _base64_encode),
                "base64_decode": (1, _base64_decode),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the dns shell command."""

        def _dns_cmd(args: list[str]) -> str:
            """Resolve a hostname to an IP address."""
            if not args:
                return "Usage: dns <hostname>"
            try:
                return resolve(args[0])
            except Exception as exc:  # noqa: BLE001
                return f"error: {exc}"

        return [ShellCommand(name="dns", handler=_dns_cmd, help_text="Resolve hostname to IP")]
