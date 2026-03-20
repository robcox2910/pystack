"""PyDB ↔ PyOS filesystem adapter.

A storage engine that saves PyDB tables inside the PyOS virtual
filesystem instead of the real disk. This means database files live
alongside OS files in the simulated world.

Think of it like keeping your card binder inside the school building
(PyOS) instead of at home (the real filesystem).
"""

import contextlib

from py_os.kernel import Kernel
from py_os.syscalls import SyscallError, SyscallNumber
from pydb.record import Record
from pydb.schema import Schema
from pydb.serializer import SerializationError, deserialize_table_data, serialize_table_data
from pydb.storage import StorageError

TABLE_FILE_SUFFIX = ".json"
DEFAULT_DB_DIR = "/data"


class PyOSStorageEngine:
    """Store PyDB tables in the PyOS virtual filesystem.

    Implements the same interface as ``pydb.storage.StorageEngine``
    but delegates all I/O to PyOS kernel syscalls.

    Args:
        kernel: The running PyOS kernel.
        db_dir: Directory in the PyOS filesystem for table files.

    """

    __slots__ = ("_db_dir", "_kernel")

    def __init__(self, kernel: Kernel, db_dir: str = DEFAULT_DB_DIR) -> None:
        """Create a storage engine backed by the PyOS filesystem."""
        self._kernel = kernel
        self._db_dir = db_dir
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create the database directory if it doesn't exist."""
        with contextlib.suppress(SyscallError):
            self._kernel.syscall(SyscallNumber.SYS_CREATE_DIR, path=self._db_dir)

    def _table_path(self, table_name: str) -> str:
        """Return the virtual filesystem path for a table."""
        return f"{self._db_dir}/{table_name}{TABLE_FILE_SUFFIX}"

    @property
    def data_dir(self) -> str:
        """Return the database directory path."""
        return self._db_dir

    def save_table(
        self,
        name: str,
        schema: Schema,
        records: list[Record],
        next_id: int,
    ) -> None:
        """Save a table to the PyOS filesystem.

        Args:
            name: The table name.
            schema: The table's schema.
            records: All records in the table.
            next_id: The next auto-increment ID.

        Raises:
            StorageError: If the write fails.

        """
        json_str = serialize_table_data(name, schema, records, next_id)
        path = self._table_path(name)
        try:
            # Create file if it doesn't exist, then write.
            with contextlib.suppress(SyscallError):
                self._kernel.syscall(SyscallNumber.SYS_CREATE_FILE, path=path)
            self._kernel.syscall(
                SyscallNumber.SYS_WRITE_FILE,
                path=path,
                data=json_str.encode("utf-8"),
            )
        except SyscallError as exc:
            msg = f"Failed to save table {name!r}: {exc}"
            raise StorageError(msg) from exc

    def load_table(self, name: str) -> tuple[str, Schema, list[Record], int]:
        """Load a table from the PyOS filesystem.

        Args:
            name: The table name.

        Returns:
            A tuple of (name, schema, records, next_id).

        Raises:
            StorageError: If the file doesn't exist or is corrupted.

        """
        path = self._table_path(name)
        try:
            data: bytes = self._kernel.syscall(SyscallNumber.SYS_READ_FILE, path=path)
        except SyscallError as exc:
            msg = f"No data file for table {name!r} at {path}"
            raise StorageError(msg) from exc

        try:
            return deserialize_table_data(data.decode("utf-8"))
        except SerializationError as exc:
            msg = f"Corrupted data file for table {name!r}: {exc}"
            raise StorageError(msg) from exc

    def delete_table(self, name: str) -> None:
        """Remove a table's data file from the PyOS filesystem.

        Args:
            name: The table name.

        Raises:
            StorageError: If the file doesn't exist.

        """
        path = self._table_path(name)
        try:
            self._kernel.syscall(SyscallNumber.SYS_DELETE_FILE, path=path)
        except SyscallError as exc:
            msg = f"No data file for table {name!r} at {path}"
            raise StorageError(msg) from exc

    def table_exists(self, name: str) -> bool:
        """Check whether a data file exists for the given table name."""
        path = self._table_path(name)
        try:
            self._kernel.syscall(SyscallNumber.SYS_READ_FILE, path=path)
        except SyscallError:
            return False
        return True

    def list_tables(self) -> list[str]:
        """Return the names of all tables in the PyOS filesystem."""
        try:
            entries: list[str] = self._kernel.syscall(
                SyscallNumber.SYS_LIST_DIR,
                path=self._db_dir,
            )
        except SyscallError:
            return []
        return sorted(
            entry.removesuffix(TABLE_FILE_SUFFIX)
            for entry in entries
            if entry.endswith(TABLE_FILE_SUFFIX)
        )
