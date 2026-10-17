"""PyNet integration plugin for PyStack.

Bridge PyNet's networking utilities into Pebble so kids can resolve
DNS names, parse URLs, and encode/decode Base64 from their Pebble
programs.

Networking is like the postal system of the internet -- it looks up
addresses, reads the envelope, and packs messages into a format that
travels safely.

Shell command ``overlap`` shows off PyNet's event loop: it starts several
``sleep`` programs at the same moment and times them. Think of putting
three kettles on the stove at once instead of waiting for each to boil
before starting the next -- the whole job takes as long as one kettle.

Shell command ``netecho`` sends a message to a tiny PyNet server and waits
for it to come back. Think of shouting into a canyon and timing how long
the echo takes to return.

Shell command ``wsecho`` sends a text message over a WebSocket to a tiny
PyNet server and prints the reply. Think of a walkie-talkie left switched
on: once the call is connected, either side can talk whenever it likes.

Pebble module name: ``net``

Example Pebble usage::

    import "net"
    let encoded = base64_encode("Hello, world!")
    print(encoded)

    let decoded = base64_decode(encoded)
    print(decoded)
"""

import time

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pynet.base64 import b64_decode, b64_encode
from pynet.dns import resolve
from pynet.loop import gather, run
from pynet.messaging import JsonValue, Message, Peer, connect, serve
from pynet.process import create_process
from pynet.ws import WebSocket, connect_websocket, serve_websocket

from pystack.plugins._shared import url_parse as _url_parse
from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

DEFAULT_OVERLAP = 3
DEFAULT_SECONDS = 1.0
MAX_OVERLAP = 20
MAX_SECONDS = 10.0
MAX_ARGS = 2
ECHO_USAGE = "Usage: netecho <text...>"
WS_ECHO_USAGE = "Usage: wsecho <text...>"
MS_PER_SECOND = 1000
LOOPBACK = "127.0.0.1"
OVERLAP_USAGE = f"Usage: overlap [n 1-{MAX_OVERLAP}] [seconds 0-{MAX_SECONDS:g}]"


async def _sleep_once(seconds: float) -> int:
    """Run one ``sleep`` subprocess and return its exit code."""
    proc = await create_process(["sleep", f"{seconds:g}"], stdout=False, stderr=False)
    return await proc.wait()


async def _sleep_many(count: int, seconds: float) -> None:
    """Run ``count`` sleeps concurrently and wait for all of them."""
    await gather(*(_sleep_once(seconds) for _ in range(count)))


def _overlap_cmd(args: list[str]) -> str:
    """Run n sleeps at once on PyNet's event loop and report the timing."""
    try:
        count = int(args[0]) if args else DEFAULT_OVERLAP
        seconds = float(args[1]) if len(args) > 1 else DEFAULT_SECONDS
    except ValueError:
        return OVERLAP_USAGE
    if len(args) > MAX_ARGS or not 1 <= count <= MAX_OVERLAP or not 0 <= seconds <= MAX_SECONDS:
        return OVERLAP_USAGE
    started = time.monotonic()
    try:
        run(_sleep_many(count, seconds))
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    elapsed = time.monotonic() - started
    return (
        f"ran {count} \u00d7 sleep {seconds:g} at once in {elapsed:.2f}s "
        f"(one after another would take {count * seconds:g}s)"
    )


async def _echo_handler(msg: Message) -> JsonValue:
    """Return the request body unchanged."""
    return msg.body


def _echo_setup(peer: Peer) -> None:
    """Register the ``echo`` handler on each accepted connection."""
    peer.on("echo", _echo_handler)


async def _echo_round_trip(text: str) -> tuple[str, float]:
    """Send ``text`` to a local echo server and return the reply and seconds taken."""
    server = await serve(LOOPBACK, 0, _echo_setup, heartbeat_interval=None)
    client: Peer | None = None
    try:
        client = await connect(LOOPBACK, server.port, heartbeat_interval=None)
        started = time.perf_counter()
        reply = await client.request("echo", text)
        elapsed = time.perf_counter() - started
        return str(reply.body), elapsed
    finally:
        if client is not None:
            await client.close()
        server.close()
        await server.wait_closed()


def _netecho_cmd(args: list[str]) -> str:
    """Round-trip a message through a local PyNet server and report the timing."""
    if not args:
        return ECHO_USAGE
    try:
        text, elapsed = run(_echo_round_trip(" ".join(args)))
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    return f"echo: {text} (round trip {elapsed * MS_PER_SECOND:.1f} ms)"


async def _ws_echo_handler(ws: WebSocket) -> None:
    """Send the first message received straight back, as text or bytes."""
    msg = await ws.recv()
    if isinstance(msg, str):
        await ws.send_text(msg)
    else:
        await ws.send_bytes(msg)


async def _ws_echo_round_trip(text: str) -> str:
    """Send ``text`` to a local WebSocket echo server and return the reply."""
    server = await serve_websocket(_ws_echo_handler, LOOPBACK, 0)
    try:
        client = await connect_websocket(LOOPBACK, server.port)
        try:
            await client.send_text(text)
            reply = await client.recv()
            return reply if isinstance(reply, str) else reply.decode(errors="replace")
        finally:
            await client.close()
    finally:
        server.close()
        await server.wait_closed()


def _wsecho_cmd(args: list[str]) -> str:
    """Round-trip a text message through a local PyNet WebSocket server."""
    if not args:
        return WS_ECHO_USAGE
    try:
        reply = run(_ws_echo_round_trip(" ".join(args)))
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
    return f"ws echo: {reply}"


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
    stdlib module, and ``dns``, ``overlap``, ``netecho``, and ``wsecho`` shell commands.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyNet",
            description="DNS, URL parsing, Base64, and a run-things-at-once event loop demo",
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
        """Return the dns, overlap, netecho, and wsecho shell commands."""

        def _dns_cmd(args: list[str]) -> str:
            """Resolve a hostname to an IP address."""
            if not args:
                return "Usage: dns <hostname>"
            try:
                return resolve(args[0])
            except Exception as exc:  # noqa: BLE001
                return f"error: {exc}"

        return [
            ShellCommand(name="dns", handler=_dns_cmd, help_text="Resolve hostname to IP"),
            ShellCommand(
                name="overlap",
                handler=_overlap_cmd,
                help_text="Run n sleeps at once on PyNet's event loop",
            ),
            ShellCommand(
                name="netecho",
                handler=_netecho_cmd,
                help_text="Echo text through a local PyNet message server",
            ),
            ShellCommand(
                name="wsecho",
                handler=_wsecho_cmd,
                help_text="Echo text through a local PyNet WebSocket server",
            ),
        ]
