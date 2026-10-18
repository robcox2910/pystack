"""Tests that sibling projects are pinned to release tags.

PyStack used to build against each sibling's latest ``main``, so a change
in one project could break PyStack without anyone touching PyStack. Now
every sibling is pinned to a release tag, like using a specific edition
of a textbook instead of whatever the author is still writing.
"""

import re
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
GITHUB = "https://github.com/robcox2910"
# Packages whose GitHub repo has a different name.
REPOS = {"pyos-learn": "py-os", "pydocdb": "pydoc-db"}
TAG_PATTERN = re.compile(r"v\d+\.\d+\.\d+")
SIBLINGS = frozenset(
    {
        "pyos-learn",
        "pebble-lang",
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
    }
)


def _sources() -> dict[str, dict[str, str]]:
    """Return the ``[tool.uv.sources]`` table from pyproject.toml."""
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["uv"]["sources"]


class TestDependencyPins:
    """Every sibling comes from a tagged release, never a folder or a branch."""

    def test_every_sibling_source_is_a_tagged_git_source(self) -> None:
        """Each source names the sibling's GitHub repo and a vX.Y.Z tag."""
        for name, source in _sources().items():
            assert set(source) == {"git", "tag"}, name
            assert source["git"] == f"{GITHUB}/{REPOS.get(name, name)}", name
            assert TAG_PATTERN.fullmatch(source["tag"]), name

    def test_every_sibling_has_a_pinned_source(self) -> None:
        """A new sibling can't sneak in without a pinned source."""
        assert set(_sources()) == SIBLINGS

    def test_overrides_use_the_pinned_tags(self) -> None:
        """An override for a sibling names exactly the repo and tag of its pinned source.

        Some siblings pin older tags of other siblings in their own sources;
        the overrides win, so they must never drift from the pins above.
        """
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["tool"]["uv"]
        sources = config["sources"]
        for override in config.get("override-dependencies", []):
            name, url = (part.strip() for part in override.split("@", 1))
            assert name in SIBLINGS, override
            source = sources[name]
            assert url == f"git+{source['git']}@{source['tag']}", override
