"""PyGit integration plugin for PyStack.

Bridge PyGit's hashing and diff functionality into Pebble so kids can
compute Git-style SHA-1 hashes and diff two strings from their Pebble
programs.

Pebble module name: ``git``

Example Pebble usage::

    import "git"
    let h = git_hash("hello world")
    print(h)

    let d = git_diff("line1", "line2")
    print(d)
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pygit.diff import diff_lines, format_diff
from pygit.hashing import hash_content

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler


@pebble_handler
def _git_hash(args: list[PebbleValue]) -> PebbleValue:
    """Return the SHA-1 hash of a text string (Git-style)."""
    return hash_content(str(args[0]))


@pebble_handler
def _git_diff(args: list[PebbleValue]) -> PebbleValue:
    """Return a unified diff between two text strings."""
    old = str(args[0])
    new = str(args[1])
    lines = diff_lines(old, new)
    return format_diff(lines)


class GitPlugin(Plugin):
    """Integrate PyGit hashing and diff into PyStack.

    Register git_hash and git_diff functions in Pebble's ``git``
    stdlib module, and a ``git-hash`` shell command.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyGit",
            description="Git hashing and diff for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "git"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the git stdlib module with git_hash and git_diff."""
        return StdlibModule(
            functions={
                "git_hash": (1, _git_hash),
                "git_diff": (2, _git_diff),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return git-hash and git-diff shell commands."""

        def _git_hash_cmd(args: list[str]) -> str:
            """Print the SHA-1 hash of the given text."""
            if not args:
                return "Usage: git-hash <text>"
            text = " ".join(args)
            return hash_content(text)

        def _git_diff_cmd(args: list[str]) -> str:
            """Show a diff (requires two arguments)."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: git-diff <old> <new>"
            lines = diff_lines(args[0], args[1])
            return format_diff(lines)

        return [
            ShellCommand(name="git-hash", handler=_git_hash_cmd, help_text="Print SHA-1 hash"),
            ShellCommand(name="git-diff", handler=_git_diff_cmd, help_text="Show diff"),
        ]
