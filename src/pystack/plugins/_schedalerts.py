"""The ``schedalerts`` demo: a failing job, its alert, and where the alert went.

A smoke alarm is only useful if someone hears it. PyScheduler's alerts
work the same way: when a job fails, the scheduler writes the alert down
first (so it can never be forgotten), then hands it to each notifier the
routes pick. Here the only notifier is a ``log`` notifier, a notebook
next to the config that gets one line per alert.

The demo writes that config into a temporary folder, runs the scheduler
in-process on PyNet's event loop, triggers a job that always fails, waits
until the alert has been delivered, and prints the alert, its delivery
and the notebook line.
"""

import json
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

from pyscheduler.client import ApiClient

from pystack.plugins.sched_plugin import RUN_DATE, with_scheduler

FAILING_JOB = "nightly-report"
ALERT_LOG = "alerts.log"
DONE_SECONDS = 5.0
POLL = 0.02

CONFIG = """
notifiers:
  team-log: {type: log, path: alerts.log}
routes:
  - {match: "alert.#", notify: [team-log]}
jobs:
  nightly-report:
    command: exit 1
    schedule: manual
    criticality: high
"""


def write_config(folder: Path) -> Path:
    """Write the demo's ``pysched.yaml`` into ``folder`` and return its path."""
    header = (
        "scheduler:\n"
        "  name: pystack-alerts\n"
        f"  state_dir: {folder / 'state'}\n"
        f"  log_dir: {folder / 'logs'}\n"
        "  listen: 127.0.0.1:0\n"
    )
    path = folder / "pysched.yaml"
    path.write_text(header + textwrap.dedent(CONFIG).lstrip("\n"), encoding="utf-8")
    return path


def wait_for_sent_alert(client: ApiClient) -> dict[str, Any]:
    """Wait until the failing job's alert has a sent delivery, and return it.

    Raises:
        TimeoutError: If no alert was delivered within ``DONE_SECONDS``.

    """
    deadline = time.monotonic() + DONE_SECONDS
    while True:
        for alert in client.alerts(job=FAILING_JOB)["alerts"]:
            if any(d["status"] == "sent" for d in alert["deliveries"]):
                return alert
        if time.monotonic() > deadline:
            msg = f"no alert was delivered within {DONE_SECONDS:g} s"
            raise TimeoutError(msg)
        time.sleep(POLL)


def alert_story(client: ApiClient, log_path: Path) -> list[str]:
    """Trigger the failing job, wait for its alert and describe where it went."""
    run = client.trigger(FAILING_JOB, run_date=RUN_DATE)["run"]
    lines = [f"Triggered {run['run_id']}, a job that always fails."]
    alert = wait_for_sent_alert(client)
    lines.append("")
    lines.append(f"Alert {alert['alert_id']}:")
    lines.append(f"  kind: {alert['kind']}  criticality: {alert['criticality']}")
    lines.append(f"  message: {alert['message']}")
    lines.extend(
        f"  delivered to {d['notifier']}: {d['status']} (attempt {d['attempts']})"
        for d in alert["deliveries"]
    )
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    lines.append("")
    lines.append(f"The {ALERT_LOG} notebook now has {len(entries)} line(s); the newest says:")
    lines.append(f"  {entries[-1]['kind']} alert for {entries[-1]['run_id']}")
    return lines


def schedalerts_cmd(_args: list[str]) -> str:
    """Run the alert demo and return its story."""
    lines = ["Starting a scheduler with a log notifier and a route for every alert..."]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = Path(tmp)
        config = write_config(folder)
        lines.extend(with_scheduler(config, lambda client: alert_story(client, folder / ALERT_LOG)))
    return "\n".join(lines)
