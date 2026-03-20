"""PyStack command-line interface.

Launch the integrated environment with Pebble + PyDB, run Pebble
programs that query databases, or start an interactive SQL session.
"""

import sys
from pathlib import Path

from pystack.environment import PyStackEnvironment


def main() -> None:
    """Entry point for the ``pystack`` command."""
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        _print_help()
        return

    command = args[0]

    match command:
        case "pebble":
            _run_pebble(args[1:])
        case "sql":
            _run_sql(args[1:])
        case _:
            # Treat as a .pbl file path.
            if command.endswith(".pbl"):
                _run_pebble([command])
            else:
                sys.stderr.write(f"Unknown command: {command}\n")
                _print_help()
                sys.exit(1)


def _print_help() -> None:
    """Print usage information."""
    sys.stdout.write(
        "PyStack -- the full stack, from scratch\n\n"
        "Usage:\n"
        "  pystack pebble <file.pbl>  Run a Pebble program with database access\n"
        "  pystack sql                Launch interactive SQL REPL\n"
        "  pystack <file.pbl>         Shortcut for pystack pebble <file.pbl>\n"
        "  pystack --help             Show this help\n"
    )


def _run_pebble(args: list[str]) -> None:
    """Run a Pebble program with database access."""
    if not args:
        sys.stderr.write("Usage: pystack pebble <file.pbl>\n")
        sys.exit(1)

    file_path = Path(args[0])
    if not file_path.exists():
        sys.stderr.write(f"Error: file not found: {file_path}\n")
        sys.exit(1)

    env = PyStackEnvironment()
    try:
        output = env.run_pebble_file(file_path)
        if output:
            sys.stdout.write(output)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"Error: {exc}\n")
        sys.exit(1)
    finally:
        env.shutdown()


def _run_sql(args: list[str]) -> None:
    """Launch an interactive SQL REPL with the integrated database."""
    env = PyStackEnvironment()
    try:
        from pydb.cli import repl

        repl(env.database)
    finally:
        env.shutdown()
