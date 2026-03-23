"""PyDocDB integration plugin for PyStack.

Bridge PyDocDB's document store into Pebble so kids can insert, find,
and count JSON-like documents from their Pebble programs.

A document database is like a filing cabinet where every index card
can have different fields -- no fixed schema required!

Pebble module name: ``docdb``

Example Pebble usage::

    import "docdb"
    doc_insert("students", {"name": "Alice", "age": 14})
    let results = doc_find("students", {"name": "Alice"})
    print(results)
"""

import json

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pydocdb.collection import Collection

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_collections: dict[str, Collection] = {}


def _get_collection(name: str) -> Collection:
    """Return a collection by name, creating it if needed."""
    if name not in _collections:
        _collections[name] = Collection(name)
    return _collections[name]


@pebble_handler
def _doc_insert(args: list[PebbleValue]) -> PebbleValue:
    """Insert a document into a named collection."""
    collection_name = str(args[0])
    data = args[1]
    col = _get_collection(collection_name)
    if isinstance(data, dict):
        doc = col.insert_one(data)
        return str(doc.id)
    return "error: data must be a dictionary"


@pebble_handler
def _doc_find(args: list[PebbleValue]) -> PebbleValue:
    """Find documents in a collection matching a query."""
    collection_name = str(args[0])
    query = args[1] if len(args) > 1 else {}
    col = _get_collection(collection_name)
    if not isinstance(query, dict):
        query = {}
    results = col.find(query)
    result_list: list[PebbleValue] = [str(r) for r in results]
    return result_list


@pebble_handler
def _doc_count(args: list[PebbleValue]) -> PebbleValue:
    """Count documents in a collection."""
    collection_name = str(args[0])
    col = _get_collection(collection_name)
    return col.count()


def reset_docdb_state() -> None:
    """Reset all module-level state for testing."""
    _collections.clear()


class DocDBPlugin(Plugin):
    """Integrate PyDocDB document store functions into PyStack.

    Register insert/find/count functions in Pebble's ``docdb`` stdlib
    module and shell commands for interactive use.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyDocDB",
            description="Document store for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "docdb"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the docdb stdlib module with insert/find/count functions."""
        return StdlibModule(
            functions={
                "doc_insert": (2, _doc_insert),
                "doc_find": (2, _doc_find),
                "doc_count": (1, _doc_count),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the doc shell commands."""

        def _doc_insert_cmd(args: list[str]) -> str:
            """Insert a document into a collection."""
            if len(args) < 2:  # noqa: PLR2004
                return "Usage: doc-insert <collection> <json>"
            try:
                data = json.loads(" ".join(args[1:]))
            except json.JSONDecodeError:
                return "Error: invalid JSON"
            doc = _get_collection(args[0]).insert_one(data)
            return f"Inserted document {doc.id}"

        def _doc_find_cmd(args: list[str]) -> str:
            """Find documents in a collection."""
            if not args:
                return "Usage: doc-find <collection> [query]"
            query: dict[str, object] = {}
            if len(args) >= 2:  # noqa: PLR2004
                try:
                    query = json.loads(" ".join(args[1:]))
                except json.JSONDecodeError:
                    return "Error: invalid JSON query"
            results = _get_collection(args[0]).find(query)
            return "\n".join(str(r) for r in results) if results else "(no documents found)"

        def _doc_count_cmd(args: list[str]) -> str:
            """Count documents in a collection."""
            if not args:
                return "Usage: doc-count <collection>"
            return str(_get_collection(args[0]).count())

        return [
            ShellCommand(
                name="doc-insert", handler=_doc_insert_cmd, help_text="Insert a document"
            ),
            ShellCommand(
                name="doc-find", handler=_doc_find_cmd, help_text="Find documents"
            ),
            ShellCommand(
                name="doc-count", handler=_doc_count_cmd, help_text="Count documents"
            ),
        ]
