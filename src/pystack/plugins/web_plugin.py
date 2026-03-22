"""PyWeb integration plugin for PyStack.

Bridge HTTP client functionality into Pebble so kids can fetch web
pages and parse URLs from their Pebble programs. Since PyWeb is a
server framework, the HTTP client operations use PyNet's HTTP module.

Pebble module name: ``web``

Example Pebble usage::

    import "web"
    let parsed = url_parse("https://example.com:8080/hello?name=world")
    print(parsed["host"])
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pynet.http import get as http_get_impl

from pystack.plugins._shared import url_parse as _url_parse
from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler


@pebble_handler
def _http_get(args: list[PebbleValue]) -> PebbleValue:
    """Fetch the body of a URL via HTTP GET."""
    url = str(args[0])
    response = http_get_impl(url)
    return response.body


class WebPlugin(Plugin):
    """Integrate PyWeb and PyNet HTTP functions into PyStack.

    Register HTTP client and URL parsing functions in Pebble's ``web``
    stdlib module, and a ``curl`` shell command.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyWeb",
            description="HTTP client and URL parsing for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "web"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the web stdlib module with http_get and url_parse."""
        return StdlibModule(
            functions={
                "http_get": (1, _http_get),
                "url_parse": (1, _url_parse),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the curl shell command."""

        def _curl_cmd(args: list[str]) -> str:
            """Fetch a URL and print the response body."""
            if not args:
                return "Usage: curl <url>"
            url = args[0]
            try:
                response = http_get_impl(url)
            except Exception as exc:  # noqa: BLE001
                return f"error: {exc}"
            else:
                return response.body

        return [
            ShellCommand(
                name="curl",
                handler=_curl_cmd,
                help_text="Fetch a URL (educational, may fail without network)",
            ),
        ]
