"""Tests for the ``sched`` demo of PyScheduler.

The demo runs a three-job chain plus an on-failure cleanup job, prints
the board, then restarts the scheduler on the same state folder.
"""

import time
from pathlib import Path

import pytest
from pyscheduler.client import ApiClient, JsonObject
from pyscheduler.config import ConfigError

from pystack.plugins import sched_plugin
from pystack.plugins.sched_plugin import PySchedulerPlugin

SCHED_MAX_SECONDS = 5.0
RETRIED_ATTEMPTS = "2"
FIRST_ATTEMPT = "1"


def _sched() -> str:
    """Run the sched command and return its output."""
    cmds = {c.name: c.handler for c in PySchedulerPlugin().shell_commands()}
    return cmds["sched"]([])


def _board(output: str) -> dict[str, list[str]]:
    """Return each job's board row, split into words, keyed by job name."""
    jobs = {*sched_plugin.CHAIN, sched_plugin.CLEANUP}
    rows = [line.split() for line in output.splitlines() if line.startswith("  ")]
    return {row[0]: row for row in rows if row[0] in jobs}


class TestSchedCommand:
    """Verify the sched story: a chain, a retry, a skipped cleanup and a restart."""

    def test_sched_story(self) -> None:
        """Every chain job succeeds, transform on its retry, and the history survives."""
        started = time.monotonic()
        output = _sched()
        elapsed = time.monotonic() - started
        board = _board(output)
        for job in sched_plugin.CHAIN:
            assert board[job][1] == "succeeded", output
        assert board["extract"][2] == FIRST_ATTEMPT
        assert board["transform"][2] == RETRIED_ATTEMPTS
        assert board["load"][2] == FIRST_ATTEMPT
        assert board["cleanup"][1] == "skipped"
        assert "cleanup skipped: load (2026-10-19) did not fail" in output
        assert "history survived the restart" in output
        assert "Traceback" not in output
        assert elapsed < SCHED_MAX_SECONDS

    def test_triggers_the_fixed_run_date(self) -> None:
        """The demo always uses the same run date, so its output never depends on today."""
        assert f"Triggered extract.{sched_plugin.RUN_DATE}.1" in _sched()


class TestSchedulerPluginInfo:
    """Verify the plugin's metadata and commands."""

    def test_info_and_commands(self) -> None:
        """The plugin is called PyScheduler and adds only the sched command."""
        plugin = PySchedulerPlugin()
        assert plugin.info().name == "PyScheduler"
        assert [c.name for c in plugin.shell_commands()] == ["sched", "schedalerts", "schedweb"]


class _PartialClient(ApiClient):
    """An API client whose scheduler only remembers the extract run."""

    def runs(self, *args: object, **kwargs: object) -> JsonObject:
        """Return just one run, as if the rest of the history were lost."""
        del args, kwargs
        return {"runs": [{"job": "extract", "state": "succeeded"}]}


class TestSchedFailures:
    """Verify the demo says so when something goes wrong."""

    def test_a_bad_config_stops_before_ready(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A config the scheduler refuses raises its ConfigError instead of hanging."""
        bad = tmp_path / "pysched.yaml"
        bad.write_text("jobs:\n  oops:\n    command: 'true'\n    schedule: never\n")

        def write_bad(folder: Path) -> Path:
            """Ignore the demo's folder and hand back the broken config."""
            del folder
            return bad

        monkeypatch.setattr(sched_plugin, "write_config", write_bad)
        with pytest.raises(ConfigError):
            _sched()

    def test_a_slow_chain_times_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If the chain has not finished in time, waiting gives up with TimeoutError."""
        monkeypatch.setattr(sched_plugin, "DONE_SECONDS", 0.0)
        with pytest.raises(TimeoutError, match="did not finish"):
            _sched()

    def test_lost_history_is_reported(self) -> None:
        """A restart that finds fewer runs says the history was lost."""
        lines = sched_plugin.second_start(_PartialClient("http://127.0.0.1:1", None))
        assert lines[-1] == "history was lost -- that should never happen!"
