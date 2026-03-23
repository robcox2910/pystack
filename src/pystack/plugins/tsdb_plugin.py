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

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pytsdb.aggregation import AggFunc, aggregate
from pytsdb.database import TimeSeriesDB

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_db: TimeSeriesDB | None = None


def _get_db() -> TimeSeriesDB:
    """Return the shared TimeSeriesDB instance, creating it if needed."""
    global _db  # noqa: PLW0603
    if _db is None:
        _db = TimeSeriesDB()
    return _db


@pebble_handler
def _ts_add(args: list[PebbleValue]) -> PebbleValue:
    """Add a data point to a named time series."""
    series_name = str(args[0])
    value = float(str(args[1]))
    db = _get_db()
    # Auto-create the series if it doesn't exist.
    if series_name not in db.list_series():
        db.create_series(series_name)
    db.add_point(series_name, value=value)
    return "ok"


@pebble_handler
def _ts_query(args: list[PebbleValue]) -> PebbleValue:
    """Query all data points in a named time series."""
    series_name = str(args[0])
    db = _get_db()
    points = db.query(series_name)
    result: list[PebbleValue] = [p.value for p in points]
    return result


@pebble_handler
def _ts_avg(args: list[PebbleValue]) -> PebbleValue:
    """Compute the average of a series over a time window (in seconds)."""
    series_name = str(args[0])
    window_seconds = int(str(args[1]))
    db = _get_db()
    points = db.query(series_name)
    if not points:
        return "error: no data points"
    window = timedelta(seconds=window_seconds)
    agg_points = aggregate(points, window=window, func=AggFunc.AVG)
    if not agg_points:
        return "error: no data in window"
    result: list[PebbleValue] = [p.value for p in agg_points]
    return result


def reset_tsdb_state() -> None:
    """Reset all module-level state for testing."""
    global _db  # noqa: PLW0603
    _db = None


class TSDBPlugin(Plugin):
    """Integrate PyTSDB time-series database functions into PyStack.

    Register add/query/avg functions in Pebble's ``tsdb`` stdlib
    module and shell commands for interactive use.
    """

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
                "ts_add": (2, _ts_add),
                "ts_query": (1, _ts_query),
                "ts_avg": (2, _ts_avg),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the ts shell commands."""

        def _ts_add_cmd(args: list[str]) -> str:
            """Add a data point to a series."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: ts-add <series> <value>"
            series_name, value = args[0], float(args[1])
            db = _get_db()
            if series_name not in db.list_series():
                db.create_series(series_name)
            db.add_point(series_name, value=value)
            return f"Added {value} to '{series_name}'"

        def _ts_query_cmd(args: list[str]) -> str:
            """Query data points in a series."""
            if not args:
                return "Usage: ts-query <series>"
            points = _get_db().query(args[0])
            if not points:
                return "(no data points)"
            return "\n".join(f"{p.timestamp}: {p.value}" for p in points)

        def _ts_avg_cmd(args: list[str]) -> str:
            """Compute average over a time window."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: ts-avg <series> <window_seconds>"
            points = _get_db().query(args[0])
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
