"""PyTSDB integration plugin for PyStack.

Bridge PyTSDB's time-series database into Pebble so kids can record
timestamped measurements, query time ranges, and compute averages.

A time-series database is like a weather station's logbook -- every
few minutes you jot down the temperature along with the current time.

Pebble module name: ``tsdb``

Example Pebble usage::

    import "tsdb"
    ts_add("temperature", 72.5)
    ts_add("temperature", 74.0)
    let avg = ts_avg("temperature", 3600)
    print(avg)
"""

from datetime import timedelta
from pathlib import Path

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pytsdb.aggregation import AggFunc, aggregate
from pytsdb.database import TimeSeriesDB
from pytsdb.errors import PyTSDBError
from pytsdb.persistence import load, save

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method

_DB_FILE = "db.json"


class TSDBPlugin(Plugin):
    """Integrate PyTSDB time-series database functions into PyStack.

    Register add/query/avg functions in Pebble's ``tsdb`` stdlib
    module and shell commands for interactive use.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._db: TimeSeriesDB | None = None

    def _get_db(self) -> TimeSeriesDB:
        """Return this plugin's TimeSeriesDB, creating it on first use."""
        if self._db is None:
            self._db = TimeSeriesDB()
        return self._db

    def _add_point(self, series_name: str, raw_value: str) -> float | str:
        """Add *raw_value* to *series_name*, creating the series if needed.

        Returns:
            The value added, or an ``"error: ..."`` message when the value
            isn't a number (``"abc"``) or PyTSDB refuses it (``"nan"``).

        """
        try:
            value = float(raw_value)
            db = self._get_db()
            # Auto-create the series if it doesn't exist.
            if series_name not in db.list_series():
                db.create_series(series_name)
            db.add_point(series_name, value=value)
        except (ValueError, PyTSDBError) as exc:
            return f"error: {exc}"
        return value

    @pebble_method
    def ts_add(self, args: list[PebbleValue]) -> PebbleValue:
        """Add a data point to a named time series: "ok", or "error: ..." for a bad value."""
        added = self._add_point(str(args[0]), str(args[1]))
        return added if isinstance(added, str) else "ok"

    @pebble_method
    def ts_query(self, args: list[PebbleValue]) -> PebbleValue:
        """Query all data points in a named time series."""
        series_name = str(args[0])
        db = self._get_db()
        points = db.query(series_name)
        result: list[PebbleValue] = [p.value for p in points]
        return result

    @pebble_method
    def ts_avg(self, args: list[PebbleValue]) -> PebbleValue:
        """Compute the average of a series over a time window (in seconds)."""
        series_name = str(args[0])
        window_seconds = int(str(args[1]))
        db = self._get_db()
        points = db.query(series_name)
        if not points:
            return "error: no data points"
        window = timedelta(seconds=window_seconds)
        agg_points = aggregate(points, window=window, func=AggFunc.AVG)
        if not agg_points:
            return "error: no data in window"
        result: list[PebbleValue] = [p.value for p in agg_points]
        return result

    def load_state(self, folder: Path) -> None:
        """Load the saved database, if there is one."""
        path = folder / _DB_FILE
        if path.exists():
            self._db = load(path)

    def save_state(self, folder: Path) -> None:
        """Save the database, if this run used or loaded one."""
        if self._db is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        save(self._db, folder / _DB_FILE)

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyTSDB",
            description="Time-series database for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "tsdb"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the tsdb stdlib module with add/query/avg functions."""
        return StdlibModule(
            functions={
                "ts_add": (2, self.ts_add),
                "ts_query": (1, self.ts_query),
                "ts_avg": (2, self.ts_avg),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the ts shell commands."""

        def _ts_add_cmd(args: list[str]) -> str:
            """Add a data point to a series."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: ts-add <series> <value>"
            series_name = args[0]
            added = self._add_point(series_name, args[1])
            if isinstance(added, str):
                return added
            return f"Added {added} to '{series_name}'"

        def _ts_query_cmd(args: list[str]) -> str:
            """Query data points in a series."""
            if not args:
                return "Usage: ts-query <series>"
            points = self._get_db().query(args[0])
            if not points:
                return "(no data points)"
            return "\n".join(f"{p.timestamp}: {p.value}" for p in points)

        def _ts_avg_cmd(args: list[str]) -> str:
            """Compute average over a time window."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: ts-avg <series> <window_seconds>"
            points = self._get_db().query(args[0])
            if not points:
                return "(no data points)"
            window = timedelta(seconds=int(args[1]))
            agg_points = aggregate(points, window=window, func=AggFunc.AVG)
            return "\n".join(f"{p.timestamp}: {p.value}" for p in agg_points)

        return [
            ShellCommand(name="ts-add", handler=_ts_add_cmd, help_text="Add data point"),
            ShellCommand(name="ts-query", handler=_ts_query_cmd, help_text="Query series"),
            ShellCommand(name="ts-avg", handler=_ts_avg_cmd, help_text="Average over window"),
        ]
