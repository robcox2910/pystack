"""Property-based tests -- rules that must hold for *every* input.

An ordinary test checks one example someone thought of: "store
``name -> Ada``, restart PyStack, and ``name`` is still Ada". A property
test states a rule instead, such as "whatever a program stores, it is all
still there after a restart", and lets Hypothesis invent hundreds of
inputs to try to break it. If one breaks the rule, Hypothesis *shrinks* it
down to the smallest input that still fails, and shows you that.

Each test below says its rule in plain English in its docstring. The
strategies at the top are recipes for making random inputs; each one is
named for what it makes.

The step-by-step check of the kv plugin against a plain dict lives in
``tests/test_model.py``. See ``docs/property-testing.md`` for the walk-through.
"""

import re
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from pydb.database import Database
from pydb.record import Value as PyDBValue
from pydb.schema import Column, Schema
from pydb.types import DataType
from pygraphdb.graph import Graph
from pygraphdb.persistence import save_graph
from pysearch.engine import SearchEngine
from pysearch.errors import PersistenceError
from pysearch.persistence import save_engine

from pystack.adapters.pebble_db import make_db_module
from pystack.environment import PyStackEnvironment
from tests.strategies import call_pebble, kv_keys, kv_values

# The file names this plugin gives saved engines: ``engine_`` and a number.
OUR_ENGINE_FILE = re.compile(r"engine_[0-9]+")

# Python's ``int`` refuses to read more than 4,300 digits at once.
INT_DIGIT_LIMIT = 4300

# The Pebble values a database row may turn into: plain text, numbers,
# True/False and nothing. (Pebble has lists, dicts and more, but a single
# table cell is never one of those.)
PLAIN_PEBBLE_TYPES = (str, int, float, bool, type(None))

# --- Strategies: recipes for random inputs -----------------------------------
# kv_keys() and kv_values() live in tests/strategies.py, shared with the model.


def kv_contents() -> st.SearchStrategy[dict[str, str]]:
    """Make everything one kv store might hold: any keys, each with any text."""
    return st.dictionaries(kv_keys(), kv_values())


def utc_timestamps() -> st.SearchStrategy[datetime]:
    """Make any moment in time, written in UTC."""
    # PyDB turns every TIMESTAMP into UTC before storing it (see
    # pydb.types.check_value), so a table only ever holds UTC times.
    return st.datetimes(timezones=st.just(UTC))


def pydb_rows() -> st.SearchStrategy[dict[str, PyDBValue]]:
    """Make one row for a table with a column of every PyDB type, any of them NULL."""
    return st.fixed_dictionaries(
        {
            "text": st.none() | st.text(),
            "integer": st.none() | st.integers(),
            # NaN and infinity are floats too, and PyDB stores them.
            "float": st.none() | st.floats(),
            "boolean": st.none() | st.booleans(),
            "date": st.none() | st.dates(),
            "timestamp": st.none() | utc_timestamps(),
        }
    )


def name_pieces() -> st.SearchStrategy[str]:
    """Make a short run of letters, digits (from any script), ``_`` and ``-``."""
    # Letters and digits from every language, but no ``/`` or other
    # characters an operating system won't put in a file name.
    return st.text(
        alphabet=st.characters(categories=["L", "N"], include_characters="_-"),
        max_size=10,
    )


def search_file_stems() -> st.SearchStrategy[str]:
    """Make a file name for the search folder: ``engine_7``, look-alikes such as ``engine_x``, anything."""
    ours = st.integers(min_value=0, max_value=20).map("engine_{}".format)
    return st.one_of(ours, name_pieces().map("engine_".__add__), name_pieces())


def long_digit_runs() -> st.SearchStrategy[str]:
    """Make a run of ``1``s around Python's 4,300-digit limit for ``int``."""
    lengths = st.integers(min_value=INT_DIGIT_LIMIT - 10, max_value=INT_DIGIT_LIMIT + 10)
    return lengths.map("1".__mul__)


def edge_ids() -> st.SearchStrategy[str]:
    """Make an edge id: ``e7``, look-alikes such as ``e²`` or ``e111...1``, anything."""
    ours = st.integers(min_value=1, max_value=20).map("e{}".format)
    digits = st.text(alphabet=st.characters(categories=["N"]), min_size=1, max_size=3)
    return st.one_of(ours, digits.map("e".__add__), long_digit_runs().map("e".__add__), st.text())


# --- Helpers -----------------------------------------------------------------


def start_or_refuse(folder: Path) -> PyStackEnvironment | None:
    """Start PyStack on *folder*, accepting only a PersistenceError refusal.

    A PersistenceError means "I won't load that", which is fine, so it gives
    ``None``. Any *other* exception escapes and fails the test, and that is
    the whole check.
    """
    try:
        return PyStackEnvironment(db_path=folder)
    except PersistenceError:
        return None


def pebble_value_back_to_pydb(value: object, data_type: DataType) -> object:
    """Turn a value Pebble received back into the PyDB value it came from.

    This uses Python's own ``fromisoformat``, not PyDB's helpers, so it
    doesn't share any code with the adapter it checks.
    """
    if value is None:
        return None
    if data_type is DataType.DATE:
        return date.fromisoformat(str(value))
    if data_type is DataType.TIMESTAMP:
        text = str(value)
        # A TIMESTAMP crosses as UTC, written with a ``Z`` on the end.
        assert text.endswith("Z")
        return datetime.fromisoformat(text)
    return value


# --- PyDB to Pebble: every value gets across, and can be turned back ----------


@given(row=pydb_rows())
def test_every_pydb_value_reaches_pebble_and_maps_back(row: dict[str, PyDBValue]) -> None:
    """Every value a table holds reaches Pebble as a plain Pebble value, and maps back exactly."""
    with tempfile.TemporaryDirectory() as folder:
        database = Database(path=Path(folder))
        columns = [Column(name, DataType(name.upper())) for name in row]
        # The row has a column of every type PyDB has, so no type is left out.
        assert {column.data_type for column in columns} == set(DataType)
        database.create_table("cells", Schema(columns))
        stored = database.get_table("cells").insert(row).data
        db_query = make_db_module(database).functions["db_query"][1]
        assert db_query is not None
        received = db_query(["SELECT * FROM cells"])
    assert isinstance(received, list)
    [pebble_row] = received
    assert isinstance(pebble_row, dict)
    for column in columns:
        value = pebble_row[column.name]
        assert type(value) in PLAIN_PEBBLE_TYPES
        back = pebble_value_back_to_pydb(value, column.data_type)
        original = stored[column.name]
        # ``==`` thinks True == 1 == 1.0, so check the type separately.
        assert type(back) is type(original)
        if isinstance(original, float):
            # ``repr`` tells -0.0 from 0.0, and NaN (which never equals
            # itself) is written ``nan``.
            assert repr(back) == repr(original)
        else:
            assert back == original


# --- Restarting: what a program stored is still there --------------------------


@given(contents=kv_contents())
def test_kv_data_survives_a_restart(contents: dict[str, str]) -> None:
    """Whatever a program stores with ``kv_set``, the next run reads back exactly."""
    with tempfile.TemporaryDirectory() as folder:
        first = PyStackEnvironment(db_path=Path(folder))
        for key, value in contents.items():
            call_pebble(first, "kv", "kv_set", key, value)
        first.shutdown()

        second = PyStackEnvironment(db_path=Path(folder))
        try:
            listed = call_pebble(second, "kv", "kv_keys")
            assert isinstance(listed, list)
            assert sorted(map(str, listed)) == sorted(contents)
            for key, value in contents.items():
                assert call_pebble(second, "kv", "kv_get", key) == value
        finally:
            second.shutdown()


# --- Odd things in the data folder: start up, or refuse, never crash -----------


@given(stems=st.lists(search_file_stems(), max_size=3, unique=True))
def test_any_engine_file_name_starts_or_raises_persistence_error(stems: list[str]) -> None:
    """Whatever the saved engine files are called, PyStack starts and lists its own, or refuses cleanly."""
    with tempfile.TemporaryDirectory() as folder:
        search_folder = Path(folder) / "search"
        search_folder.mkdir()
        for stem in stems:
            save_engine(SearchEngine(), search_folder / f"{stem}.json")
        env = start_or_refuse(Path(folder))
        if env is not None:
            listed = call_pebble(env, "search", "search_list")
            assert isinstance(listed, list)
            ours = [stem for stem in stems if OUR_ENGINE_FILE.fullmatch(stem)]
            assert sorted(map(str, listed)) == sorted(ours)
            new_id = call_pebble(env, "search", "search_create")
            assert new_id not in stems
            env.shutdown()


@given(saved_ids=st.lists(edge_ids(), max_size=3, unique=True))
def test_new_edges_never_reuse_a_saved_edge_id(saved_ids: list[str]) -> None:
    """Whatever ids the saved edges have, PyStack starts and a new edge gets an id nobody has."""
    with tempfile.TemporaryDirectory() as folder:
        graph = Graph()
        graph.add_node("a")
        for edge_id in saved_ids:
            graph.add_edge(edge_id, "a", "a")
        (Path(folder) / "graphdb").mkdir()
        save_graph(graph, Path(folder) / "graphdb" / "graph.json")
        env = PyStackEnvironment(db_path=Path(folder))
        try:
            new_id = call_pebble(env, "graphdb", "graph_add_edge", "a", "a", "LOOP")
            assert isinstance(new_id, str)
            assert not new_id.startswith("error:")
            assert new_id not in saved_ids
        finally:
            env.shutdown()
