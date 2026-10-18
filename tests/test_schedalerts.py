"""Tests for the ``schedalerts`` demo of PyScheduler's alerts.

A job that always fails raises a ``failed`` alert, which is routed to a
``log`` notifier and delivered.
"""

import time

import pytest

from pystack.plugins import _schedalerts
from pystack.plugins.sched_plugin import RUN_DATE, PySchedulerPlugin

SCHEDALERTS_MAX_SECONDS = 5.0
RUN_ID = f"{_schedalerts.FAILING_JOB}.{RUN_DATE}.1"


def _run_demo() -> str:
    """Run the schedalerts command and return its output."""
    cmds = {c.name: c.handler for c in PySchedulerPlugin().shell_commands()}
    return cmds["schedalerts"]([])


class TestSchedalertsCommand:
    """Verify the alert story: a failure, its alert, and the delivery."""

    def test_schedalerts_story(self) -> None:
        """The failed run raises one alert, delivered to the log notifier."""
        started = time.monotonic()
        output = _run_demo()
        elapsed = time.monotonic() - started
        assert f"Triggered {RUN_ID}" in output
        assert f"Alert {RUN_ID}:failed:1:" in output
        assert "kind: failed  criticality: high" in output
        assert "delivered to team-log: sent (attempt 1)" in output
        assert f"failed alert for {RUN_ID}" in output
        assert "Traceback" not in output
        assert elapsed < SCHEDALERTS_MAX_SECONDS

    def test_listed_with_sched(self) -> None:
        """The plugin offers both scheduler demos."""
        names = [c.name for c in PySchedulerPlugin().shell_commands()]
        assert names == ["sched", "schedalerts"]


class TestSchedalertsFailures:
    """Verify the demo gives up instead of hanging."""

    def test_no_delivery_times_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no route, nothing is delivered and waiting ends with TimeoutError."""
        monkeypatch.setattr(_schedalerts, "DONE_SECONDS", 0.5)
        unrouted = _schedalerts.CONFIG.replace(
            '  - {match: "alert.#", notify: [team-log]}\n', ""
        ).replace("routes:\n", "")
        monkeypatch.setattr(_schedalerts, "CONFIG", unrouted)
        with pytest.raises(TimeoutError, match="no alert was delivered"):
            _schedalerts.schedalerts_cmd([])
