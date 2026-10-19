"""Tests for the ``schedweb`` demo: PyScheduler's web UI over seeded runs."""

from pystack.plugins import _schedweb
from pystack.plugins.sched_plugin import PySchedulerPlugin

SERVE_SECONDS = "2"


def _run_schedweb(*args: str) -> str:
    """Run the schedweb shell command with ``args`` and return its output."""
    cmds = {c.name: c.handler for c in PySchedulerPlugin().shell_commands()}
    return cmds["schedweb"](list(args))


class TestSchedwebCommand:
    """Verify the demo seeds, serves the UI, answers the login page and stops."""

    def test_serves_the_login_page(self) -> None:
        """With --seconds the UI opens, the login page answers 200, and it stops by itself."""
        output = _run_schedweb("--seconds", SERVE_SECONDS)
        assert "The web UI was at http://127.0.0.1:" in output
        assert "log in as admin / demo" in output
        assert "The login page answered 200." in output
        assert output.endswith("The web UI has stopped.")
        assert "Traceback" not in output


class TestSchedwebArguments:
    """Verify argument handling without starting anything."""

    def test_bad_arguments_show_usage(self) -> None:
        """Unknown flags, a missing value or a non-positive value show the usage line."""
        for args in (["--minutes", "1"], ["--seconds"], ["--seconds", "0"], ["--seconds", "x"]):
            assert _run_schedweb(*args) == _schedweb.USAGE

    def test_no_arguments_means_until_ctrl_c(self) -> None:
        """No arguments means serve until Ctrl-C (no time limit)."""
        assert _schedweb.parse_seconds([]) is None
