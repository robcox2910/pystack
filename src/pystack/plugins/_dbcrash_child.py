"""The helper program for the ``dbcrash`` demo -- the one that gets unplugged.

It opens a journalled PyDB database, records three job runs (each one
committed, so each is written in the journal "diary" first), then starts a
fourth inside a transaction and dies without warning. Think of a clerk who
writes three finished jobs in the diary, picks up a fourth, and the lights go
out before it is signed off.

Run it with ``python -m pystack.plugins._dbcrash_child <folder>``.
"""

import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from pydb.database import Database
from pydb.schema import Column, Schema
from pydb.transaction import Transaction
from pydb.types import DataType

TABLE = "job_runs"
COMMITTED_RUNS = (
    ("nightly-backup", date(2026, 10, 15), datetime(2026, 10, 15, 2, 0, tzinfo=UTC)),
    ("tidy-logs", date(2026, 10, 16), datetime(2026, 10, 16, 3, 15, tzinfo=UTC)),
    ("send-report", date(2026, 10, 17), datetime(2026, 10, 17, 7, 30, tzinfo=UTC)),
)
UNFINISHED_RUN = ("rebuild-index", date(2026, 10, 17), datetime(2026, 10, 17, 8, 0, tzinfo=UTC))
CRASH_EXIT_CODE = 9  # unusual on purpose: a program that hits an error exits with 1


def runs_schema() -> Schema:
    """Return the job-run table's columns: a name, a run date and a start time."""
    return Schema(
        columns=[
            Column("job", DataType.TEXT),
            Column("run_date", DataType.DATE),
            Column("started", DataType.TIMESTAMP),
        ]
    )


def crash_mid_transaction(folder: Path) -> None:
    """Commit three job runs, start a fourth, then die without committing."""
    db = Database(folder, journal=True)
    runs = db.create_table(TABLE, runs_schema())
    for job, run_date, started in COMMITTED_RUNS:
        runs.insert({"job": job, "run_date": run_date, "started": started})
    txn = Transaction(db)
    job, run_date, started = UNFINISHED_RUN
    txn.get_table(TABLE).insert({"job": job, "run_date": run_date, "started": started})
    os._exit(CRASH_EXIT_CODE)  # the power cut: no commit, no close, no clean-up


if __name__ == "__main__":
    crash_mid_transaction(Path(sys.argv[1]))
