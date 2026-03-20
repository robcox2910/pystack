"""PyOS ↔ Pebble adapter.

Register a ``pebble`` command in the PyOS shell so users can run
Pebble programs from the OS command line. Programs run with full
database access via the ``db`` stdlib module.

Usage from the PyOS shell::

    pebble run /programs/hello.pbl
    pebble eval 'print(1 + 2)'
"""

from collections.abc import Callable

from py_os.kernel import Kernel
from py_os.shell import Shell
from py_os.syscalls import SyscallError, SyscallNumber

MIN_QUOTED_LENGTH = 2
PEBBLE_USAGE = "Usage: pebble run <file.pbl> | pebble eval '<code>'"


def _run_file(
    kernel: Kernel,
    run_source: Callable[[str], str],
    file_path: str,
) -> str:
    """Run a .pbl file from the PyOS filesystem."""
    try:
        data: bytes = kernel.syscall(SyscallNumber.SYS_READ_FILE, path=file_path)
    except SyscallError as exc:
        return f"Error: {exc}"
    try:
        return run_source(data.decode("utf-8")).rstrip("\n")
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"


def _eval_code(run_source: Callable[[str], str], source: str) -> str:
    """Evaluate a Pebble expression."""
    try:
        return run_source(source).rstrip("\n")
    except Exception as exc:  # noqa: BLE001
        return f"Error: {exc}"


def register_pebble_command(
    shell: Shell,
    kernel: Kernel,
    run_source: Callable[[str], str],
) -> None:
    """Register the ``pebble`` command in a PyOS shell.

    Args:
        shell: The PyOS shell to extend.
        kernel: The running kernel (for filesystem access).
        run_source: A callable that compiles and runs Pebble source code.

    """

    def handler(args: list[str]) -> str:
        if not args:
            return PEBBLE_USAGE
        subcommand = args[0]
        if subcommand == "run" and len(args) > 1:
            return _run_file(kernel, run_source, args[1])
        if subcommand == "eval" and len(args) > 1:
            source = " ".join(args[1:])
            # Remove matching outer quotes if present.
            if len(source) >= MIN_QUOTED_LENGTH and source[0] == source[-1] and source[0] in "'\"":
                source = source[1:-1]
            return _eval_code(run_source, source)
        return PEBBLE_USAGE

    shell._commands["pebble"] = handler  # noqa: SLF001


def register_sql_command(
    shell: Shell,
    run_sql: Callable[[str], str],
) -> None:
    """Register a ``sql`` command in the PyOS shell.

    Args:
        shell: The PyOS shell to extend.
        run_sql: A callable that executes SQL and returns formatted results.

    """

    def handler(args: list[str]) -> str:
        if not args:
            return "Usage: sql '<query>'"
        sql = " ".join(args)
        try:
            return run_sql(sql)
        except Exception as exc:  # noqa: BLE001
            return f"Error: {exc}"

    shell._commands["sql"] = handler  # noqa: SLF001
