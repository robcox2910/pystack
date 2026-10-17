"""Tests for the ``dbcrash`` demo of PyDB's journal.

A child process commits three job runs and dies in the middle of a
fourth; the demo reopens the folder and shows what survived.
"""

import sys
import time
from pathlib import Path

import pytest
from pydb.database import Database

from pystack.plugins import pydb_plugin
from pystack.plugins._dbcrash_child import (
    COMMITTED_RUNS,
    CRASH_EXIT_CODE,
    TABLE,
    UNFINISHED_RUN,
    runs_schema,
)
from pystack.plugins.pydb_plugin import PyDBPlugin

DBCRASH_RUNS = 3
DBCRASH_MAX_LINES = 20
DBCRASH_MAX_SECONDS = 3.0
ORDINARY_ERROR_EXIT = 1
BROKEN_CHILD = "import sys; sys.stderr.write('ModuleNotFoundError: no pydb here\\n'); sys.exit(1)"


def _dbcrash() -> str:
    """Run the dbcrash command and return its output."""
    cmds = {c.name: c.handler for c in PyDBPlugin().shell_commands()}
    return cmds["dbcrash"]([])


class TestDbcrashCommand:
    """Verify the dbcrash story of crash recovery."""

    def test_dbcrash_story(self) -> None:
        """Three committed runs survive and the unfinished fourth is gone."""
        output = _dbcrash()
        lines = output.splitlines()
        assert "  job 1: nightly-backup ran on 2026-10-15, started 2026-10-15T02:00:00Z" in lines
        assert "  job 2: tidy-logs ran on 2026-10-16, started 2026-10-16T03:15:00Z" in lines
        assert "  job 3: send-report ran on 2026-10-17, started 2026-10-17T07:30:00Z" in lines
        assert "job 4: never committed, so it's gone" in lines
        assert "rebuild-index" not in output
        assert "Traceback" not in output
        assert len(lines) < DBCRASH_MAX_LINES

    def test_dbcrash_is_deterministic_and_quick(self) -> None:
        """Every run prints the same story in under three seconds."""
        started = time.monotonic()
        outputs = {_dbcrash() for _ in range(DBCRASH_RUNS)}
        assert len(outputs) == 1
        assert (time.monotonic() - started) / DBCRASH_RUNS < DBCRASH_MAX_SECONDS


class TestDbcrashChecksTheHelper:
    """The story is only told when the helper really crashed where planned."""

    def test_crash_code_differs_from_an_ordinary_error(self) -> None:
        """Use a crash exit code an uncaught error can't produce by accident."""
        assert CRASH_EXIT_CODE != ORDINARY_ERROR_EXIT

    def test_unexpected_helper_failure_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Say the helper failed, show its last error lines, and skip recovery."""

        def broken_command(_folder: Path) -> list[str]:
            """Return a helper command that fails the ordinary way."""
            return [sys.executable, "-c", BROKEN_CHILD]

        monkeypatch.setattr(pydb_plugin, "child_command", broken_command)
        output = _dbcrash()
        lines = output.splitlines()
        assert any("stopped unexpectedly (exit code 1)" in line for line in lines)
        assert "  ModuleNotFoundError: no pydb here" in lines
        assert "crashed (exit code" not in output
        assert "Reopening" not in output
        assert "Traceback" not in output

    def test_a_surviving_job_4_is_called_out(self, tmp_path: Path) -> None:
        """Flag it loudly if the unfinished job somehow survived."""
        with Database(tmp_path, journal=True) as db:
            runs = db.create_table(TABLE, runs_schema())
            for job, run_date, started in (*COMMITTED_RUNS, UNFINISHED_RUN):
                runs.insert({"job": job, "run_date": run_date, "started": started})
        lines = pydb_plugin.recovery_lines(tmp_path)
        assert "job 4: survived -- that should never happen!" in lines
