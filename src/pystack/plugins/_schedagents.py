"""The ``schedagents`` demo: a scheduler that hands jobs to helpers on other desks.

Imagine a head chef who does not cook every dish herself. She pins an
order to the board and a kitchen helper picks it up. Some orders say
"any helper will do"; others say "only the helper with the grill". That
is what PyScheduler's remote agents do: the scheduler holds the timetable,
and small agents (``build-01``, and ``gpu-01`` tagged ``gpu``) take the
jobs, run them, and report back.

PyScheduler's own demo does the work: it starts a scheduler, an embedded
message broker and both agents, runs one job pinned to ``build-01`` and
one job that needs the ``gpu`` tag, and prints which agent ran each. This
command runs it in a temporary folder on the main thread (the jobs are
child processes) and returns what it printed.
"""

import contextlib
import io
import tempfile
from pathlib import Path

from pyscheduler.demo_agents import run_agents_demo

AGENTS_SECONDS = 30.0


def schedagents_cmd(_args: list[str]) -> str:
    """Run the remote-agents demo and return which agent ran each job."""
    lines = ["Starting a scheduler, a broker and two agents (build-01 and gpu-01, tagged gpu)..."]
    out = io.StringIO()
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp,
        contextlib.redirect_stdout(out),
    ):
        run_agents_demo(Path(tmp), seconds=AGENTS_SECONDS)
    lines.extend(out.getvalue().splitlines())
    return "\n".join(lines)
