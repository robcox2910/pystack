"""Tests for the ``schedagents`` demo of PyScheduler's remote agents.

A pinned job must run on ``build-01`` and a job tagged ``gpu`` on ``gpu-01``.
"""

import time

import pytest
from pyscheduler import demo_agents

from pystack.plugins import _schedagents
from pystack.plugins.sched_plugin import PySchedulerPlugin

SCHEDAGENTS_MAX_SECONDS = 10.0


def _run_demo() -> str:
    """Run the schedagents command and return its output."""
    cmds = {c.name: c.handler for c in PySchedulerPlugin().shell_commands()}
    return cmds["schedagents"]([])


class TestSchedagentsCommand:
    """Verify each job ran on the agent it was meant for."""

    def test_jobs_ran_on_expected_agents(self) -> None:
        """The pinned job ran on build-01, the gpu-tagged job on gpu-01, quickly."""
        started = time.monotonic()
        output = _run_demo()
        elapsed = time.monotonic() - started
        assert f"{demo_agents.PINNED_JOB} ran on build-01" in output
        assert f"{demo_agents.TAGGED_JOB} ran on gpu-01" in output
        assert "Traceback" not in output
        assert elapsed < SCHEDAGENTS_MAX_SECONDS

    def test_listed_with_sched(self) -> None:
        """The plugin offers the agents demo."""
        names = [c.name for c in PySchedulerPlugin().shell_commands()]
        assert "schedagents" in names


class TestSchedagentsFailures:
    """Verify a failing demo surfaces its error."""

    def test_timeout_propagates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A time limit that is too short raises instead of hanging."""
        monkeypatch.setattr(_schedagents, "AGENTS_SECONDS", 0.01)
        with pytest.raises(TimeoutError):
            _schedagents.schedagents_cmd([])
