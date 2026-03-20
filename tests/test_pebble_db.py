"""Tests for the Pebble ↔ PyDB adapter.

The adapter lets Pebble programs query a PyDB database. These tests
verify that the bridge works correctly.
"""

from pathlib import Path

from pydb.database import Database
from pebble.stdlib import STDLIB_MODULES

from pystack.adapters.pebble_db import register_db_module, unregister_db_module
from pystack.environment import PyStackEnvironment


class TestRegisterModule:
    """Verify that the db module is registered in Pebble's stdlib."""

    def test_register_adds_module(self, tmp_path: Path) -> None:
        """Registering should add 'db' to STDLIB_MODULES."""
        db = Database(path=tmp_path)
        register_db_module(db)
        assert "db" in STDLIB_MODULES
        unregister_db_module()

    def test_unregister_removes_module(self, tmp_path: Path) -> None:
        """Unregistering should remove 'db' from STDLIB_MODULES."""
        db = Database(path=tmp_path)
        register_db_module(db)
        unregister_db_module()
        assert "db" not in STDLIB_MODULES

    def test_module_has_functions(self, tmp_path: Path) -> None:
        """The db module should expose db_query, db_execute, db_tables."""
        db = Database(path=tmp_path)
        register_db_module(db)
        module = STDLIB_MODULES["db"]
        assert "db_query" in module.functions
        assert "db_execute" in module.functions
        assert "db_tables" in module.functions
        unregister_db_module()


class TestPebbleDbIntegration:
    """Verify Pebble programs can query PyDB through the adapter."""

    def test_create_and_query(self, tmp_path: Path) -> None:
        """A Pebble program should create a table and query it."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = """
import "db"
db_execute("CREATE TABLE cards (name TEXT, power INTEGER)")
db_execute("INSERT INTO cards VALUES ('Pikachu', 55)")
db_execute("INSERT INTO cards VALUES ('Charmander', 52)")
let rows = db_query("SELECT name FROM cards ORDER BY name")
for row in rows {
    print(row["name"])
}
"""
            output = env.run_pebble_source(source)
            assert "Charmander" in output
            assert "Pikachu" in output
        finally:
            env.shutdown()

    def test_db_execute_returns_message(self, tmp_path: Path) -> None:
        """db_execute should return a status message."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = """
import "db"
let result = db_execute("CREATE TABLE t (val INTEGER)")
print(result)
"""
            output = env.run_pebble_source(source)
            assert "created" in output
        finally:
            env.shutdown()

    def test_db_tables(self, tmp_path: Path) -> None:
        """db_tables should return a list of table names."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = """
import "db"
db_execute("CREATE TABLE alpha (val INTEGER)")
db_execute("CREATE TABLE beta (val INTEGER)")
let tables = db_tables()
print(tables)
"""
            output = env.run_pebble_source(source)
            assert "alpha" in output
            assert "beta" in output
        finally:
            env.shutdown()

    def test_aggregation_query(self, tmp_path: Path) -> None:
        """Pebble should be able to run aggregate queries."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            source = """
import "db"
db_execute("CREATE TABLE scores (name TEXT, score INTEGER)")
db_execute("INSERT INTO scores VALUES ('Alice', 100)")
db_execute("INSERT INTO scores VALUES ('Bob', 200)")
db_execute("INSERT INTO scores VALUES ('Charlie', 150)")
let rows = db_query("SELECT COUNT(*) FROM scores")
print(rows[0]["COUNT(*)"])
"""
            output = env.run_pebble_source(source)
            assert "3" in output
        finally:
            env.shutdown()

    def test_data_persists_across_calls(self, tmp_path: Path) -> None:
        """Data created in one run should be queryable in the next."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            env.run_pebble_source("""
import "db"
db_execute("CREATE TABLE persist (val INTEGER)")
db_execute("INSERT INTO persist VALUES (42)")
""")
            env.save()
        finally:
            env.shutdown()

        # New environment, same db_path.
        env2 = PyStackEnvironment(db_path=tmp_path)
        try:
            output = env2.run_pebble_source("""
import "db"
let rows = db_query("SELECT val FROM persist")
print(rows[0]["val"])
""")
            assert "42" in output
        finally:
            env2.shutdown()


class TestEnvironment:
    """Verify the PyStackEnvironment lifecycle."""

    def test_run_sql(self, tmp_path: Path) -> None:
        """run_sql should execute SQL and return formatted output."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            env.run_sql("CREATE TABLE t (val INTEGER)")
            env.run_sql("INSERT INTO t VALUES (1)")
            result = env.run_sql("SELECT * FROM t")
            assert "1" in result
        finally:
            env.shutdown()

    def test_shutdown_saves_data(self, tmp_path: Path) -> None:
        """Shutdown should save the database."""
        env = PyStackEnvironment(db_path=tmp_path)
        env.run_sql("CREATE TABLE t (val INTEGER)")
        env.run_sql("INSERT INTO t VALUES (99)")
        env.shutdown()

        # Verify file was saved.
        assert (tmp_path / "t.json").exists()
