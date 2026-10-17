"""PySearch integration plugin for PyStack.

Bridge PySearch's full-text search engine into Pebble so kids can
create search indices, add documents, and query them with TF-IDF
ranking from their Pebble programs.

A search engine is like the index at the back of a book -- you type a
word and it instantly tells you which pages mention it, best matches
first.

Pebble module name: ``search``

Example Pebble usage::

    import "search"
    let engine = search_create()
    search_add(engine, "doc1", "the cat sat on the mat")
    search_add(engine, "doc2", "the dog chased the cat")
    let results = search_query(engine, "cat")
    print(results)
"""

from pathlib import Path

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pysearch.engine import SearchEngine
from pysearch.persistence import load_engine, save_engine

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method


def _engine_number(engine_id: str) -> int:
    """Return the number in an engine id: ``engine_7`` -> 7."""
    return int(engine_id.removeprefix("engine_"))


class SearchPlugin(Plugin):
    """Integrate PySearch full-text search into PyStack.

    Register search_create, search_add, and search_query functions in
    Pebble's ``search`` stdlib module. No shell commands -- search is
    more naturally used from Pebble programs.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._engines: dict[str, SearchEngine] = {}
        self._next_id: list[int] = [0]

    @pebble_method
    def search_create(self, args: list[PebbleValue]) -> PebbleValue:  # noqa: ARG002
        """Create a new search engine and return its ID string."""
        engine_id = f"engine_{self._next_id[0]}"
        self._next_id[0] += 1
        self._engines[engine_id] = SearchEngine()
        return engine_id

    @pebble_method
    def search_add(self, args: list[PebbleValue]) -> PebbleValue:
        """Add a document to a search engine by engine ID."""
        engine_id = str(args[0])
        doc_id = str(args[1])
        text = str(args[2])
        if engine_id not in self._engines:
            return f"error: unknown engine {engine_id}"
        self._engines[engine_id].add(doc_id, text)
        return True

    @pebble_method
    def search_query(self, args: list[PebbleValue]) -> PebbleValue:
        """Query a search engine and return a list of [doc_id, score] results."""
        engine_id = str(args[0])
        query = str(args[1])
        if engine_id not in self._engines:
            return f"error: unknown engine {engine_id}"
        results = self._engines[engine_id].search(query)
        pebble_results: list[PebbleValue] = []
        for doc_id, score in results:
            pair: list[PebbleValue] = [doc_id, score]
            pebble_results.append(pair)
        return pebble_results

    @pebble_method
    def search_list(self, args: list[PebbleValue]) -> PebbleValue:  # noqa: ARG002 -- Pebble passes args
        """Return the ids of every engine, oldest first (including saved ones)."""
        ordered = sorted(self._engines, key=_engine_number)
        ids: list[PebbleValue] = list(ordered)
        return ids

    def load_state(self, folder: Path) -> None:
        """Load every saved engine; new engines get ids after the saved ones."""
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("engine_*.json")):
            self._engines[path.stem] = load_engine(path)
        numbers = [_engine_number(engine_id) for engine_id in self._engines]
        self._next_id[0] = max(numbers, default=-1) + 1

    def save_state(self, folder: Path) -> None:
        """Save every engine, one file each."""
        if not self._engines:
            return
        folder.mkdir(parents=True, exist_ok=True)
        for engine_id, engine in self._engines.items():
            save_engine(engine, folder / f"{engine_id}.json")

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
                "search_create": (0, self.search_create),
                "search_add": (3, self.search_add),
                "search_query": (2, self.search_query),
                "search_list": (0, self.search_list),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return no shell commands (search is used from Pebble)."""
        return []
