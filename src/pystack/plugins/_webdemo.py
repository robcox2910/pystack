"""The ``webdemo`` tour of PyWeb's async server.

A restaurant with a doorman: anyone may read the menu in the window, but
to get a table you show your wristband -- and the doorman hands one out
when you give the right name and password.

The demo starts a real server on a free port, then visits it with a tiny
hand-written HTTP client so every step can be seen.
"""

from collections.abc import AsyncIterator

from pynet.loop import run
from pynet.streams import StreamReader, open_connection
from pyweb.app import App
from pyweb.aserver import AsyncServer
from pyweb.auth import InMemoryUsers, SessionAuth, authenticate, current_user, require
from pyweb.messages import HttpRequest, HttpResponse, html, json
from pyweb.security import LoginThrottle, SessionSigner
from pyweb.sse import EventStream, ServerEvent

LOOPBACK = "127.0.0.1"
ROUNDS = 1_000  # fast for a demo; the real default is 100 000
TICKS = 3
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
_SHOWN = ("HttpOnly", "SameSite=Lax")
DEMO_NAME = "ada"
DEMO_PASSWORD = "demo-password-not-real"  # noqa: S105 - obviously fake
DEMO_SECRET = "demo-secret-not-real-0123456789abcdef"  # noqa: S105 - obviously fake


users = InMemoryUsers()
users.add(DEMO_NAME, DEMO_PASSWORD, rounds=ROUNDS)
auth = SessionAuth(SessionSigner(DEMO_SECRET), users)
throttle = LoginThrottle()
app = App()
app.middleware(auth)


@app.get("/")
def home(_request: HttpRequest) -> HttpResponse:
    """Serve the public page."""
    return html("<h1>Welcome to the PyWeb demo</h1>")


@app.post("/login", blocking=True)
def login(request: HttpRequest) -> HttpResponse:
    """Hand out a session cookie for the right name and password."""
    form = request.form()
    user = authenticate(users, throttle, form.get("name") or "", form.get("password") or "")
    if user is None:
        return json({"error": "bad login"}, HTTP_UNAUTHORIZED)
    response = json({"hello": user.name})
    auth.login(response, user)
    return response


@app.get("/api/me")
@require()
def me(request: HttpRequest) -> dict[str, str]:
    """Say who is logged in."""
    user = current_user(request)
    return {"user": user.name if user else ""}


@app.get("/ticks")
def ticks(_request: HttpRequest) -> EventStream:
    """Broadcast three numbered events, then stop."""

    async def source() -> AsyncIterator[ServerEvent]:
        """Yield tick 1 to tick 3."""
        for number in range(1, TICKS + 1):
            yield ServerEvent(f"tick {number}")

    return EventStream(source())


async def _read_head(reader: StreamReader) -> tuple[int, dict[str, str]]:
    """Read the status line and headers; return the status and lower-cased headers."""
    head = (await reader.read_until(b"\r\n\r\n")).decode().split("\r\n")
    status = int(head[0].split()[1])
    headers: dict[str, str] = {}
    for line in head[1:]:
        if ": " in line:
            name, value = line.split(": ", 1)
            headers[name.lower()] = value
    return status, headers


async def _send(
    port: int, request_line: str, extra_headers: str = "", body: str = ""
) -> tuple[StreamReader, int, dict[str, str]]:
    """Send one raw HTTP request and return the reader positioned at the body."""
    reader, writer = await open_connection(LOOPBACK, port)
    head = f"{request_line}\r\nHost: demo\r\nConnection: close\r\n{extra_headers}\r\n"
    writer.write((head + body).encode())
    await writer.drain()
    status, headers = await _read_head(reader)
    return reader, status, headers


async def _get(port: int, path: str, cookie: str | None = None) -> tuple[int, str]:
    """GET a path (with an optional cookie) and return the status and body text."""
    extra = f"Cookie: {cookie}\r\n" if cookie else ""
    reader, status, headers = await _send(port, f"GET {path} HTTP/1.1", extra)
    length = int(headers.get("content-length", "0"))
    body = await reader.read_exactly(length) if length else b""
    return status, body.decode()


async def _login(port: int) -> tuple[int, str]:
    """POST the demo login form and return the status and the Set-Cookie header."""
    form = f"name={DEMO_NAME}&password={DEMO_PASSWORD}"
    extra = f"Content-Type: application/x-www-form-urlencoded\r\nContent-Length: {len(form)}\r\n"
    reader, status, headers = await _send(port, "POST /login HTTP/1.1", extra, form)
    await reader.read_exactly(int(headers.get("content-length", "0")))
    return status, headers.get("set-cookie", "")


async def _chunk(reader: StreamReader) -> str:
    """Read one chunk of a chunked reply and return its text."""
    size = int((await reader.read_until(b"\r\n"))[:-2], 16)
    return (await reader.read_exactly(size + 2))[:-2].decode()


async def _ticks(port: int) -> tuple[int, list[str]]:
    """Listen to the event stream and return the status and the three events."""
    reader, status, _headers = await _send(port, "GET /ticks HTTP/1.1")
    events = [(await _chunk(reader)).strip().removeprefix("data: ") for _ in range(TICKS)]
    return status, events


async def _tour() -> list[str]:
    """Start the server, visit every route and return the printed lines."""
    lines: list[str] = []
    async with AsyncServer(app, access_log=False) as server:
        port = server.port
        status, _ = await _get(port, "/")
        lines.append(f"GET /           -> {status} (public page)")
        status, _ = await _get(port, "/api/me")
        lines.append(f"GET /api/me     -> {status} (no wristband yet)")
        status, set_cookie = await _login(port)
        lines.append(f"POST /login     -> {status}")
        token, _, attributes = set_cookie.partition(";")
        name = token.partition("=")[0]
        flags = "; ".join(p.strip() for p in attributes.split(";") if p.strip() in _SHOWN)
        lines.append(f"Set-Cookie: {name}=… ({flags})")
        status, body = await _get(port, "/api/me", cookie=token)
        lines.append(f"GET /api/me     -> {status} {body} (wristband shown)")
        status, events = await _ticks(port)
        lines.append(f"GET /ticks      -> {status} (event stream)")
        lines.extend(f"event: {event}" for event in events)
    return lines


def webdemo() -> str:
    """Run the tour and return the story as text, or an error message."""
    try:
        return "\n".join(run(_tour()))
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"
