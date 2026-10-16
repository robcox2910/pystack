"""The ``pystack`` command must work even when the optional web extra isn't installed.

Flask is only needed for ``pystack web``. Someone who installs plain
``pystack`` should still be able to run every other command.
"""

import subprocess
import sys

_BLOCK_FLASK_AND_RUN_HELP = """
import sys
sys.modules["flask"] = None  # pretend Flask isn't installed
sys.argv = ["pystack", "--help"]
from pystack.cli import main
main()
"""

_BLOCK_FLASK_AND_RUN_WEB = """
import sys
sys.modules["flask"] = None
sys.argv = ["pystack", "web"]
from pystack.cli import main
main()
"""


def _run(code: str) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a fresh Python, so blocking Flask can't leak into other tests."""
    return subprocess.run(  # noqa: S603 -- running our own interpreter with a fixed snippet
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, timeout=60
    )


def test_cli_starts_without_flask() -> None:
    """Regression: importing the CLI used to fail with ImportError when Flask was missing."""
    result = _run(_BLOCK_FLASK_AND_RUN_HELP)
    assert result.returncode == 0, result.stderr
    assert "pystack" in result.stdout


def test_web_command_explains_how_to_install_flask() -> None:
    """``pystack web`` without Flask says which extra to install instead of a traceback."""
    result = _run(_BLOCK_FLASK_AND_RUN_WEB)
    assert result.returncode == 1
    assert "pip install 'pystack[web]'" in result.stderr
    assert "Traceback" not in result.stderr
