"""Tests that sibling projects come from their PyPI releases.

PyStack used to build against each sibling's latest ``main``, so a change
in one project could break PyStack without anyone touching PyStack. Now
every sibling is a released ``fromscratch-*`` package with a minimum
version, like using a specific edition of a textbook instead of whatever
the author is still writing.
"""

import re
import tomllib
from pathlib import Path
from typing import Any

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
SIBLING_PREFIX = "fromscratch-"
# A sibling requirement: the package name and a minimum released version.
SIBLING_REQUIREMENT = re.compile(r"(fromscratch-[a-z]+)>=\d+\.\d+\.\d+")
SIBLINGS = frozenset(
    f"{SIBLING_PREFIX}{name}"
    for name in (
        "pyos",
        "pebble",
        "pydb",
        "pyweb",
        "pygit",
        "pycrypt",
        "pynet",
        "pysearch",
        "pymq",
        "pykv",
        "pydocdb",
        "pygraphdb",
        "pytsdb",
        "pyvecdb",
        "pycoldb",
        "pyllm",
        "pyscheduler",
    )
)


def _config() -> dict[str, Any]:
    """Return pyproject.toml as a dictionary."""
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _sibling_requirements() -> list[str]:
    """Return the required dependencies that are series siblings."""
    dependencies: list[str] = _config()["project"]["dependencies"]
    return [d for d in dependencies if d.startswith(SIBLING_PREFIX)]


class TestDependencyPins:
    """Every sibling comes from a PyPI release, never a folder, a branch or a git tag."""

    def test_no_sibling_is_pulled_from_git_or_a_folder(self) -> None:
        """There is no ``[tool.uv.sources]`` table, so nothing bypasses PyPI."""
        assert "sources" not in _config().get("tool", {}).get("uv", {})

    def test_every_sibling_names_a_released_version(self) -> None:
        """Each sibling requirement has a ``>=X.Y.Z`` floor."""
        for requirement in _sibling_requirements():
            assert SIBLING_REQUIREMENT.fullmatch(requirement), requirement

    def test_every_sibling_is_listed(self) -> None:
        """A sibling can't go missing or sneak in unnoticed."""
        names = {SIBLING_REQUIREMENT.fullmatch(r) for r in _sibling_requirements()}
        assert {m.group(1) for m in names if m} == SIBLINGS
