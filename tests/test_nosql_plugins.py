"""Tests for the NoSQL database integration plugins.

Verify that each NoSQL plugin (kv, docdb, graphdb, tsdb, vecdb, coldb)
registers Pebble stdlib functions correctly and that Pebble programs
can call them through the PyStackEnvironment.
"""

from pathlib import Path

from pebble.stdlib import STDLIB_MODULES

from pystack.environment import PyStackEnvironment
from pystack.plugins.coldb_plugin import (
    ColDBPlugin,
    _col_delete,
    _col_get,
    _col_set,
    reset_coldb_state,
)
from pystack.plugins.docdb_plugin import (
    DocDBPlugin,
    _doc_count,
    _doc_find,
    _doc_insert,
    reset_docdb_state,
)
from pystack.plugins.graphdb_plugin import (
    GraphDBPlugin,
    _graph_add_edge,
    _graph_add_node,
    _graph_bfs,
    _graph_shortest_path,
    reset_graphdb_state,
)
from pystack.plugins.kv_plugin import (
    KVPlugin,
    _kv_delete,
    _kv_get,
    _kv_keys,
    _kv_set,
    reset_kv_state,
)
from pystack.plugins.tsdb_plugin import TSDBPlugin, _get_db, _ts_add, _ts_query, reset_tsdb_state
from pystack.plugins.vecdb_plugin import (
    VecDBPlugin,
    _vec_cosine,
    _vec_insert,
    _vec_search,
    reset_vecdb_state,
)

TOTAL_PLUGIN_COUNT = 12
COSINE_TOLERANCE = 0.001


class TestKVPlugin:
    """Verify PyKV integration via the kv plugin."""

    def test_kv_set_and_get(self) -> None:
        """Setting a key and getting it back should return the value."""
        reset_kv_state()
        try:
            result = _kv_set(["name", "Alice"])
            assert result == "ok"
            value = _kv_get(["name"])
            assert value == "Alice"
        finally:
            reset_kv_state()

    def test_kv_delete(self) -> None:
        """Deleting a key should make it unavailable."""
        reset_kv_state()
        try:
            _kv_set(["temp", "123"])
            result = _kv_delete(["temp"])
            assert result == "ok"
            value = _kv_get(["temp"])
            assert value == "not found"
        finally:
            reset_kv_state()

    def test_kv_keys_returns_list(self) -> None:
        """The kv_keys handler should return a list of key names."""
        reset_kv_state()
        try:
            _kv_set(["a", "1"])
            _kv_set(["b", "2"])
            keys = _kv_keys([])
            assert isinstance(keys, list)
            assert "a" in keys
            assert "b" in keys
        finally:
            reset_kv_state()

    def test_kv_get_missing_returns_not_found(self) -> None:
        """Getting a nonexistent key should return 'not found'."""
        reset_kv_state()
        try:
            result = _kv_get(["missing"])
            assert result == "not found"
        finally:
            reset_kv_state()

    def test_kv_plugin_registers_module(self) -> None:
        """The KVPlugin should register a 'kv' stdlib module."""
        plugin = KVPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "kv_set" in stdlib.functions
        assert "kv_get" in stdlib.functions

    def test_kv_pebble_source(self, tmp_path: Path) -> None:
        """Run a Pebble program that sets and gets a key."""
        reset_kv_state()
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = (
                'import "kv"\n'
                'kv_set("greeting", "hello")\n'
                'let val = kv_get("greeting")\n'
                "print(val)"
            )
            output = env.run_pebble_source(source)
            assert output.strip() == "hello"
        finally:
            reset_kv_state()
            env.shutdown()


class TestDocDBPlugin:
    """Verify PyDocDB integration via the docdb plugin."""

    def test_doc_insert_returns_id(self) -> None:
        """Inserting a document should return the document id."""
        reset_docdb_state()
        try:
            result = _doc_insert(["users", {"name": "Alice"}])
            assert isinstance(result, str)
            assert len(result) > 0
        finally:
            reset_docdb_state()

    def test_doc_find_returns_list(self) -> None:
        """Finding documents should return a list."""
        reset_docdb_state()
        try:
            _doc_insert(["users", {"name": "Bob"}])
            results = _doc_find(["users", {}])
            assert isinstance(results, list)
            assert len(results) >= 1
        finally:
            reset_docdb_state()

    def test_doc_count_returns_integer(self) -> None:
        """Counting documents should return an integer."""
        reset_docdb_state()
        try:
            _doc_insert(["items", {"kind": "book"}])
            _doc_insert(["items", {"kind": "pen"}])
            count = _doc_count(["items"])
            expected_count = 2
            assert count == expected_count
        finally:
            reset_docdb_state()

    def test_docdb_plugin_registers_module(self) -> None:
        """The DocDBPlugin should register a 'docdb' stdlib module."""
        plugin = DocDBPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "doc_insert" in stdlib.functions
        assert "doc_find" in stdlib.functions
        assert "doc_count" in stdlib.functions


class TestGraphDBPlugin:
    """Verify PyGraphDB integration via the graphdb plugin."""

    def test_graph_add_node_returns_id(self) -> None:
        """Adding a node should return the node id."""
        reset_graphdb_state()
        try:
            result = _graph_add_node(["alice", "Person"])
            assert result == "alice"
        finally:
            reset_graphdb_state()

    def test_graph_add_edge_returns_id(self) -> None:
        """Adding an edge should return the edge id."""
        reset_graphdb_state()
        try:
            _graph_add_node(["alice", "Person"])
            _graph_add_node(["bob", "Person"])
            result = _graph_add_edge(["alice", "bob", "KNOWS"])
            assert isinstance(result, str)
            assert result.startswith("e")
        finally:
            reset_graphdb_state()

    def test_graph_shortest_path(self) -> None:
        """Finding shortest path between connected nodes should return the path."""
        reset_graphdb_state()
        try:
            _graph_add_node(["a", "Node"])
            _graph_add_node(["b", "Node"])
            _graph_add_node(["c", "Node"])
            _graph_add_edge(["a", "b", "LINK"])
            _graph_add_edge(["b", "c", "LINK"])
            path = _graph_shortest_path(["a", "c"])
            assert isinstance(path, list)
            assert "a" in path
            assert "c" in path
        finally:
            reset_graphdb_state()

    def test_graph_bfs_returns_visited(self) -> None:
        """BFS should return all reachable nodes."""
        reset_graphdb_state()
        try:
            _graph_add_node(["x", "Node"])
            _graph_add_node(["y", "Node"])
            _graph_add_edge(["x", "y", "LINK"])
            visited = _graph_bfs(["x"])
            assert isinstance(visited, list)
            assert "x" in visited
            assert "y" in visited
        finally:
            reset_graphdb_state()

    def test_graphdb_plugin_registers_module(self) -> None:
        """The GraphDBPlugin should register a 'graphdb' stdlib module."""
        plugin = GraphDBPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "graph_add_node" in stdlib.functions
        assert "graph_add_edge" in stdlib.functions
        assert "graph_shortest_path" in stdlib.functions
        assert "graph_bfs" in stdlib.functions


class TestTSDBPlugin:
    """Verify PyTSDB integration via the tsdb plugin."""

    def test_ts_add_returns_ok(self) -> None:
        """Adding a data point should return 'ok'."""
        reset_tsdb_state()
        try:
            result = _ts_add(["temperature", 72.5])
            assert result == "ok"
        finally:
            reset_tsdb_state()

    def test_ts_query_returns_values(self) -> None:
        """Querying a series should return a list of values."""
        reset_tsdb_state()
        try:
            _ts_add(["temp", 70.0])
            _ts_add(["temp", 75.0])
            values = _ts_query(["temp"])
            assert isinstance(values, list)
            expected_count = 2
            assert len(values) == expected_count
        finally:
            reset_tsdb_state()

    def test_tsdb_plugin_registers_module(self) -> None:
        """The TSDBPlugin should register a 'tsdb' stdlib module."""
        plugin = TSDBPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "ts_add" in stdlib.functions
        assert "ts_query" in stdlib.functions
        assert "ts_avg" in stdlib.functions


class TestVecDBPlugin:
    """Verify PyVecDB integration via the vecdb plugin."""

    def test_vec_insert_returns_id(self) -> None:
        """Inserting a vector should return the record id."""
        reset_vecdb_state()
        try:
            result = _vec_insert(["song1", [0.9, 0.1, 0.3]])
            assert result == "song1"
        finally:
            reset_vecdb_state()

    def test_vec_search_returns_results(self) -> None:
        """Searching should return a list of record ids."""
        reset_vecdb_state()
        try:
            _vec_insert(["a", [1.0, 0.0, 0.0]])
            _vec_insert(["b", [0.0, 1.0, 0.0]])
            results = _vec_search([[0.9, 0.1, 0.0], 1])
            assert isinstance(results, list)
            assert len(results) >= 1
            assert results[0] == "a"
        finally:
            reset_vecdb_state()

    def test_vec_cosine_returns_float(self) -> None:
        """Cosine similarity should return a float between -1 and 1."""
        result = _vec_cosine([[1.0, 0.0], [1.0, 0.0]])
        assert isinstance(result, float)
        assert abs(result - 1.0) < COSINE_TOLERANCE

    def test_vecdb_plugin_registers_module(self) -> None:
        """The VecDBPlugin should register a 'vecdb' stdlib module."""
        plugin = VecDBPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "vec_insert" in stdlib.functions
        assert "vec_search" in stdlib.functions
        assert "vec_cosine" in stdlib.functions


class TestColDBPlugin:
    """Verify PyColDB integration via the coldb plugin."""

    def test_col_set_and_get(self) -> None:
        """Setting and getting a column should return the value."""
        reset_coldb_state()
        try:
            result = _col_set(["grades", "alice", "math", "A+"])
            assert result == "ok"
            value = _col_get(["grades", "alice", "math"])
            assert value == "A+"
        finally:
            reset_coldb_state()

    def test_col_delete(self) -> None:
        """Deleting a column should make it unavailable."""
        reset_coldb_state()
        try:
            _col_set(["grades", "bob", "science", "B"])
            result = _col_delete(["grades", "bob", "science"])
            assert result == "ok"
            value = _col_get(["grades", "bob", "science"])
            assert value == "not found"
        finally:
            reset_coldb_state()

    def test_col_get_missing_returns_not_found(self) -> None:
        """Getting a nonexistent column should return 'not found'."""
        reset_coldb_state()
        try:
            result = _col_get(["missing", "row", "col"])
            assert result == "not found"
        finally:
            reset_coldb_state()

    def test_coldb_plugin_registers_module(self) -> None:
        """The ColDBPlugin should register a 'coldb' stdlib module."""
        plugin = ColDBPlugin()
        stdlib = plugin.pebble_stdlib()
        assert stdlib is not None
        assert "col_set" in stdlib.functions
        assert "col_get" in stdlib.functions
        assert "col_delete" in stdlib.functions


class TestKVShellCommands:
    """Verify KV plugin shell commands."""

    def test_kv_shell_set_and_get(self) -> None:
        """The kv-set and kv-get shell commands should work."""
        reset_kv_state()
        try:
            plugin = KVPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["kv-set"](["color", "blue"])
            assert "Set" in result
            result = cmds["kv-get"](["color"])
            assert result == "blue"
        finally:
            reset_kv_state()

    def test_kv_shell_delete(self) -> None:
        """The kv-delete shell command should remove a key."""
        reset_kv_state()
        try:
            plugin = KVPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            cmds["kv-set"](["temp", "val"])
            result = cmds["kv-delete"](["temp"])
            assert "Deleted" in result
        finally:
            reset_kv_state()

    def test_kv_shell_keys(self) -> None:
        """The kv-keys shell command should list keys."""
        reset_kv_state()
        try:
            plugin = KVPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["kv-keys"]([])
            assert result == "(no keys)"
            cmds["kv-set"](["x", "1"])
            result = cmds["kv-keys"]([])
            assert "x" in result
        finally:
            reset_kv_state()

    def test_kv_shell_usage(self) -> None:
        """Shell commands with missing args should show usage."""
        plugin = KVPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        assert "Usage" in cmds["kv-set"]([])
        assert "Usage" in cmds["kv-get"]([])
        assert "Usage" in cmds["kv-delete"]([])

    def test_kv_shell_delete_existing(self) -> None:
        """Deleting an existing key should return a Deleted message."""
        reset_kv_state()
        try:
            plugin = KVPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            cmds["kv-set"](["mykey", "myval"])
            result = cmds["kv-delete"](["mykey"])
            assert "Deleted" in result
        finally:
            reset_kv_state()

    def test_kv_shell_get_missing(self) -> None:
        """Getting a missing key should return not-found message."""
        reset_kv_state()
        try:
            plugin = KVPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["kv-get"](["no-such-key"])
            assert "not found" in result
        finally:
            reset_kv_state()


class TestDocDBShellCommands:
    """Verify DocDB plugin shell commands."""

    def test_doc_shell_insert_and_find(self) -> None:
        """The doc-insert and doc-find shell commands should work."""
        reset_docdb_state()
        try:
            plugin = DocDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["doc-insert"](["users", '{"name": "Alice"}'])
            assert "Inserted" in result
            result = cmds["doc-find"](["users"])
            assert "Alice" in result
        finally:
            reset_docdb_state()

    def test_doc_shell_count(self) -> None:
        """The doc-count shell command should return the count."""
        reset_docdb_state()
        try:
            plugin = DocDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            cmds["doc-insert"](["items", '{"kind": "pen"}'])
            result = cmds["doc-count"](["items"])
            assert result == "1"
        finally:
            reset_docdb_state()

    def test_doc_shell_insert_bad_json(self) -> None:
        """Inserting invalid JSON should return an error."""
        plugin = DocDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        result = cmds["doc-insert"](["users", "not-json"])
        assert "Error" in result

    def test_doc_shell_find_bad_json(self) -> None:
        """Finding with invalid JSON query should return an error."""
        plugin = DocDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        result = cmds["doc-find"](["users", "not-json"])
        assert "Error" in result

    def test_doc_shell_usage(self) -> None:
        """Shell commands with missing args should show usage."""
        plugin = DocDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        assert "Usage" in cmds["doc-insert"]([])
        assert "Usage" in cmds["doc-find"]([])
        assert "Usage" in cmds["doc-count"]([])

    def test_doc_shell_find_empty(self) -> None:
        """Finding in an empty collection should return no-documents message."""
        reset_docdb_state()
        try:
            plugin = DocDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["doc-find"](["empty"])
            assert "no documents" in result
        finally:
            reset_docdb_state()


class TestGraphDBShellCommands:
    """Verify GraphDB plugin shell commands."""

    def test_graph_shell_add_node_and_edge(self) -> None:
        """The graph shell commands should add nodes and edges."""
        reset_graphdb_state()
        try:
            plugin = GraphDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["graph"](["add-node", "alice", "Person"])
            assert "Added node" in result
            cmds["graph"](["add-node", "bob", "Person"])
            result = cmds["graph"](["add-edge", "alice", "bob", "KNOWS"])
            assert "Added edge" in result
        finally:
            reset_graphdb_state()

    def test_graph_shell_path(self) -> None:
        """The graph path shell command should find shortest paths."""
        reset_graphdb_state()
        try:
            plugin = GraphDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            cmds["graph"](["add-node", "a", "N"])
            cmds["graph"](["add-node", "b", "N"])
            cmds["graph"](["add-edge", "a", "b"])
            result = cmds["graph"](["path", "a", "b"])
            assert "a" in result
            assert "b" in result
        finally:
            reset_graphdb_state()

    def test_graph_shell_usage(self) -> None:
        """Shell command with no args should show usage."""
        plugin = GraphDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        assert "Usage" in cmds["graph"]([])
        assert "Usage" in cmds["graph"](["unknown"])


class TestTSDBShellCommands:
    """Verify TSDB plugin shell commands."""

    def test_ts_shell_add_and_query(self) -> None:
        """The ts-add and ts-query shell commands should work."""
        reset_tsdb_state()
        try:
            plugin = TSDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["ts-add"](["temp", "72.5"])
            assert "Added" in result
            result = cmds["ts-query"](["temp"])
            assert "72.5" in result
        finally:
            reset_tsdb_state()

    def test_ts_shell_avg(self) -> None:
        """The ts-avg shell command should compute averages."""
        reset_tsdb_state()
        try:
            plugin = TSDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            cmds["ts-add"](["temp", "70.0"])
            cmds["ts-add"](["temp", "80.0"])
            result = cmds["ts-avg"](["temp", "86400"])
            assert result != "(no data points)"
        finally:
            reset_tsdb_state()

    def test_ts_shell_usage(self) -> None:
        """Shell commands with missing args should show usage."""
        plugin = TSDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        assert "Usage" in cmds["ts-add"]([])
        assert "Usage" in cmds["ts-query"]([])
        assert "Usage" in cmds["ts-avg"]([])

    def test_ts_shell_query_empty(self) -> None:
        """Querying an empty series should return no-data message."""
        reset_tsdb_state()
        try:
            plugin = TSDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            db = _get_db()
            db.create_series("empty")
            result = cmds["ts-query"](["empty"])
            assert "no data" in result
        finally:
            reset_tsdb_state()

    def test_ts_shell_avg_empty(self) -> None:
        """Averaging an empty series should return no-data message."""
        reset_tsdb_state()
        try:
            plugin = TSDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            db = _get_db()
            db.create_series("empty")
            result = cmds["ts-avg"](["empty", "3600"])
            assert "no data" in result
        finally:
            reset_tsdb_state()


class TestVecDBShellCommands:
    """Verify VecDB plugin shell commands."""

    def test_vec_shell_insert_and_search(self) -> None:
        """The vec insert and search shell commands should work."""
        reset_vecdb_state()
        try:
            plugin = VecDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["vec"](["insert", "a", "1.0,0.0,0.0"])
            assert "Inserted" in result
            cmds["vec"](["insert", "b", "0.0,1.0,0.0"])
            result = cmds["vec"](["search", "0.9,0.1,0.0", "1"])
            assert "a" in result
        finally:
            reset_vecdb_state()

    def test_vec_shell_cosine(self) -> None:
        """The vec cosine shell command should compute similarity."""
        plugin = VecDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        result = cmds["vec"](["cosine", "1.0,0.0", "1.0,0.0"])
        assert "1.0" in result

    def test_vec_shell_usage(self) -> None:
        """Shell command with no args should show usage."""
        plugin = VecDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        assert "Usage" in cmds["vec"]([])
        assert "Usage" in cmds["vec"](["unknown"])


class TestColDBShellCommands:
    """Verify ColDB plugin shell commands."""

    def test_col_shell_set_and_get(self) -> None:
        """The col set and get shell commands should work."""
        reset_coldb_state()
        try:
            plugin = ColDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["col"](["set", "grades", "alice", "math", "A+"])
            assert "Set" in result
            result = cmds["col"](["get", "grades", "alice", "math"])
            assert result == "A+"
        finally:
            reset_coldb_state()

    def test_col_shell_get_missing(self) -> None:
        """Getting a missing column via shell should return Not found."""
        reset_coldb_state()
        try:
            plugin = ColDBPlugin()
            cmds = {c.name: c.handler for c in plugin.shell_commands()}
            result = cmds["col"](["get", "x", "y", "z"])
            assert "Not found" in result
        finally:
            reset_coldb_state()

    def test_col_shell_usage(self) -> None:
        """Shell command with no args should show usage."""
        plugin = ColDBPlugin()
        cmds = {c.name: c.handler for c in plugin.shell_commands()}
        assert "Usage" in cmds["col"]([])
        assert "Usage" in cmds["col"](["unknown"])


class TestEnvironmentRegistersNoSQLPlugins:
    """Verify that PyStackEnvironment auto-registers all NoSQL plugins on boot."""

    def test_nosql_modules_registered(self, tmp_path: Path) -> None:
        """All six NoSQL plugin modules should be registered after boot."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            expected_modules = ["kv", "docdb", "graphdb", "tsdb", "vecdb", "coldb"]
            for module_name in expected_modules:
                assert module_name in STDLIB_MODULES, f"{module_name} not registered"
        finally:
            env.shutdown()

    def test_all_plugins_in_registry(self, tmp_path: Path) -> None:
        """All twelve plugins should appear in the plugin registry."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            infos = env.plugin_registry.list_plugins()
            assert len(infos) >= TOTAL_PLUGIN_COUNT
            names = {info.name for info in infos}
            for expected in ("PyKV", "PyDocDB", "PyGraphDB", "PyTSDB", "PyVecDB", "PyColDB"):
                assert expected in names, f"{expected} not in registry"
        finally:
            env.shutdown()
