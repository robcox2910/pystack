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

from pebble.builtins import Value as PebbleValue
from pebble.stdlib import StdlibModule
from pygraphdb.graph import Graph
from pygraphdb.pathfinding import shortest_path
from pygraphdb.traversal import bfs

from pystack.plugins.base import Plugin, PluginInfo, ShellCommand, pebble_handler

_graph: Graph | None = None

_edge_counter: int = 0


def _get_graph() -> Graph:
    """Return the shared Graph instance, creating it if needed."""
    global _graph  # noqa: PLW0603
    if _graph is None:
        _graph = Graph()
    return _graph


@pebble_handler
def _graph_add_node(args: list[PebbleValue]) -> PebbleValue:
    """Add a node to the graph with an id and label."""
    node_id = str(args[0])
    label = str(args[1]) if len(args) > 1 else ""
    g = _get_graph()
    g.add_node(node_id, label=label)
    return node_id


@pebble_handler
def _graph_add_edge(args: list[PebbleValue]) -> PebbleValue:
    """Add an edge between two nodes."""
    global _edge_counter  # noqa: PLW0603
    from_id = str(args[0])
    to_id = str(args[1])
    rel_type = str(args[2]) if len(args) > 2 else "CONNECTED"  # noqa: PLR2004
    g = _get_graph()
    _edge_counter += 1
    edge_id = f"e{_edge_counter}"
    g.add_edge(edge_id, from_id, to_id, rel_type=rel_type)
    return edge_id


@pebble_handler
def _graph_shortest_path(args: list[PebbleValue]) -> PebbleValue:
    """Find the shortest path between two nodes."""
    from_id = str(args[0])
    to_id = str(args[1])
    g = _get_graph()
    path = shortest_path(g, from_id, to_id)
    if not path:
        return "no path"
    result: list[PebbleValue] = [n.node_id for n in path]
    return result


@pebble_handler
def _graph_bfs(args: list[PebbleValue]) -> PebbleValue:
    """Perform breadth-first search from a start node."""
    start_id = str(args[0])
    g = _get_graph()
    visited = bfs(g, start_id)
    result: list[PebbleValue] = [n.node_id for n in visited]
    return result


def reset_graphdb_state() -> None:
    """Reset all module-level state for testing."""
    global _graph, _edge_counter  # noqa: PLW0603
    _graph = None
    _edge_counter = 0


class GraphDBPlugin(Plugin):
    """Integrate PyGraphDB graph database functions into PyStack.

    Register node/edge/path/traversal functions in Pebble's ``graphdb``
    stdlib module and shell commands for interactive use.
    """

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
                "graph_add_node": (2, _graph_add_node),
                "graph_add_edge": (3, _graph_add_edge),
                "graph_shortest_path": (2, _graph_shortest_path),
                "graph_bfs": (1, _graph_bfs),
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
                _get_graph().add_node(node_id, label=label)
                return f"Added node '{node_id}' ({label})"

            if sub == "add-edge" and len(args) >= min_path_args:
                global _edge_counter  # noqa: PLW0603
                from_id = args[1]
                to_id = args[2]
                rel_type = args[3] if len(args) >= min_add_edge_args else "CONNECTED"
                _edge_counter += 1
                edge_id = f"e{_edge_counter}"
                _get_graph().add_edge(edge_id, from_id, to_id, rel_type=rel_type)
                return f"Added edge {from_id} -[{rel_type}]-> {to_id}"

            if sub == "path" and len(args) >= min_path_args:
                from_id = args[1]
                to_id = args[2]
                path = shortest_path(_get_graph(), from_id, to_id)
                if not path:
                    return "No path found"
                return " -> ".join(n.node_id for n in path)

            return "Usage: graph <add-node|add-edge|path> [args...]"

        return [
            ShellCommand(name="graph", handler=_graph_cmd, help_text="Graph database operations"),
        ]
