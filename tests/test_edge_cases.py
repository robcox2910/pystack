"""Edge case tests for PyStack.

Cover error paths, missing files, invalid input, and boundary
conditions identified during code review.
"""

from pathlib import Path

import pytest
from py_os.kernel import Kernel
from pydb.storage import StorageError

from pystack.adapters.db_storage import PyOSStorageEngine
from pystack.environment import PyStackEnvironment


class TestPebbleErrorPaths:
    """Verify error handling for Pebble commands."""

    def test_pebble_run_missing_file(self, tmp_path: Path) -> None:
        """Running a missing .pbl file should return an error."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            output = env.execute_shell("pebble run /nonexistent.pbl")
            assert "Error" in output
        finally:
            env.shutdown()

    def test_pebble_eval_invalid_code(self, tmp_path: Path) -> None:
        """Evaluating invalid Pebble code should return an error."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            output = env.execute_shell("pebble eval 'let x = ???'")
            assert "Error" in output
        finally:
            env.shutdown()


class TestSQLErrorPaths:
    """Verify error handling for SQL commands."""

    def test_sql_invalid_query(self, tmp_path: Path) -> None:
        """Invalid SQL should return an error, not crash."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            output = env.execute_shell("sql INVALID GIBBERISH")
            assert "Error" in output
        finally:
            env.shutdown()


class TestStorageErrorPaths:
    """Verify PyOS storage engine error handling."""

    def test_load_nonexistent_table(self) -> None:
        """Loading a table that doesn't exist should raise StorageError."""
        kernel = Kernel()
        kernel.boot()
        try:
            engine = PyOSStorageEngine(kernel=kernel)
            with pytest.raises(StorageError, match="No data file"):
                engine.load_table("nonexistent")
        finally:
            kernel.shutdown()

    def test_delete_nonexistent_table(self) -> None:
        """Deleting a table that doesn't exist should raise StorageError."""
        kernel = Kernel()
        kernel.boot()
        try:
            engine = PyOSStorageEngine(kernel=kernel)
            with pytest.raises(StorageError, match="No data file"):
                engine.delete_table("nonexistent")
        finally:
            kernel.shutdown()


class TestShutdownIdempotent:
    """Verify shutdown can be called multiple times safely."""

    def test_double_shutdown(self, tmp_path: Path) -> None:
        """Calling shutdown twice should not crash."""
        env = PyStackEnvironment(db_path=tmp_path)
        env.shutdown()
        env.shutdown()  # Should not raise.

    def test_double_shutdown_os_mode(self, tmp_path: Path) -> None:
        """Calling shutdown twice in OS mode should not crash."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        env.shutdown()
        env.shutdown()  # Should not raise.
