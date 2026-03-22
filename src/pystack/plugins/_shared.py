"""Shared helpers used by multiple plugins.

Some Pebble handler functions appear in more than one plugin -- for
example, both the web and net plugins need URL parsing. Instead of
copying the code (which is like writing the same homework answer
twice!), we put shared handlers here so every plugin can reuse them.
"""

from pebble.builtins import Value as PebbleValue
from pynet.url import parse_url

from pystack.plugins.base import pebble_handler


@pebble_handler
def url_parse(args: list[PebbleValue]) -> PebbleValue:
    """Parse a URL string into a dict with scheme, host, port, and path."""
    url_string = str(args[0])
    parsed = parse_url(url_string)
    result: dict[str, PebbleValue] = {
        "scheme": parsed.scheme,
        "host": parsed.host,
        "port": parsed.port,
        "path": parsed.path,
    }
    return result
