"""Tests that plugin data is kept between runs, and kept apart between environments.

Write something through Pebble, shut PyStack down, start it again on the
same data folder, and the data is still there -- just like a real database.
"""

import re
from pathlib import Path

import pytest
from pycoldb.errors import PersistenceError as ColDBPersistenceError
from pydocdb.errors import PersistenceError as DocDBPersistenceError
from pygraphdb.errors import PersistenceError as GraphPersistenceError
from pygraphdb.graph import Graph
from pygraphdb.persistence import save_graph
from pykv.errors import PersistenceError as KVPersistenceError
from pymq.errors import PersistenceError as MQPersistenceError
from pysearch.engine import SearchEngine
from pysearch.errors import PersistenceError as SearchPersistenceError
from pysearch.persistence import save_engine
from pytsdb.errors import PersistenceError as TSDBPersistenceError
from pyvecdb.errors import PersistenceError as VecDBPersistenceError

from pystack.environment import PyStackEnvironment

PLUGINS_DIR = Path(__file__).parent.parent / "src" / "pystack" / "plugins"
STATEFUL = ("kv", "docdb", "graphdb", "coldb", "tsdb", "vecdb", "search", "mq")

# (module, program that writes data, program that reads it back)
ROUND_TRIPS = [
    ("kv", 'kv_set("name", "Ada")', 'print(kv_get("name"))'),
    ("docdb", 'doc_insert("pets", {"name": "Rex"})', 'print(doc_count("pets"))'),
    (
        "graphdb",
        'graph_add_node("alice", "Person")\ngraph_add_node("bob", "Person")\n'
        'graph_add_edge("alice", "bob", "KNOWS")',
        'print(graph_shortest_path("alice", "bob"))',
    ),
    (
        "coldb",
        'col_set("grades", "alice", "math", "A+")',
        'print(col_get("grades", "alice", "math"))',
    ),
    ("tsdb", 'ts_add("temperature", 72.5)', 'print(ts_query("temperature"))'),
    ("vecdb", 'vec_insert("song1", [0.9, 0.1, 0.3])', "print(vec_search([0.9, 0.1, 0.3], 1))"),
    (
        "search",
        'let e = search_create()\nsearch_add(e, "d1", "the cat sat on the mat")',
        'print(search_query("engine_0", "cat"))',
    ),
]

# (module, file inside its folder, the library's PersistenceError)
SAVE_FILES = [
    ("kv", "store.json", KVPersistenceError),
    ("docdb", "pets.json", DocDBPersistenceError),
    ("graphdb", "graph.json", GraphPersistenceError),
    ("coldb", "keyspace.json", ColDBPersistenceError),
    ("tsdb", "db.json", TSDBPersistenceError),
    ("vecdb", "store.json", VecDBPersistenceError),
    ("search", "engine_0.json", SearchPersistenceError),
    ("mq", "queues.json", MQPersistenceError),
]


def _run(env: PyStackEnvironment, module: str, program: str) -> str:
    """Run *program* with *module* imported."""
    return env.run_pebble_source(f'import "{module}"\n{program}')


class TestDataSurvivesARestart:
    """Each plugin's data is there again after PyStack restarts."""

    @pytest.mark.parametrize(("module", "write", "read"), ROUND_TRIPS)
    def test_data_survives_a_restart(
        self, tmp_path: Path, module: str, write: str, read: str
    ) -> None:
        """What one run wrote, the next run reads back unchanged."""
        first = PyStackEnvironment(db_path=tmp_path)
        _run(first, module, write)
        expected = _run(first, module, read)
        first.shutdown()

        second = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(second, module, read) == expected
        finally:
            second.shutdown()

    def test_search_ids_continue_after_saved_ones(self, tmp_path: Path) -> None:
        """A new engine after a restart gets a fresh id, never a saved one's."""
        first = PyStackEnvironment(db_path=tmp_path)
        _run(first, "search", "search_create()\nsearch_create()")
        first.shutdown()
        second = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(second, "search", "print(search_create())") == "engine_2\n"
        finally:
            second.shutdown()


class TestMessagesSurviveARestart:
    """Waiting messages are kept like a real broker keeps them; live subscriptions are not."""

    def test_waiting_messages_survive_a_restart(self, tmp_path: Path) -> None:
        """Messages still waiting when PyStack stops are handed out, in order, next time."""
        first = PyStackEnvironment(db_path=tmp_path)
        _run(
            first,
            "mq",
            'mq_create("orders")\nmq_put("orders", "one coffee")\nmq_put("orders", "two muffins")\n'
            'print(mq_get("orders"))',
        )
        first.shutdown()
        second = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(second, "mq", 'print(mq_get("orders"))\nprint(mq_get("orders"))') == (
                "two muffins\nempty\n"
            )
        finally:
            second.shutdown()

    def test_shell_commands_share_the_saved_queues(self, tmp_path: Path) -> None:
        """``mq-put`` in one session is waiting for ``mq-get`` in the next."""
        first = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        first.execute_shell("mq-put orders one coffee")
        first.shutdown()
        second = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            assert second.execute_shell("mq-get orders").strip() == "one coffee"
        finally:
            second.shutdown()

    def test_subscriptions_are_live_only(self, tmp_path: Path) -> None:
        """Pub/sub is like live radio: a subscription doesn't outlive the run."""
        first = PyStackEnvironment(db_path=tmp_path)
        _run(first, "mq", 'mq_subscribe("news")\nmq_publish("news", "hello")')
        first.shutdown()
        second = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(second, "mq", 'print(mq_receive("news"))') == (
                "error: not subscribed to 'news'\n"
            )
        finally:
            second.shutdown()

    def test_two_environments_do_not_share_queues(self, tmp_path: Path) -> None:
        """A queue made in one environment doesn't exist in another."""
        first = PyStackEnvironment(db_path=tmp_path / "first")
        second = PyStackEnvironment(db_path=tmp_path / "second")
        try:
            _run(first, "mq", 'mq_create("orders")\nmq_put("orders", "x")')
            assert _run(second, "mq", 'print(mq_get("orders"))') == (
                "error: queue 'orders' not found\n"
            )
        finally:
            first.shutdown()
            second.shutdown()


class TestEnvironmentsAreSeparate:
    """Two environments in one process never share plugin data."""

    @pytest.mark.parametrize(
        ("module", "write", "read"), [ROUND_TRIPS[0], ROUND_TRIPS[2], ROUND_TRIPS[6]]
    )
    def test_two_environments_do_not_share_plugin_data(
        self, tmp_path: Path, module: str, write: str, read: str
    ) -> None:
        """Data written in one environment is invisible in another."""
        first = PyStackEnvironment(db_path=tmp_path / "first")
        second = PyStackEnvironment(db_path=tmp_path / "second")
        try:
            _run(first, module, write)
            assert _run(second, module, read) != _run(first, module, read)
        finally:
            first.shutdown()
            second.shutdown()


class TestSavingIsCareful:
    """Nothing is written needlessly, and damaged files are never overwritten."""

    def test_untouched_plugins_write_nothing(self, tmp_path: Path) -> None:
        """A run that never used a plugin leaves no plugin folders behind."""
        PyStackEnvironment(db_path=tmp_path).shutdown()
        assert not [name for name in STATEFUL if (tmp_path / name).exists()]

    @pytest.mark.parametrize(("module", "filename", "error"), SAVE_FILES)
    def test_corrupt_save_file_stops_boot_and_is_kept(
        self, tmp_path: Path, module: str, filename: str, error: type[Exception]
    ) -> None:
        """A damaged save file stops start-up, names the file, and is left untouched."""
        folder = tmp_path / module
        folder.mkdir()
        damaged = folder / filename
        damaged.write_text("{not json", encoding="utf-8")
        with pytest.raises(error, match=re.escape(filename)):
            PyStackEnvironment(db_path=tmp_path)
        assert damaged.read_text(encoding="utf-8") == "{not json"


class TestNoGlobalState:
    """Plugin data lives on plugin instances, not in module-level variables."""

    @pytest.mark.parametrize("module", STATEFUL)
    def test_no_global_state_left(self, module: str) -> None:
        """No ``global`` statements or ``reset_*`` helpers remain."""
        source = (PLUGINS_DIR / f"{module}_plugin.py").read_text(encoding="utf-8")
        assert "global " not in source
        assert "def reset_" not in source


class TestReviewFixes:
    """Regressions found in the final review of plugin persistence."""

    @pytest.mark.parametrize(
        ("module", "filename", "content", "error"),
        [
            ("docdb", "pets.json", "{}", DocDBPersistenceError),
            ("kv", "store.json", "[]", KVPersistenceError),
            ("coldb", "keyspace.json", "{}", ColDBPersistenceError),
            ("mq", "queues.json", "{}", MQPersistenceError),
        ],
    )
    def test_wrong_shape_save_file_stops_boot_and_is_kept(
        self, tmp_path: Path, module: str, filename: str, content: str, error: type[Exception]
    ) -> None:
        """Valid JSON that isn't a save file stops start-up instead of loading as empty."""
        folder = tmp_path / module
        folder.mkdir()
        (folder / filename).write_text(content, encoding="utf-8")
        with pytest.raises(error, match=re.escape(filename)):
            PyStackEnvironment(db_path=tmp_path)
        assert (folder / filename).read_text(encoding="utf-8") == content

    def test_docdb_collections_differing_only_in_case_stay_separate(self, tmp_path: Path) -> None:
        """``Pets`` and ``pets`` are different collections, even on a case-insensitive disk."""
        first = PyStackEnvironment(db_path=tmp_path)
        _run(
            first,
            "docdb",
            'doc_insert("Pets", {"n": 1})\ndoc_insert("pets", {"n": 2})\ndoc_insert("pets", {"n": 3})',
        )
        first.shutdown()
        second = PyStackEnvironment(db_path=tmp_path)
        try:
            assert (
                _run(second, "docdb", 'print(doc_count("Pets"))\nprint(doc_count("pets"))')
                == "1\n2\n"
            )
        finally:
            second.shutdown()

    def test_saved_search_engines_can_be_listed(self, tmp_path: Path) -> None:
        """A later program can find saved engines without guessing their ids."""
        first = PyStackEnvironment(db_path=tmp_path)
        _run(first, "search", "search_create()\nsearch_create()")
        first.shutdown()
        second = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(second, "search", "print(search_list())") == "[engine_0, engine_1]\n"
        finally:
            second.shutdown()

    def test_searching_an_empty_vector_store_does_not_fix_its_size(self, tmp_path: Path) -> None:
        """A failed search on an empty store leaves the vector size open."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            output = _run(
                env,
                "vecdb",
                'print(vec_search([1.0, 2.0], 1))\nprint(vec_insert("a", [1.0, 2.0, 3.0]))',
            )
            assert output.splitlines()[1] == "a"
        finally:
            env.shutdown()


class TestOddNamesInSaveFiles:
    """Names PyStack didn't make itself never crash start-up (found by a property test)."""

    def test_engine_file_without_a_number_is_left_alone(self, tmp_path: Path) -> None:
        """``engine_.json`` isn't an engine PyStack saved: start-up skips it and leaves it be."""
        folder = tmp_path / "search"
        folder.mkdir()
        stray = folder / "engine_.json"
        save_engine(SearchEngine(), stray)
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(env, "search", "print(search_list())") == "[]\n"
            assert _run(env, "search", "print(search_create())") == "engine_0\n"
        finally:
            env.shutdown()
        assert stray.exists()

    def test_saved_edge_id_with_a_superscript_digit_loads(self, tmp_path: Path) -> None:
        """An edge called ``e²`` isn't one PyStack numbered, so new edges start at ``e1``."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("e²", "a", "a")
        (tmp_path / "graphdb").mkdir()
        save_graph(graph, tmp_path / "graphdb" / "graph.json")
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(env, "graphdb", 'print(graph_add_edge("a", "a", "LOOP"))') == "e1\n"
        finally:
            env.shutdown()

    def test_saved_edge_id_with_thousands_of_digits_loads(self, tmp_path: Path) -> None:
        """An edge id too long for ``int`` to read isn't one PyStack numbered either."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("e" + "1" * 5000, "a", "a")
        (tmp_path / "graphdb").mkdir()
        save_graph(graph, tmp_path / "graphdb" / "graph.json")
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            assert _run(env, "graphdb", 'print(graph_add_edge("a", "a", "LOOP"))') == "e1\n"
        finally:
            env.shutdown()
