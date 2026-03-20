"""Tests for the PyStack web UI.

The web UI provides browser-based access to the integrated platform.
These tests verify the API endpoints work correctly.
"""

import json

from pystack.web.app import create_app

CONTENT_TYPE = "application/json"


class TestWebApp:
    """Verify the Flask application and its endpoints."""

    def test_index_returns_html(self) -> None:
        """GET / should return the terminal HTML page."""
        app = create_app()
        with app.test_client() as client:
            response = client.get("/")
            assert response.status_code == 200  # noqa: PLR2004
            assert b"PyStack" in response.data

    def test_shell_endpoint(self) -> None:
        """POST /api/shell should execute a shell command."""
        app = create_app()
        with app.test_client() as client:
            response = client.post(
                "/api/shell",
                data=json.dumps({"command": "echo hello"}),
                content_type=CONTENT_TYPE,
            )
            data = json.loads(response.data)
            assert "hello" in data["output"]
            assert not data["halted"]

    def test_shell_missing_command(self) -> None:
        """POST /api/shell without a command should return 400."""
        app = create_app()
        with app.test_client() as client:
            response = client.post(
                "/api/shell",
                data=json.dumps({}),
                content_type=CONTENT_TYPE,
            )
            assert response.status_code == 400  # noqa: PLR2004

    def test_pebble_endpoint(self) -> None:
        """POST /api/pebble should execute Pebble code."""
        app = create_app()
        with app.test_client() as client:
            response = client.post(
                "/api/pebble",
                data=json.dumps({"source": "print(1 + 2)"}),
                content_type=CONTENT_TYPE,
            )
            data = json.loads(response.data)
            assert "3" in data["output"]
            assert not data["error"]

    def test_pebble_error(self) -> None:
        """POST /api/pebble with invalid code should return an error."""
        app = create_app()
        with app.test_client() as client:
            response = client.post(
                "/api/pebble",
                data=json.dumps({"source": "invalid!!!code"}),
                content_type=CONTENT_TYPE,
            )
            data = json.loads(response.data)
            assert data["error"]

    def test_sql_endpoint(self) -> None:
        """POST /api/sql should execute SQL."""
        app = create_app()
        with app.test_client() as client:
            # Create a table first.
            client.post(
                "/api/sql",
                data=json.dumps({"sql": "CREATE TABLE t (val INTEGER)"}),
                content_type=CONTENT_TYPE,
            )
            client.post(
                "/api/sql",
                data=json.dumps({"sql": "INSERT INTO t VALUES (42)"}),
                content_type=CONTENT_TYPE,
            )
            response = client.post(
                "/api/sql",
                data=json.dumps({"sql": "SELECT * FROM t"}),
                content_type=CONTENT_TYPE,
            )
            data = json.loads(response.data)
            assert "42" in data["output"]
            assert not data["error"]

    def test_sql_missing_field(self) -> None:
        """POST /api/sql without sql field should return 400."""
        app = create_app()
        with app.test_client() as client:
            response = client.post(
                "/api/sql",
                data=json.dumps({}),
                content_type=CONTENT_TYPE,
            )
            assert response.status_code == 400  # noqa: PLR2004

    def test_pebble_with_db(self) -> None:
        """Pebble code should have access to the database."""
        app = create_app()
        with app.test_client() as client:
            response = client.post(
                "/api/pebble",
                data=json.dumps(
                    {
                        "source": (
                            'import "db"\n'
                            'db_execute("CREATE TABLE webtest (val INTEGER)")\n'
                            'db_execute("INSERT INTO webtest VALUES (99)")\n'
                            'let rows = db_query("SELECT val FROM webtest")\n'
                            'print(rows[0]["val"])'
                        ),
                    }
                ),
                content_type=CONTENT_TYPE,
            )
            data = json.loads(response.data)
            assert "99" in data["output"]
