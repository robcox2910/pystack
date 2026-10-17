"""PyDB integration plugin for PyStack.

PyDB itself is wired in through the environment (the ``sql`` command and the
Pebble ``db`` module); this plugin adds the shell demos that show off what
PyDB can do.

Shell command ``dbcrash`` pulls the plug on a journalled database. A helper
program writes three job runs in the journal "diary", starts a fourth and
dies before finishing it, like a power cut. We then reopen the folder:
recovery reads the diary, puts back the three finished runs, and leaves out
the one that was never signed off.

This plugin has no Pebble module.
"""

import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from pydb.database import Database
from pydb.record import Value
from pydb.types import to_iso

from pystack.plugins._dbcrash_child import TABLE, UNFINISHED_RUN
from pystack.plugins.base import Plugin, PluginInfo, ShellCommand

CHILD_MODULE = "pystack.plugins._dbcrash_child"
CHILD_TIMEOUT = 20


def _show(value: Value) -> str:
    """Return *value* as text, with dates and timestamps in their ISO form."""
    return to_iso(value) if isinstance(value, date) else str(value)


def _dbcrash_cmd(_args: list[str]) -> str:
    """Crash a helper mid-transaction, reopen its database and report what survived."""
    lines = ["Starting a helper program that writes job runs to a journalled database..."]
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "jobs-db"
        result = subprocess.run(  # noqa: S603 -- fixed argv: our own interpreter and module
            [sys.executable, "-m", CHILD_MODULE, str(folder)],
            check=False,
            capture_output=True,
            timeout=CHILD_TIMEOUT,
        )
        lines.append(
            f"The helper program crashed (exit code {result.returncode}) in the middle of job 4."
        )
        lines.append("")
        lines.append("Reopening the folder -- recovery reads the journal diary:")
        with Database(folder, journal=True) as db:
            runs = db.get_table(TABLE)
            records = runs.select()
            lines.extend(
                f"  job {r.record_id}: {r['job']} ran on {_show(r['run_date'])}, "
                f"started {_show(r['started'])}"
                for r in records
            )
            if all(r["job"] != UNFINISHED_RUN[0] for r in records):
                lines.append("job 4: never committed, so it's gone")
            else:
                lines.append("job 4: survived -- that should never happen!")
            lines.append(f"The next new job run gets ID {runs.next_id}.")
    return "\n".join(lines)


class PyDBPlugin(Plugin):
    """Add PyDB's shell demos to PyStack (currently ``dbcrash``)."""

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyDB",
            description="Crash-recovery demo for PyDB's journal",
            version="0.1.0",
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the dbcrash shell command."""
        return [
            ShellCommand(
                name="dbcrash",
                handler=_dbcrash_cmd,
                help_text="Crash a journalled PyDB mid-transaction and watch it recover",
            ),
        ]
