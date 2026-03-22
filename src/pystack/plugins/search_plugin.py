"""PySearch integration plugin for PyStack.

Bridge PySearch's full-text search engine into Pebble so kids can
create search indices, add documents, and query them with TF-IDF
ranking from their Pebble programs.

Pebble module name: ``search``

Example Pebble usage::

    import "search"
    let engine = search_create()
    search_add(engine, "doc1", "the cat sat on the mat")
    search_add(engine, "doc2", "the dog chased the cat")
    let results = search_query(engine, "cat")
    print(results)
"""

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pysearch.engine import SearchEngine

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

# Module-level storage for search engine instances, keyed by ID.
_engines: dict[str, SearchEngine] = {}
_next_id: list[int] = [0]


@pebble_handler
def _search_create(args: list[PebbleValue]) -> PebbleValue:  # noqa: ARG001
    """Create a new search engine and return its ID string."""
    engine_id = f"engine_{_next_id[0]}"
    _next_id[0] += 1
    _engines[engine_id] = SearchEngine()
    return engine_id


@pebble_handler
def _search_add(args: list[PebbleValue]) -> PebbleValue:
    """Add a document to a search engine by engine ID."""
    engine_id = str(args[0])
    doc_id = str(args[1])
    text = str(args[2])
    if engine_id not in _engines:
        return f"error: unknown engine {engine_id}"
    _engines[engine_id].add(doc_id, text)
    return True


@pebble_handler
def _search_query(args: list[PebbleValue]) -> PebbleValue:
    """Query a search engine and return a list of [doc_id, score] results."""
    engine_id = str(args[0])
    query = str(args[1])
    if engine_id not in _engines:
        return f"error: unknown engine {engine_id}"
    results = _engines[engine_id].search(query)
    pebble_results: list[PebbleValue] = []
    for doc_id, score in results:
        pair: list[PebbleValue] = [doc_id, score]
        pebble_results.append(pair)
    return pebble_results


def reset_engines() -> None:
    """Clear all engine instances (for testing)."""
    _engines.clear()
    _next_id[0] = 0


class SearchPlugin(Plugin):
    """Integrate PySearch full-text search into PyStack.

    Register search_create, search_add, and search_query functions in
    Pebble's ``search`` stdlib module. No shell commands -- search is
    more naturally used from Pebble programs.
    """

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PySearch",
            description="Full-text search with TF-IDF ranking for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "search"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the search stdlib module with create, add, and query functions."""
        return StdlibModule(
            functions={
                "search_create": (0, _search_create),
                "search_add": (3, _search_add),
                "search_query": (2, _search_query),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return no shell commands (search is used from Pebble)."""
        return []
