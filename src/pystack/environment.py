"""PyStack environment -- boot and wire everything together.

The environment is the control room. It creates a database, registers
the Pebble adapter, and provides a ready-to-use integrated runtime.
"""

from pathlib import Path

from pydb.database import Database

from pystack.adapters.pebble_db import register_db_module, unregister_db_module


class PyStackEnvironment:
    """Manage the lifecycle of an integrated PyStack session.

    Creates a PyDB database and registers the Pebble ``db`` stdlib
    module so Pebble programs can query the database.

    Args:
        db_path: Directory for PyDB data files.

    """

    __slots__ = ("_database", "_db_path")

    def __init__(self, db_path: str | Path = "pystack_data") -> None:
        """Create and boot the integrated environment."""
        self._db_path = Path(db_path)
        self._database = Database(path=self._db_path)
        self._database.load()
        register_db_module(self._database)

    @property
    def database(self) -> Database:
        """Return the PyDB database instance."""
        return self._database

    def save(self) -> None:
        """Save the database to disk."""
        self._database.save()

    def shutdown(self) -> None:
        """Clean up resources and unregister adapters."""
        self._database.save()
        unregister_db_module()

    def run_pebble_source(self, source: str, filename: str = "<stdin>") -> str:
        """Compile and run a Pebble source string with database access.

        Args:
            source: The Pebble source code.
            filename: The filename for error reporting.

        Returns:
            The captured stdout output from the program.

        """
        import io

        from pebble.analyzer import SemanticAnalyzer
        from pebble.bytecode import CompiledProgram
        from pebble.compiler import Compiler
        from pebble.errors import PebbleError
        from pebble.lexer import Lexer
        from pebble.optimizer import optimize
        from pebble.parser import Parser
        from pebble.resolver import ModuleResolver
        from pebble.type_checker import type_check
        from pebble.vm import VirtualMachine

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
        all_functions = {**resolver.merged_functions, **compiled.functions}
        all_structs = {**resolver.merged_structs, **compiled.structs}
        all_struct_field_types = {
            **resolver.merged_struct_field_types,
            **compiled.struct_field_types,
        }
        all_class_methods = {**resolver.merged_class_methods, **compiled.class_methods}
        all_enums = {**resolver.merged_enums, **compiled.enums}
        all_class_parents = {**resolver.merged_class_parents, **compiled.class_parents}
        full_program = CompiledProgram(
            main=compiled.main,
            functions=all_functions,
            structs=all_structs,
            struct_field_types=all_struct_field_types,
            class_methods=all_class_methods,
            enums=all_enums,
            class_parents=all_class_parents,
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
        return self.run_pebble_source(source, filename=str(path))

    def run_sql(self, sql: str) -> str:
        """Execute a SQL statement and return formatted results.

        Args:
            sql: The SQL text.

        Returns:
            Formatted result string.

        """
        from pydb.executor import execute
        from pydb.formatter import format_results
        from pydb.query import Query
        from pydb.sql_parser import parse_sql

        parsed = parse_sql(sql)
        results = execute(parsed, self._database)
        columns = parsed.columns if isinstance(parsed, Query) and parsed.columns else None
        return format_results(results, columns=columns)
