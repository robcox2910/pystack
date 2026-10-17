"""Tests for the ``dbcrash`` demo of PyDB's journal.

A child process commits three job runs and dies in the middle of a
fourth; the demo reopens the folder and shows what survived.
"""

import time

from pystack.plugins.pydb_plugin import PyDBPlugin

DBCRASH_RUNS = 3
DBCRASH_MAX_LINES = 20
DBCRASH_MAX_SECONDS = 3.0


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
