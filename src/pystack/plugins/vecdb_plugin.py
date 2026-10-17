"""PyVecDB integration plugin for PyStack.

Bridge PyVecDB's vector database into Pebble so kids can insert vectors,
search for similar ones, and compute cosine similarity.

A vector database is like a music app that turns songs into lists of
numbers, then finds other songs with similar numbers -- that is how
recommendations work!

Pebble module name: ``vecdb``

Example Pebble usage::

    import "vecdb"
    vec_insert("song1", [0.9, 0.1, 0.3])
    vec_insert("song2", [0.2, 0.8, 0.4])
    let results = vec_search([0.85, 0.15, 0.35], 1)
    print(results)
"""

from pathlib import Path

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pyvecdb.distance import cosine_similarity
from pyvecdb.persistence import load_store, save_store
from pyvecdb.search import knn_search
from pyvecdb.store import VectorStore

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler, pebble_method

DEFAULT_DIMENSIONS = 3


def _parse_vector(raw: PebbleValue) -> list[float]:
    """Parse a vector from a Pebble value (list of numbers or string)."""
    if isinstance(raw, list):
        return [float(str(item)) for item in raw]
    # Try parsing as string like "[0.1, 0.2, 0.3]"
    text = str(raw).strip("[]")
    return [float(x.strip()) for x in text.split(",")]


@pebble_handler
def _vec_cosine(args: list[PebbleValue]) -> PebbleValue:
    """Compute cosine similarity between two vectors."""
    vec_a = _parse_vector(args[0])
    vec_b = _parse_vector(args[1])
    return cosine_similarity(vec_a, vec_b)


_STORE_FILE = "store.json"


class VecDBPlugin(Plugin):
    """Integrate PyVecDB vector database functions into PyStack.

    Register insert/search/cosine functions in Pebble's ``vecdb``
    stdlib module and shell commands for interactive use.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._store: VectorStore | None = None

    def _get_store(self, dimensions: int = DEFAULT_DIMENSIONS) -> VectorStore:
        """Return this plugin's VectorStore, creating it on first use."""
        if self._store is None:
            self._store = VectorStore(dimensions=dimensions)
        return self._store

    @pebble_method
    def vec_insert(self, args: list[PebbleValue]) -> PebbleValue:
        """Insert a vector with an id into the store."""
        record_id = str(args[0])
        vector = _parse_vector(args[1])
        store = self._get_store(dimensions=len(vector))
        store.insert(record_id, vector)
        return record_id

    @pebble_method
    def vec_search(self, args: list[PebbleValue]) -> PebbleValue:
        """Search for the k most similar vectors."""
        query_vector = _parse_vector(args[0])
        k = int(str(args[1])) if len(args) > 1 else 1
        if self._store is None:
            # Don't create the store here: that would fix its vector size
            # (and save it) just because someone searched an empty store.
            return "error: Cannot search an empty store"
        store = self._store
        results = knn_search(store, query=query_vector, k=k)
        result_list: list[PebbleValue] = [r.record_id for r, _score in results]
        return result_list

    def load_state(self, folder: Path) -> None:
        """Load the saved vector store, if there is one."""
        path = folder / _STORE_FILE
        if path.exists():
            self._store = load_store(path)

    def save_state(self, folder: Path) -> None:
        """Save the vector store, if this run used or loaded one."""
        if self._store is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        save_store(self._store, folder / _STORE_FILE)

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyVecDB",
            description="Vector database for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "vecdb"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the vecdb stdlib module with insert/search/cosine functions."""
        return StdlibModule(
            functions={
                "vec_insert": (2, self.vec_insert),
                "vec_search": (2, self.vec_search),
                "vec_cosine": (2, _vec_cosine),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the vec shell commands."""

        def _vec_cmd(args: list[str]) -> str:
            """Handle vec subcommands: insert, search, cosine."""
            if not args:
                return "Usage: vec <insert|search|cosine> [args...]"

            sub = args[0]
            min_insert_args = 3
            min_search_args = 2
            min_cosine_args = 3

            if sub == "insert" and len(args) >= min_insert_args:
                record_id = args[1]
                vector = _parse_vector(args[2])
                store = self._get_store(dimensions=len(vector))
                store.insert(record_id, vector)
                return f"Inserted '{record_id}'"

            if sub == "search" and len(args) >= min_search_args:
                query_vector = _parse_vector(args[1])
                k = int(args[2]) if len(args) >= min_cosine_args else 1
                store = self._get_store(dimensions=len(query_vector))
                results = knn_search(store, query=query_vector, k=k)
                return "\n".join(f"{r.record_id}: {score:.4f}" for r, score in results)

            if sub == "cosine" and len(args) >= min_cosine_args:
                vec_a = _parse_vector(args[1])
                vec_b = _parse_vector(args[2])
                sim = cosine_similarity(vec_a, vec_b)
                return f"{sim:.6f}"

            return "Usage: vec <insert|search|cosine> [args...]"

        return [
            ShellCommand(name="vec", handler=_vec_cmd, help_text="Vector database operations"),
        ]
