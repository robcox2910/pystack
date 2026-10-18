"""PyScheduler integration plugin for PyStack.

PyScheduler is a job scheduler, like the timetable and the conductor of
an orchestra rolled into one: it knows which jobs play when, waits for
each one's cue (its dependencies), and gives a wobbly player one more go
(a retry).

Shell command ``sched`` runs a tiny nightly chain in a temporary folder.
It writes a config with three jobs in a row (``extract``, then
``transform``, then ``load``) plus a ``cleanup`` job that only runs if
``load`` fails. ``transform`` always fails its first attempt and passes
its retry, so you can watch a retry happen. The scheduler starts
in-process on PyNet's event loop with its HTTP API; we trigger the chain
for a fixed run date, wait for it, and print the board. Then we stop the
scheduler and start a brand-new one on the same state folder: the runs
are still there, because every change was written to its journalled
PyDB store first.

Shell command ``schedalerts`` (in ``_schedalerts.py``) runs a job that
always fails and follows its alert: written down first, routed to a
``log`` notifier, and delivered.

This plugin has no Pebble module.
"""

import tempfile
import textwrap
import time
from collections.abc import Callable
from pathlib import Path

from pynet.loop import Event, run, run_in_thread, sleep, spawn, timeout
from pyscheduler.client import ApiClient
from pyscheduler.service import serve

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand

RUN_DATE = "2026-10-19"
CHAIN = ("extract", "transform", "load")
CLEANUP = "cleanup"
READY_SECONDS = 5.0
DONE_SECONDS = 5.0
POLL = 0.02
FINAL_STATES = frozenset({"succeeded", "failed", "skipped", "cancelled"})

JOBS = """
jobs:
  extract:
    command: sleep 0.1
    schedule: manual
  transform:
    command: sh -c 'test "$PYSCHED_ATTEMPT" -gt 1'
    depends_on: [extract]
    retries: {count: 1, delay: 1s}
  load:
    command: sleep 0.1
    depends_on: [transform]
  cleanup:
    command: echo tidying up after a failed load
    depends_on:
      - {job: load, on: failure}
"""


def write_config(folder: Path) -> Path:
    """Write the demo's ``pysched.yaml`` into ``folder`` and return its path."""
    header = (
        "scheduler:\n"
        "  name: pystack-demo\n"
        f"  state_dir: {folder / 'state'}\n"
        f"  log_dir: {folder / 'logs'}\n"
        "  listen: 127.0.0.1:0\n"
    )
    path = folder / "pysched.yaml"
    path.write_text(header + textwrap.dedent(JOBS).lstrip("\n"), encoding="utf-8")
    return path


def with_scheduler[T](config: Path, body: Callable[[ApiClient], T]) -> T:
    """Run the scheduler for ``config`` on the loop, ``body(client)`` on a thread, then stop it."""

    async def main() -> T:
        """Start the scheduler, wait until it listens, run the body, then stop."""
        stop = Event()
        ports: list[int] = []
        task = spawn(serve(config, ready=ports.append, stop=stop), name="sched-demo")
        async with timeout(READY_SECONDS):
            while not ports and not task.done():
                await sleep(POLL)
        if task.done():
            task.result()  # raises whatever stopped the scheduler
            msg = "the scheduler stopped before it was ready"
            raise RuntimeError(msg)
        client = ApiClient(f"http://127.0.0.1:{ports[0]}", None)
        try:
            return await run_in_thread(lambda: body(client))
        finally:
            stop.set()
            await task

    return run(main())


def wait_for_chain(client: ApiClient) -> dict[str, dict[str, object]]:
    """Wait until every job's run for ``RUN_DATE`` has finished; return them by job.

    Raises:
        TimeoutError: If they have not all finished within ``DONE_SECONDS``.

    """
    deadline = time.monotonic() + DONE_SECONDS
    jobs = (*CHAIN, CLEANUP)
    while True:
        runs = {run["job"]: run for run in client.runs(run_date=RUN_DATE)["runs"]}
        if all(runs.get(job, {}).get("state") in FINAL_STATES for job in jobs):
            return runs
        if time.monotonic() > deadline:
            msg = f"the chain did not finish within {DONE_SECONDS:g} s"
            raise TimeoutError(msg)
        time.sleep(POLL)


def board_lines(runs: dict[str, dict[str, object]]) -> list[str]:
    """Return the board: one line per job with its state, attempts and duration."""
    lines = [f"  {'JOB':<10} {'STATE':<10} {'ATTEMPTS':<9} DURATION"]
    for job in (*CHAIN, CLEANUP):
        run = runs[job]
        seconds = run.get("duration_seconds")
        duration = "-" if not isinstance(seconds, float | int) else f"{seconds:.2f}s"
        lines.append(f"  {job:<10} {run['state']!s:<10} {run['attempt']!s:<9} {duration}")
    return lines


def first_start(client: ApiClient) -> list[str]:
    """Trigger the chain, wait for it and describe what happened."""
    run = client.trigger(CHAIN[0], run_date=RUN_DATE)["run"]
    lines = [f"Triggered {run['run_id']}; the rest of the chain follows on its own."]
    runs = wait_for_chain(client)
    lines.append("")
    lines.append(f"The board for {RUN_DATE}:")
    lines.extend(board_lines(runs))
    if runs[CLEANUP]["reason"]:
        lines.append(f"{CLEANUP} {runs[CLEANUP]['reason']}")
    return lines


def second_start(client: ApiClient) -> list[str]:
    """Look at the runs a brand-new scheduler finds in the old state folder."""
    runs = client.runs(run_date=RUN_DATE)["runs"]
    found = sorted(f"{run['job']} {run['state']}" for run in runs)
    survived = {run["job"] for run in runs} == {*CHAIN, CLEANUP}
    return [
        f"The new scheduler found {len(runs)} runs: {', '.join(found)}",
        "history survived the restart"
        if survived
        else "history was lost -- that should never happen!",
    ]


def _sched_cmd(_args: list[str]) -> str:
    """Run the demo chain, print its board, restart and show the history survived."""
    lines = ["Starting a scheduler on PyNet's event loop..."]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        config = write_config(Path(tmp))
        lines.extend(with_scheduler(config, first_start))
        lines.append("")
        lines.append("Stopping the scheduler and starting a new one on the same state folder...")
        lines.extend(with_scheduler(config, second_start))
    return "\n".join(lines)


def _schedalerts_cmd(args: list[str]) -> str:
    """Run the alert demo (imported lazily: it reuses this module's helpers)."""
    from pystack.plugins._schedalerts import schedalerts_cmd  # noqa: PLC0415

    return schedalerts_cmd(args)


class PySchedulerPlugin(Plugin):
    """Add PyScheduler's shell demo to PyStack (currently ``sched``)."""

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyScheduler",
            description="Run a job chain with a retry and watch its history survive a restart",
            version="0.1.0",
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the sched shell command."""
        return [
            ShellCommand(
                name="sched",
                handler=_sched_cmd,
                help_text="Run a small job chain on PyScheduler and restart it",
            ),
            ShellCommand(
                name="schedalerts",
                handler=_schedalerts_cmd,
                help_text="Fail a PyScheduler job and follow its alert to a log notifier",
            ),
        ]
