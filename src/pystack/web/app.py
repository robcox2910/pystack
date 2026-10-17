"""Flask application for the PyStack web UI.

Provide a browser-based interface with three panels:
- OS Terminal: run PyOS shell commands
- Pebble Editor: write and run Pebble programs
- SQL Console: execute SQL queries

All three share the same integrated environment.
"""

import atexit
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request
from py_os.kernel import KernelState
from py_os.shell import Shell

from pystack.environment import PyStackEnvironment

_HTTP_BAD_REQUEST = 400


def create_app(data_dir: str | Path = "pystack_data") -> Flask:
    """Create the PyStack web application.

    Boot the integrated environment (kernel + database + Pebble) and
    wire up the API endpoints.

    Args:
        data_dir: Where the database and plugin data are kept.

    Returns:
        A configured Flask application. Its environment is in
        ``app.extensions["pystack_env"]``, so whoever runs the app can
        shut it down (which saves everything).

    """
    env = PyStackEnvironment(db_path=data_dir, os_mode=True)

    shell = env.shell
    kernel = env.kernel
    if not isinstance(shell, Shell):
        msg = "Shell not available -- OS mode failed to boot"
        raise TypeError(msg)

    boot_log = "\n".join(kernel.dmesg()) if kernel else ""

    app = Flask(__name__)
    app.extensions["pystack_env"] = env

    @app.route("/")
    def index() -> str:  # pyright: ignore[reportUnusedFunction]
        """Render the main page."""
        return render_template("index.html", boot_log=boot_log)

    @app.route("/api/shell", methods=["POST"])
    def api_shell() -> tuple[Response, int] | Response:  # pyright: ignore[reportUnusedFunction]
        """Execute a PyOS shell command.

        Body: ``{"command": "ls /"}``

        """
        data = request.get_json(silent=True)
        if data is None or "command" not in data:
            return jsonify({"error": "Missing 'command' field"}), _HTTP_BAD_REQUEST

        if kernel and kernel.state is not KernelState.RUNNING:
            return jsonify({"output": "System halted.", "halted": True})

        command: str = data["command"]
        result = shell.execute(command)
        halted = result == Shell.EXIT_SENTINEL
        if not halted:
            return jsonify({"output": result, "halted": False})
        # Save now, but leave the environment open: the Pebble and SQL panels
        # still work after ``exit``, and stopping the server saves those too.
        message = "System halted."
        try:
            env.save()
        except ExceptionGroup as exc:
            message += f" Warning: {exc}"
        if kernel and kernel.state is KernelState.RUNNING:
            kernel.shutdown()
        return jsonify({"output": message, "halted": True})

    @app.route("/api/pebble", methods=["POST"])
    def api_pebble() -> tuple[Response, int] | Response:  # pyright: ignore[reportUnusedFunction]
        """Execute Pebble source code.

        Body: ``{"source": "print(1 + 2)"}``

        """
        data = request.get_json(silent=True)
        if data is None or "source" not in data:
            return jsonify({"error": "Missing 'source' field"}), _HTTP_BAD_REQUEST

        source: str = data["source"]
        try:
            output = env.run_pebble_source(source)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"output": f"Error: {exc}", "error": True})
        return jsonify({"output": output, "error": False})

    @app.route("/api/sql", methods=["POST"])
    def api_sql() -> tuple[Response, int] | Response:  # pyright: ignore[reportUnusedFunction]
        """Execute a SQL statement.

        Body: ``{"sql": "SELECT * FROM cards"}``

        """
        data = request.get_json(silent=True)
        if data is None or "sql" not in data:
            return jsonify({"error": "Missing 'sql' field"}), _HTTP_BAD_REQUEST

        sql: str = data["sql"]
        try:
            output = env.run_sql(sql)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"output": f"Error: {exc}", "error": True})
        return jsonify({"output": output, "error": False})

    return app


def main(data_dir: str | Path = "pystack_data") -> None:
    """Run the web UI development server, saving everything when it stops.

    Args:
        data_dir: Where the database and plugin data are kept.

    """
    app = create_app(data_dir)
    env: PyStackEnvironment = app.extensions["pystack_env"]
    atexit.register(env.shutdown)  # backstop; shutdown() only runs once
    try:
        app.run(port=8080)
    finally:
        env.shutdown()
