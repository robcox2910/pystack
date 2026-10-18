"""PyGraphDB integration plugin for PyStack.

Bridge PyGraphDB's graph database into Pebble so kids can create nodes,
add edges, find shortest paths, and traverse graphs from their programs.

A graph database stores data as nodes (dots) and edges (lines connecting
them) -- like a social network map showing who is friends with whom.

Pebble module name: ``graphdb``

Example Pebble usage::

    import "graphdb"
    graph_add_node("alice", "Person")
    graph_add_node("bob", "Person")
    graph_add_edge("alice", "bob", "KNOWS")
    let path = graph_shortest_path("alice", "bob")
    print(path)
"""

from pathlib import Path
from typing import cast

from pebble import StdlibModule
from pebble import Value as PebbleValue
from pygraphdb.graph import Graph
from pygraphdb.pathfinding import shortest_path
from pygraphdb.persistence import load_graph, save_graph
from pygraphdb.traversal import bfs

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_method

_GRAPH_FILE = "graph.json"


def _saved_edges(graph: Graph) -> list[dict[str, str]]:
    """Return the edges of *graph* as plain dicts (each has an ``edge_id``)."""
    edges = graph.to_dict()["edges"]
    return cast("list[dict[str, str]]", edges)


def _counter_number(edge_id: str) -> int | None:
    """Return the number in an id this plugin makes itself (``e7`` -> 7), else None."""
    number = edge_id[1:]
    # ``isdigit`` alone also says yes to "²", which ``int`` can't read,
    # and this plugin only ever writes 0-9.
    if not (edge_id.startswith("e") and number.isascii() and number.isdigit()):
        return None
    try:
        return int(number)
    except ValueError:  # over 4,300 digits: too long for ``int`` to read
        return None


class GraphDBPlugin(Plugin):
    """Integrate PyGraphDB graph database functions into PyStack.

    Register node/edge/path/traversal functions in Pebble's ``graphdb``
    stdlib module and shell commands for interactive use.
    """

    def __init__(self) -> None:
        """Start with no data; it is created on first use or loaded at start-up."""
        self._graph: Graph | None = None
        self._edge_counter: int = 0

    def _get_graph(self) -> Graph:
        """Return this plugin's Graph, creating it on first use."""
        if self._graph is None:
            self._graph = Graph()
        return self._graph

    @pebble_method
    def graph_add_node(self, args: list[PebbleValue]) -> PebbleValue:
        """Add a node to the graph with an id and label."""
        node_id = str(args[0])
        label = str(args[1]) if len(args) > 1 else ""
        g = self._get_graph()
        g.add_node(node_id, label=label)
        return node_id

    @pebble_method
    def graph_add_edge(self, args: list[PebbleValue]) -> PebbleValue:
        """Add an edge between two nodes."""
        from_id = str(args[0])
        to_id = str(args[1])
        rel_type = str(args[2]) if len(args) > 2 else "CONNECTED"  # noqa: PLR2004
        g = self._get_graph()
        self._edge_counter += 1
        edge_id = f"e{self._edge_counter}"
        g.add_edge(edge_id, from_id, to_id, rel_type=rel_type)
        return edge_id

    @pebble_method
    def graph_shortest_path(self, args: list[PebbleValue]) -> PebbleValue:
        """Find the shortest path between two nodes."""
        from_id = str(args[0])
        to_id = str(args[1])
        g = self._get_graph()
        path = shortest_path(g, from_id, to_id)
        if not path:
            return "no path"
        result: list[PebbleValue] = [n.node_id for n in path]
        return result

    @pebble_method
    def graph_bfs(self, args: list[PebbleValue]) -> PebbleValue:
        """Perform breadth-first search from a start node."""
        start_id = str(args[0])
        g = self._get_graph()
        visited = bfs(g, start_id)
        result: list[PebbleValue] = [n.node_id for n in visited]
        return result

    def load_state(self, folder: Path) -> None:
        """Load the saved graph, if there is one."""
        path = folder / _GRAPH_FILE
        if path.exists():
            self._graph = load_graph(path)
            # New edges get ids after the saved ones (e1, e2, ...).
            numbers = (_counter_number(edge["edge_id"]) for edge in _saved_edges(self._graph))
            self._edge_counter = max((n for n in numbers if n is not None), default=0)

    def save_state(self, folder: Path) -> None:
        """Save the graph, if this run used or loaded one."""
        if self._graph is None:
            return
        folder.mkdir(parents=True, exist_ok=True)
        save_graph(self._graph, folder / _GRAPH_FILE)

    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="PyGraphDB",
            description="Graph database for Pebble programs",
            version="0.1.0",
        )

    def pebble_module_name(self) -> str:
        """Return the Pebble import name."""
        return "graphdb"

    def pebble_stdlib(self) -> StdlibModule:
        """Return the graphdb stdlib module with node/edge/path functions."""
        return StdlibModule(
            functions={
                "graph_add_node": (2, self.graph_add_node),
                "graph_add_edge": (3, self.graph_add_edge),
                "graph_shortest_path": (2, self.graph_shortest_path),
                "graph_bfs": (1, self.graph_bfs),
            },
            constants={},
        )

    def shell_commands(self) -> list[ShellCommand]:
        """Return the graph shell commands."""

        def _graph_cmd(args: list[str]) -> str:
            """Handle graph subcommands: add-node, add-edge, path."""
            if not args:
                return "Usage: graph <add-node|add-edge|path> [args...]"

            sub = args[0]
            min_add_node_args = 3
            min_add_edge_args = 4
            min_path_args = 3

            if sub == "add-node" and len(args) >= min_add_node_args:
                node_id = args[1]
                label = args[2]
                self._get_graph().add_node(node_id, label=label)
                return f"Added node '{node_id}' ({label})"

            if sub == "add-edge" and len(args) >= min_path_args:
                from_id = args[1]
                to_id = args[2]
                rel_type = args[3] if len(args) >= min_add_edge_args else "CONNECTED"
                self._edge_counter += 1
                edge_id = f"e{self._edge_counter}"
                self._get_graph().add_edge(edge_id, from_id, to_id, rel_type=rel_type)
                return f"Added edge {from_id} -[{rel_type}]-> {to_id}"

            if sub == "path" and len(args) >= min_path_args:
                from_id = args[1]
                to_id = args[2]
                path = shortest_path(self._get_graph(), from_id, to_id)
                if not path:
                    return "No path found"
                return " -> ".join(n.node_id for n in path)

            return "Usage: graph <add-node|add-edge|path> [args...]"

        return [
            ShellCommand(name="graph", handler=_graph_cmd, help_text="Graph database operations"),
        ]
