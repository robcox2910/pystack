"""The ``schedweb`` demo: PyScheduler's web UI over a few days of real runs.

A shop window is more fun with the shelves stocked. This command asks
PyScheduler's own demo to stock them: a folder with a dozen jobs (chains,
a file watcher, a flaky job and one that always fails critically), a user
``admin`` with password ``demo``, and three days of runs. Then it opens
the shop on a free loopback port and waits for Ctrl-C, so you can look at
the job board, the graph and the timeline in your browser.

``schedweb --seconds N`` stops by itself after ``N`` seconds (that is how
the tests use it). Once the UI is listening, a helper checks that the
login page answers, so the output says whether the shop really opened.
"""

import tempfile
import threading
import urllib.request
from pathlib import Path

from pyscheduler.demo import LOGIN_NAME, LOGIN_PASSWORD, seed_demo, serve_demo

CHECK_TIMEOUT = 5.0
USAGE = "usage: schedweb [--seconds N]"
FLAG_AND_VALUE = 2


def parse_seconds(args: list[str]) -> float | None:
    """Return the ``--seconds`` value from ``args``, or None to serve until Ctrl-C.

    Raises:
        ValueError: If the arguments are not ``--seconds <positive number>``.

    """
    if not args:
        return None
    if len(args) != FLAG_AND_VALUE or args[0] != "--seconds":
        raise ValueError(USAGE)
    seconds = float(args[1])
    if seconds <= 0:
        raise ValueError(USAGE)
    return seconds


def check_login(url: str, found: list[str]) -> None:
    """Fetch ``url``'s login page and note how it answered in ``found``."""
    try:
        with urllib.request.urlopen(f"{url}/login", timeout=CHECK_TIMEOUT) as response:
            found.append(f"The login page answered {response.status}.")
    except OSError as exc:
        found.append(f"The login page did not answer: {exc}")


def schedweb_cmd(args: list[str]) -> str:
    """Seed a demo folder, serve the web UI, and report where it was and how it went."""
    try:
        seconds = parse_seconds(args)
    except ValueError:
        return USAGE
    found: list[str] = []
    checks: list[threading.Thread] = []

    def ready(url: str) -> None:
        """Remember the address and check the login page from a helper thread."""
        found.append(f"The web UI was at {url} (log in as {LOGIN_NAME} / {LOGIN_PASSWORD}).")
        check = threading.Thread(target=check_login, args=(url, found), daemon=True)
        checks.append(check)
        check.start()

    lines = ["Stocking a PyScheduler demo with a dozen jobs and three days of runs..."]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp) / "demo"
        seed_demo(folder)
        lines.append("Opening the web UI. Press Ctrl-C to stop.")
        serve_demo(folder, seconds=seconds, ready=ready)
    for check in checks:
        check.join(CHECK_TIMEOUT)
    lines.extend(found)
    lines.append("The web UI has stopped.")
    return "\n".join(lines)
