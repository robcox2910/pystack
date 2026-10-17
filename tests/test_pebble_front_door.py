"""Tests that PyStack runs Pebble only through Pebble's public front door.

Each environment hands Pebble its own modules for each run, so two
environments never see each other's database, and Pebble's shared table
of built-in modules is never touched.
"""

import re
from pathlib import Path

from pebble.stdlib import STDLIB_MODULES

from pystack.environment import PyStackEnvironment

SRC = Path(__file__).parent.parent / "src" / "pystack"
DEEP_IMPORT = re.compile(r"^\s*(from pebble\.|import pebble\.)", re.MULTILINE)


class TestFrontDoor:
    """PyStack environments use per-run Pebble modules, never the shared table."""

    def test_two_environments_have_separate_db_modules(self, tmp_path: Path) -> None:
        """A table made through Pebble in one environment is invisible to another."""
        first = PyStackEnvironment(db_path=tmp_path / "first")
        second = PyStackEnvironment(db_path=tmp_path / "second")
        try:
            first.run_pebble_source('import "db"\ndb_execute("CREATE TABLE only_here (x INTEGER)")')
            output = second.run_pebble_source('import "db"\nprint(db_tables())')
            assert "only_here" not in output
        finally:
            first.shutdown()
            second.shutdown()

    def test_running_pebble_leaves_pebbles_shared_table_alone(self, tmp_path: Path) -> None:
        """Booting an environment and running a program changes nothing shared."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            env.run_pebble_source('import "db"\nimport "kv"\nkv_set("a", "b")\nprint(db_tables())')
            leaked = set(STDLIB_MODULES) & {"db", *env.plugin_registry.pebble_modules()}
            assert leaked == set()
        finally:
            env.shutdown()

    def test_pystack_imports_only_pebbles_public_api(self) -> None:
        """No PyStack module reaches into Pebble's internals."""
        offenders = [
            path.relative_to(SRC).as_posix()
            for path in sorted(SRC.rglob("*.py"))
            if DEEP_IMPORT.search(path.read_text(encoding="utf-8"))
        ]
        assert offenders == []
