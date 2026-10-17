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

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pydocdb.collection import Collection
from pydocdb.persistence import load_collection, save_collection

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method

# Long enough to be readable, short enough for any file system.
_MAX_READABLE_NAME = 60


def _collection_file(name: str) -> str:
    """Return a safe, unique file name for collection *name*.

    The name comes from a Pebble program, so it could be anything: ``../x``,
    an empty string, or ``Pets`` next to ``pets`` (the same file on a Mac,
    whose disk ignores case). An escaped, shortened copy of the name keeps
    the file readable; a short fingerprint of the exact name keeps it unique.
    The real name is stored inside the file and used when loading.
    """
    readable = quote(name, safe="")[:_MAX_READABLE_NAME]
    fingerprint = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"{readable}-{fingerprint}.json"


class DocDBPlugin(Plugin):
    """Integrate PyDocDB document store functions into PyStack.

    Register insert/find/count functions in Pebble's ``docdb`` stdlib
    module and shell commands for interactive use.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._collections: dict[str, Collection] = {}

    def _get_collection(self, name: str) -> Collection:
        """Return a collection by name, creating it if needed."""
        if name not in self._collections:
            self._collections[name] = Collection(name)
        return self._collections[name]

    @pebble_method
    def doc_insert(self, args: list[PebbleValue]) -> PebbleValue:
        """Insert a document into a named collection."""
        collection_name = str(args[0])
        data = args[1]
        col = self._get_collection(collection_name)
        if isinstance(data, dict):
            doc = col.insert_one(data)
            return str(doc.id)
        return "error: data must be a dictionary"

    @pebble_method
    def doc_find(self, args: list[PebbleValue]) -> PebbleValue:
        """Find documents in a collection matching a query."""
        collection_name = str(args[0])
        query = args[1] if len(args) > 1 else {}
        col = self._get_collection(collection_name)
        if not isinstance(query, dict):
            query = {}
        results = col.find(query)
        result_list: list[PebbleValue] = [str(r) for r in results]
        return result_list

    @pebble_method
    def doc_count(self, args: list[PebbleValue]) -> PebbleValue:
        """Count documents in a collection."""
        collection_name = str(args[0])
        col = self._get_collection(collection_name)
        return col.count()

    def load_state(self, folder: Path) -> None:
        """Load every saved collection (one file each)."""
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*.json")):
            collection = load_collection(path)
            self._collections[collection.name] = collection

    def save_state(self, folder: Path) -> None:
        """Save every collection, one file each (see :func:`_collection_file`)."""
        if not self._collections:
            return
        folder.mkdir(parents=True, exist_ok=True)
        for name, collection in self._collections.items():
            save_collection(collection, folder / _collection_file(name))

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
                "doc_insert": (2, self.doc_insert),
                "doc_find": (2, self.doc_find),
                "doc_count": (1, self.doc_count),
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
            doc = self._get_collection(args[0]).insert_one(data)
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
            results = self._get_collection(args[0]).find(query)
            return "\n".join(str(r) for r in results) if results else "(no documents found)"

        def _doc_count_cmd(args: list[str]) -> str:
            """Count documents in a collection."""
            if not args:
                return "Usage: doc-count <collection>"
            return str(self._get_collection(args[0]).count())

        return [
            ShellCommand(name="doc-insert", handler=_doc_insert_cmd, help_text="Insert a document"),
            ShellCommand(name="doc-find", handler=_doc_find_cmd, help_text="Find documents"),
            ShellCommand(name="doc-count", handler=_doc_count_cmd, help_text="Count documents"),
        ]
