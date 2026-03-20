"""Tests for the full PyOS + Pebble + PyDB integration.

These tests boot a PyOS kernel, register the Pebble and SQL commands,
and verify the full integrated stack works end-to-end.
"""

from pathlib import Path

import pytest
from py_os.kernel import Kernel
from py_os.syscalls import SyscallNumber
from pydb.record import Record
from pydb.schema import Column, Schema
from pydb.types import DataType

from pystack.adapters.db_storage import PyOSStorageEngine
from pystack.environment import PyStackEnvironment

NEXT_ID_2 = 2
ONE_RECORD = 1


class TestOSPebbleIntegration:
    """Verify Pebble programs run from the PyOS shell."""

    def test_pebble_eval_from_shell(self, tmp_path: Path) -> None:
        """The pebble eval command should run Pebble code."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            output = env.execute_shell("pebble eval 'print(1 + 2)'")
            assert "3" in output
        finally:
            env.shutdown()

    def test_pebble_run_from_shell(self, tmp_path: Path) -> None:
        """The pebble run command should execute a .pbl file from PyOS fs."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            kernel = env.kernel
            assert isinstance(kernel, Kernel)
            kernel.syscall(SyscallNumber.SYS_CREATE_DIR, path="/programs")
            kernel.syscall(SyscallNumber.SYS_CREATE_FILE, path="/programs/hello.pbl")
            kernel.syscall(
                SyscallNumber.SYS_WRITE_FILE,
                path="/programs/hello.pbl",
                data=b'print("Hello from PyOS!")',
            )
            output = env.execute_shell("pebble run /programs/hello.pbl")
            assert "Hello from PyOS!" in output
        finally:
            env.shutdown()

    def test_pebble_db_from_shell(self, tmp_path: Path) -> None:
        """A Pebble program run from the shell should have DB access."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            kernel = env.kernel
            assert isinstance(kernel, Kernel)
            source = (
                'import "db"\n'
                'db_execute("CREATE TABLE t (val INTEGER)")\n'
                'db_execute("INSERT INTO t VALUES (42)")\n'
                'let rows = db_query("SELECT val FROM t")\n'
                'print(rows[0]["val"])'
            )
            kernel.syscall(SyscallNumber.SYS_CREATE_DIR, path="/programs")
            kernel.syscall(SyscallNumber.SYS_CREATE_FILE, path="/programs/db_test.pbl")
            kernel.syscall(
                SyscallNumber.SYS_WRITE_FILE,
                path="/programs/db_test.pbl",
                data=source.encode("utf-8"),
            )
            output = env.execute_shell("pebble run /programs/db_test.pbl")
            assert "42" in output
        finally:
            env.shutdown()

    def test_sql_from_shell(self, tmp_path: Path) -> None:
        """The sql command should execute SQL directly from the shell."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            env.execute_shell("sql CREATE TABLE scores (player TEXT, score INTEGER)")
            env.execute_shell("sql INSERT INTO scores VALUES ('Alice', 100)")
            output = env.execute_shell("sql SELECT * FROM scores")
            assert "Alice" in output
        finally:
            env.shutdown()

    def test_pebble_usage_message(self, tmp_path: Path) -> None:
        """The pebble command with no args should show usage."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            output = env.execute_shell("pebble")
            assert "Usage" in output
        finally:
            env.shutdown()


class TestPyOSStorageEngine:
    """Verify the PyDB storage engine that uses the PyOS filesystem."""

    def test_save_and_load(self) -> None:
        """Tables should survive save → load through PyOS fs."""
        kernel = Kernel()
        kernel.boot()
        try:
            engine = PyOSStorageEngine(kernel=kernel)
            schema = Schema(
                columns=[
                    Column(name="name", data_type=DataType.TEXT),
                    Column(name="power", data_type=DataType.INTEGER),
                ]
            )
            records = [Record(record_id=1, data={"name": "Pikachu", "power": 55})]
            engine.save_table("cards", schema, records, next_id=NEXT_ID_2)

            name, loaded_schema, loaded_records, next_id = engine.load_table("cards")
            assert name == "cards"
            assert loaded_schema.column_names == ["name", "power"]
            assert len(loaded_records) == ONE_RECORD
            assert loaded_records[0]["name"] == "Pikachu"
            assert next_id == NEXT_ID_2
        finally:
            kernel.shutdown()

    def test_list_tables(self) -> None:
        """list_tables should return saved table names."""
        kernel = Kernel()
        kernel.boot()
        try:
            engine = PyOSStorageEngine(kernel=kernel)
            schema = Schema(columns=[Column(name="val", data_type=DataType.INTEGER)])
            engine.save_table("alpha", schema, [], next_id=1)
            engine.save_table("beta", schema, [], next_id=1)
            assert engine.list_tables() == ["alpha", "beta"]
        finally:
            kernel.shutdown()

    def test_delete_table(self) -> None:
        """delete_table should remove the file."""
        kernel = Kernel()
        kernel.boot()
        try:
            engine = PyOSStorageEngine(kernel=kernel)
            schema = Schema(columns=[Column(name="val", data_type=DataType.INTEGER)])
            engine.save_table("cards", schema, [], next_id=1)
            engine.delete_table("cards")
            assert not engine.table_exists("cards")
        finally:
            kernel.shutdown()

    def test_table_exists(self) -> None:
        """table_exists should return True for saved tables."""
        kernel = Kernel()
        kernel.boot()
        try:
            engine = PyOSStorageEngine(kernel=kernel)
            schema = Schema(columns=[Column(name="val", data_type=DataType.INTEGER)])
            assert not engine.table_exists("cards")
            engine.save_table("cards", schema, [], next_id=1)
            assert engine.table_exists("cards")
        finally:
            kernel.shutdown()


class TestEnvironmentOSMode:
    """Verify the environment in OS mode."""

    def test_os_mode_has_kernel(self, tmp_path: Path) -> None:
        """OS mode should create a kernel."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            assert env.kernel is not None
            assert env.shell is not None
        finally:
            env.shutdown()

    def test_non_os_mode_no_kernel(self, tmp_path: Path) -> None:
        """Non-OS mode should not create a kernel."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            assert env.kernel is None
            assert env.shell is None
        finally:
            env.shutdown()

    def test_execute_shell_without_os_raises(self, tmp_path: Path) -> None:
        """execute_shell without OS mode should raise."""
        env = PyStackEnvironment(db_path=tmp_path)
        try:
            with pytest.raises(RuntimeError, match="Not in OS mode"):
                env.execute_shell("ls /")
        finally:
            env.shutdown()

    def test_ls_works(self, tmp_path: Path) -> None:
        """Standard PyOS commands should still work."""
        env = PyStackEnvironment(db_path=tmp_path, os_mode=True)
        try:
            output = env.execute_shell("ls /")
            assert output
        finally:
            env.shutdown()
