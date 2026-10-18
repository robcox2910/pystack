"""PyStack environment -- boot and wire everything together.

The environment is the control room. It creates a database, registers
the Pebble adapter, and provides a ready-to-use integrated runtime.
"""

import contextlib
import sys
from pathlib import Path

from pebble import run_source
from py_os.kernel import Kernel
from py_os.shell import Shell
from pydb.database import Database
from pydb.executor import execute
from pydb.formatter import format_results
from pydb.query import Query
from pydb.sql_parser import parse_sql

from pystack.adapters.os_pebble import (
    register_pebble_command,
    register_save_command,
    register_sql_command,
)
from pystack.adapters.pebble_db import make_db_module
from pystack.plugins.base import Plugin
from pystack.plugins.coldb_plugin import ColDBPlugin
from pystack.plugins.crypto_plugin import CryptoPlugin
from pystack.plugins.docdb_plugin import DocDBPlugin
from pystack.plugins.git_plugin import GitPlugin
from pystack.plugins.graphdb_plugin import GraphDBPlugin
from pystack.plugins.kv_plugin import KVPlugin
from pystack.plugins.llm_plugin import LLMPlugin
from pystack.plugins.mq_plugin import MQPlugin
from pystack.plugins.net_plugin import NetPlugin
from pystack.plugins.pydb_plugin import PyDBPlugin
from pystack.plugins.registry import PluginRegistry
from pystack.plugins.sched_plugin import PySchedulerPlugin
from pystack.plugins.search_plugin import SearchPlugin
from pystack.plugins.tsdb_plugin import TSDBPlugin
from pystack.plugins.vecdb_plugin import VecDBPlugin
from pystack.plugins.web_plugin import WebPlugin


class PyStackEnvironment:
    """Manage the lifecycle of an integrated PyStack session.

    Creates a PyDB database and runs Pebble programs through Pebble's
    public API, handing each run this environment's own ``db`` module and
    plugin modules (nothing is shared between environments).

    In OS mode, also boots a PyOS kernel and shell with integrated
    ``pebble`` and ``sql`` commands.

    Args:
        db_path: Directory for PyDB data files.
        os_mode: If True, boot a PyOS kernel and register shell commands.

    """

    __slots__ = (
        "_closed",
        "_database",
        "_db_module",
        "_db_path",
        "_kernel",
        "_os_mode",
        "_plugin_registry",
        "_shell",
    )

    def __init__(
        self,
        db_path: str | Path = "pystack_data",
        *,
        os_mode: bool = False,
    ) -> None:
        """Create and boot the integrated environment."""
        self._db_path = Path(db_path)
        self._closed = False
        self._os_mode = os_mode
        self._kernel: Kernel | None = None
        self._shell: Shell | None = None
        self._plugin_registry = PluginRegistry()

        self._database = Database(path=self._db_path)
        self._database.load()
        # This environment's own ``db`` module; it is only placed on Pebble's
        # shared module shelf while one of *our* programs runs.
        self._db_module = make_db_module(self._database)
        self._register_all_plugins()

        if os_mode:
            self._boot_os()

        # Activate every plugin exactly once, in every mode. Passing the
        # shell (which is None outside OS mode) means plugin Pebble modules
        # and on_boot() hooks always run, while shell commands are only
        # registered when there is a shell to register them in.
        self._plugin_registry.activate_all(shell=self._shell, data_dir=self._db_path)

    def _register_all_plugins(self) -> None:
        """Register all built-in integration plugins with the registry.

        Add the crypto, web, git, net, search, mq, kv, docdb, graphdb,
        tsdb, vecdb, coldb, llm, and sched plugins so the registry can wire their
        Pebble modules, shell commands, and boot hooks during activation.
        """
        plugins: list[Plugin] = [
            CryptoPlugin(),
            WebPlugin(),
            GitPlugin(),
            NetPlugin(),
            SearchPlugin(),
            MQPlugin(),
            PyDBPlugin(),
            PySchedulerPlugin(),
            KVPlugin(),
            DocDBPlugin(),
            GraphDBPlugin(),
            TSDBPlugin(),
            VecDBPlugin(),
            ColDBPlugin(),
            LLMPlugin(),
        ]
        for plugin in plugins:
            self._plugin_registry.register(plugin)

    def _boot_os(self) -> None:
        """Boot the PyOS kernel and register the pebble and sql shell commands."""
        kernel = Kernel()
        kernel.boot()
        shell = Shell(kernel=kernel)

        register_pebble_command(shell, kernel, self.run_pebble_source)
        register_sql_command(shell, self.run_sql)
        register_save_command(shell, self.save)

        # Discover any third-party plugins installed via entry points so
        # they are activated alongside the built-ins.
        self._plugin_registry.discover()

        self._kernel = kernel
        self._shell = shell

    @property
    def plugin_registry(self) -> PluginRegistry:
        """Return the plugin registry."""
        return self._plugin_registry

    @property
    def database(self) -> Database:
        """Return the PyDB database instance."""
        return self._database

    @property
    def kernel(self) -> Kernel | None:
        """Return the PyOS kernel, or None if not in OS mode."""
        return self._kernel

    @property
    def shell(self) -> Shell | None:
        """Return the PyOS shell, or None if not in OS mode."""
        return self._shell

    def execute_shell(self, command: str) -> str:
        """Execute a command in the PyOS shell.

        Args:
            command: The shell command to execute.

        Returns:
            The command output.

        Raises:
            RuntimeError: If not in OS mode.

        """
        if self._shell is None:
            msg = "Not in OS mode -- call PyStackEnvironment(os_mode=True)"
            raise RuntimeError(msg)
        return self._shell.execute(command)

    def save(self) -> None:
        """Save the database and every plugin's data.

        Every part is tried even if an earlier one fails.

        Raises:
            ExceptionGroup: If anything couldn't be saved, after trying
                everything.

        """
        failures = self._save_everything()
        if failures:
            names = ", ".join(name for name, _ in failures)
            msg = f"pystack could not save {names}"
            raise ExceptionGroup(msg, [exc for _, exc in failures])

    def shutdown(self) -> None:
        """Save everything, shut plugins down and stop the OS kernel.

        Never raises -- it runs in ``finally:`` blocks, where an error would
        hide the real one -- but prints one line per failure to stderr.
        Safe to call more than once; later calls do nothing.
        """
        if self._closed:
            return
        self._closed = True
        for name, exc in self._save_everything():
            sys.stderr.write(f"pystack: could not save {name}: {exc}\n")
        for name, exc in self._plugin_registry.shutdown_all():
            sys.stderr.write(f"pystack: could not shut down {name}: {exc}\n")
        if self._kernel is not None:
            with contextlib.suppress(Exception):
                self._kernel.shutdown()
            self._kernel = None

    def _save_everything(self) -> list[tuple[str, Exception]]:
        """Save the database and every plugin, returning what failed."""
        failures: list[tuple[str, Exception]] = []
        try:
            self._database.save()
        except Exception as exc:  # noqa: BLE001 -- reported by save()/shutdown()
            failures.append(("database", exc))
        failures.extend(self._plugin_registry.save_all(self._db_path))
        return failures

    def run_pebble_source(self, source: str) -> str:
        """Compile and run a Pebble source string with database access.

        Args:
            source: The Pebble source code.

        Returns:
            The captured stdout output from the program.

        """
        modules = {"db": self._db_module, **self._plugin_registry.pebble_modules()}
        return run_source(source, modules=modules, base_dir=Path.cwd())

    def run_pebble_file(self, file_path: str | Path) -> str:
        """Compile and run a Pebble file with database access.

        Args:
            file_path: Path to the .pbl file.

        Returns:
            The captured stdout output.

        Raises:
            FileNotFoundError: If the file doesn't exist.

        """
        path = Path(file_path)
        source = path.read_text(encoding="utf-8")
        return self.run_pebble_source(source)

    def run_sql(self, sql: str) -> str:
        """Execute a SQL statement and return formatted results.

        Args:
            sql: The SQL text.

        Returns:
            Formatted result string.

        """
        parsed = parse_sql(sql)
        results = execute(parsed, self._database)
        columns = parsed.columns if isinstance(parsed, Query) and parsed.columns else None
        return format_results(results, columns=columns)
