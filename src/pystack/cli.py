"""PyStack command-line interface.

Launch the integrated environment with Pebble + PyDB, run Pebble
programs that query databases, or start an interactive SQL session.
"""

import sys
from pathlib import Path

from py_os.shell import Shell
from pydb.cli import repl

from pystack.environment import PyStackEnvironment
from pystack.web.app import main as web_main


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
            _run_sql()
        case "os":
            _run_os()
        case "web":
            web_main()
        case _:
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
        "  pystack os                 Launch PyOS shell with Pebble + DB integration\n"
        "  pystack web                Launch browser UI at http://localhost:8080\n"
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


def _run_sql() -> None:
    """Launch an interactive SQL REPL with the integrated database."""
    env = PyStackEnvironment()
    try:
        repl(env.database)
    finally:
        env.shutdown()


def _run_os() -> None:
    """Launch the PyOS shell with Pebble and SQL integration."""
    env = PyStackEnvironment(os_mode=True)
    sys.stdout.write("PyStack OS -- type 'help' for commands, 'pebble' or 'sql' for integrations\n")
    shell = env.shell
    assert isinstance(shell, Shell)  # noqa: S101
    try:
        while True:
            try:
                line = input("pystack-os> ").strip()
            except EOFError, KeyboardInterrupt:
                sys.stdout.write("\nGoodbye!\n")
                break
            if not line:
                continue
            output = shell.execute(line)
            if output == Shell.EXIT_SENTINEL:
                break
            if output:
                sys.stdout.write(output + "\n")
    finally:
        env.shutdown()
