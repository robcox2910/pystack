"""PyStack environment -- boot and wire everything together.

The environment is the control room. It creates a database, registers
the Pebble adapter, and provides a ready-to-use integrated runtime.
"""

import contextlib
import io
from pathlib import Path

from pebble.analyzer import SemanticAnalyzer
from pebble.bytecode import CompiledProgram
from pebble.compiler import Compiler
from pebble.lexer import Lexer
from pebble.optimizer import optimize
from pebble.parser import Parser
from pebble.resolver import ModuleResolver
from pebble.type_checker import type_check
from pebble.vm import VirtualMachine
from py_os.kernel import Kernel
from py_os.shell import Shell
from pydb.database import Database
from pydb.executor import execute
from pydb.formatter import format_results
from pydb.query import Query
from pydb.sql_parser import parse_sql

from pystack.adapters.os_pebble import register_pebble_command, register_sql_command
from pystack.adapters.pebble_db import register_db_module, unregister_db_module
from pystack.plugins.registry import PluginRegistry


class PyStackEnvironment:
    """Manage the lifecycle of an integrated PyStack session.

    Creates a PyDB database and registers the Pebble ``db`` stdlib
    module so Pebble programs can query the database.

    In OS mode, also boots a PyOS kernel and shell with integrated
    ``pebble`` and ``sql`` commands.

    Args:
        db_path: Directory for PyDB data files.
        os_mode: If True, boot a PyOS kernel and register shell commands.

    """

    __slots__ = ("_database", "_db_path", "_kernel", "_os_mode", "_plugin_registry", "_shell")

    def __init__(
        self,
        db_path: str | Path = "pystack_data",
        *,
        os_mode: bool = False,
    ) -> None:
        """Create and boot the integrated environment."""
        self._db_path = Path(db_path)
        self._os_mode = os_mode
        self._kernel: Kernel | None = None
        self._shell: Shell | None = None
        self._plugin_registry = PluginRegistry()

        self._database = Database(path=self._db_path)
        self._database.load()
        register_db_module(self._database)

        if os_mode:
            self._boot_os()

    def _boot_os(self) -> None:
        """Boot the PyOS kernel and register integrated shell commands."""
        kernel = Kernel()
        kernel.boot()
        shell = Shell(kernel=kernel)

        register_pebble_command(shell, kernel, self.run_pebble_source)
        register_sql_command(shell, self.run_sql)

        # Discover and activate any installed plugins.
        self._plugin_registry.discover()
        self._plugin_registry.activate_all(shell=shell)

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
        """Save the database to disk."""
        self._database.save()

    def shutdown(self) -> None:
        """Clean up resources and unregister adapters. Safe to call multiple times."""
        with contextlib.suppress(Exception):
            self._database.save()
        unregister_db_module()
        if self._kernel is not None:
            with contextlib.suppress(Exception):
                self._kernel.shutdown()
            self._kernel = None

    def run_pebble_source(self, source: str) -> str:
        """Compile and run a Pebble source string with database access.

        Args:
            source: The Pebble source code.

        Returns:
            The captured stdout output from the program.

        """
        output = io.StringIO()
        tokens = Lexer(source).tokenize()
        program = Parser(tokens).parse()
        analyzer = SemanticAnalyzer()
        resolver = ModuleResolver(base_dir=Path.cwd())
        resolver.resolve_imports(program, analyzer)
        analyzed = analyzer.analyze(program)
        type_check(analyzed, analyzer=analyzer)
        compiled = Compiler(
            cell_vars=analyzer.cell_vars,
            free_vars=analyzer.free_vars,
            enums=resolver.merged_enums,
            class_parents=resolver.merged_class_parents,
            structs=resolver.merged_structs,
            class_methods=resolver.merged_class_methods,
            functions=resolver.merged_functions,
            variable_arity_functions=resolver.variable_arity_functions,
        ).compile(analyzed)
        compiled = optimize(compiled)
        full_program = CompiledProgram(
            main=compiled.main,
            functions={**resolver.merged_functions, **compiled.functions},
            structs={**resolver.merged_structs, **compiled.structs},
            struct_field_types={
                **resolver.merged_struct_field_types,
                **compiled.struct_field_types,
            },
            class_methods={**resolver.merged_class_methods, **compiled.class_methods},
            enums={**resolver.merged_enums, **compiled.enums},
            class_parents={**resolver.merged_class_parents, **compiled.class_parents},
        )
        VirtualMachine(output=output).run(
            full_program,
            stdlib_handlers=resolver.merged_stdlib_handlers,
            stdlib_constants=resolver.merged_stdlib_constants,
        )
        return output.getvalue()

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
