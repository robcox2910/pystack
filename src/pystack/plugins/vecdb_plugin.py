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

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pyvecdb.distance import cosine_similarity
from pyvecdb.search import knn_search
from pyvecdb.store import VectorStore

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_store: VectorStore | None = None

DEFAULT_DIMENSIONS = 3


def _get_store(dimensions: int = DEFAULT_DIMENSIONS) -> VectorStore:
    """Return the shared VectorStore instance, creating it if needed."""
    global _store  # noqa: PLW0603
    if _store is None:
        _store = VectorStore(dimensions=dimensions)
    return _store


def _parse_vector(raw: PebbleValue) -> list[float]:
    """Parse a vector from a Pebble value (list of numbers or string)."""
    if isinstance(raw, list):
        return [float(str(item)) for item in raw]
    # Try parsing as string like "[0.1, 0.2, 0.3]"
    text = str(raw).strip("[]")
    return [float(x.strip()) for x in text.split(",")]


@pebble_handler
def _vec_insert(args: list[PebbleValue]) -> PebbleValue:
    """Insert a vector with an id into the store."""
    record_id = str(args[0])
    vector = _parse_vector(args[1])
    store = _get_store(dimensions=len(vector))
    store.insert(record_id, vector)
    return record_id


@pebble_handler
def _vec_search(args: list[PebbleValue]) -> PebbleValue:
    """Search for the k most similar vectors."""
    query_vector = _parse_vector(args[0])
    k = int(str(args[1])) if len(args) > 1 else 1
    store = _get_store(dimensions=len(query_vector))
    results = knn_search(store, query=query_vector, k=k)
    result_list: list[PebbleValue] = [r.record_id for r, _score in results]
    return result_list


@pebble_handler
def _vec_cosine(args: list[PebbleValue]) -> PebbleValue:
    """Compute cosine similarity between two vectors."""
    vec_a = _parse_vector(args[0])
    vec_b = _parse_vector(args[1])
    return cosine_similarity(vec_a, vec_b)


def reset_vecdb_state() -> None:
    """Reset all module-level state for testing."""
    global _store  # noqa: PLW0603
    _store = None


class VecDBPlugin(Plugin):
    """Integrate PyVecDB vector database functions into PyStack.

    Register insert/search/cosine functions in Pebble's ``vecdb``
    stdlib module and shell commands for interactive use.
    """

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
                "vec_insert": (2, _vec_insert),
                "vec_search": (2, _vec_search),
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
                store = _get_store(dimensions=len(vector))
                store.insert(record_id, vector)
                return f"Inserted '{record_id}'"

            if sub == "search" and len(args) >= min_search_args:
                query_vector = _parse_vector(args[1])
                k = int(args[2]) if len(args) >= min_cosine_args else 1
                store = _get_store(dimensions=len(query_vector))
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
