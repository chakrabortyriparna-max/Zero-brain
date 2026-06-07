"""Graphify query helper for the Slack bot.

Reads graphify-out/graph.json and provides lightweight lookup functions
for nodes, edges, and shortest paths. Returns markdown-formatted strings
suitable for Slack replies.
"""

import json
import sys
from pathlib import Path
from collections import deque
from typing import Optional

# Resolve project root relative to this file: .claude/chat/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GRAPH_PATH = PROJECT_ROOT / "graphify-out" / "graph.json"


class GraphifyGraph:
    """Lightweight in-memory graph wrapper around graphify JSON output."""

    def __init__(self, graph_path: Optional[Path] = None) -> None:
        self.path = graph_path or GRAPH_PATH
        self._nodes: dict[str, dict] = {}
        self._adj: dict[str, list[tuple[str, str, float]]] = {}
        self._hyperedges: list[dict] = []
        self._loaded = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        for node in data.get("nodes", []):
            self._nodes[node["id"]] = node

        for link in data.get("links", []):
            src = link.get("source")
            tgt = link.get("target")
            rel = link.get("relation", "related")
            weight = link.get("weight", 1.0)
            if src and tgt:
                self._adj.setdefault(src, []).append((tgt, rel, weight))
                self._adj.setdefault(tgt, []).append((src, rel, weight))

        self._hyperedges = data.get("hyperedges", [])
        self._loaded = True

    def is_loaded(self) -> bool:
        return self._loaded

    def query_nodes(self, query: str, top_k: int = 5) -> list[dict]:
        """Fuzzy-match node labels/norm_labels against a query string."""
        query_lower = query.lower()
        scored = []
        for node in self._nodes.values():
            label = node.get("label", "")
            norm = node.get("norm_label", "")
            source = node.get("source_file", "")
            score = 0
            if query_lower in label.lower():
                score += 3
            if query_lower in norm.lower():
                score += 2
            if query_lower in source.lower():
                score += 1
            if score:
                scored.append((score, node))

        scored.sort(key=lambda x: (-x[0], x[1].get("label", "")))
        return [n for _, n in scored[:top_k]]

    def get_neighbors(self, node_id: str) -> list[dict]:
        """Return all nodes directly connected to ``node_id`` with relations."""
        results = []
        for tgt_id, rel, weight in self._adj.get(node_id, []):
            tgt = self._nodes.get(tgt_id)
            if tgt:
                results.append({"node": tgt, "relation": rel, "weight": weight})
        return results

    def get_path(self, start_id: str, end_id: str) -> Optional[list[dict]]:
        """BFS shortest path between two node IDs. Returns list of nodes or None."""
        if start_id not in self._nodes or end_id not in self._nodes:
            return None

        queue = deque([(start_id, [start_id])])
        visited = {start_id}

        while queue:
            current, path = queue.popleft()
            if current == end_id:
                return [self._nodes[nid] for nid in path]

            for neighbor, _, _ in self._adj.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_community(self, community_id: int) -> list[dict]:
        """Return all nodes belonging to a given community ID."""
        return [n for n in self._nodes.values() if n.get("community") == community_id]


# Module-level singleton so the graph is loaded once per process
_graph: Optional[GraphifyGraph] = None


def _get_graph() -> GraphifyGraph:
    global _graph
    if _graph is None:
        _graph = GraphifyGraph()
    return _graph


def _format_node(node: dict) -> str:
    label = node.get("label", node.get("id", "unknown"))
    source = node.get("source_file", "")
    loc = node.get("source_location", "")
    where = f" ({source} {loc})" if source else ""
    return f"- **{label}**{where}"


def _format_edge(edge: dict) -> str:
    tgt = edge["node"]
    rel = edge["relation"]
    label = tgt.get("label", tgt.get("id", "unknown"))
    return f"- *{rel}* → **{label}**"


# ---------------------------------------------------------------------------
# Public API — returns markdown strings for Slack
# ---------------------------------------------------------------------------

def query_nodes(query: str, top_k: int = 5) -> str:
    """Query the graph for nodes matching a string. Returns markdown."""
    graph = _get_graph()
    if not graph.is_loaded():
        return "Graph not found. Run `/graphify` in Claude Code first."

    nodes = graph.query_nodes(query, top_k=top_k)
    if not nodes:
        return f"No nodes found for query: _{query}_"

    lines = [f"*Nodes matching '{query}':*"]
    for node in nodes:
        lines.append(_format_node(node))
    return "\n".join(lines)


def neighbors(node_label: str) -> str:
    """Find neighbors of a node by label. Returns markdown."""
    graph = _get_graph()
    if not graph.is_loaded():
        return "Graph not found. Run `/graphify` in Claude Code first."

    # Resolve label -> id
    target_id = None
    for nid, node in graph._nodes.items():
        candidates = [
            node.get("label", "").lower(),
            node.get("norm_label", "").lower(),
            nid.lower(),
        ]
        if any(node_label.lower() in c for c in candidates):
            target_id = nid
            break

    if target_id is None:
        return f"Node not found: _{node_label}_"

    edges = graph.get_neighbors(target_id)
    if not edges:
        return f"No connections found for *{node_label}*."

    lines = [f"*Connections for {node_label}:*"]
    for edge in edges:
        lines.append(_format_edge(edge))
    return "\n".join(lines)


def path(start_label: str, end_label: str) -> str:
    """Shortest path between two nodes by label. Returns markdown."""
    graph = _get_graph()
    if not graph.is_loaded():
        return "Graph not found. Run `/graphify` in Claude Code first."

    def resolve(label: str) -> Optional[str]:
        for nid, node in graph._nodes.items():
            candidates = [
                node.get("label", "").lower(),
                node.get("norm_label", "").lower(),
                nid.lower(),
            ]
            if any(label.lower() in c for c in candidates):
                return nid
        return None

    start_id = resolve(start_label)
    end_id = resolve(end_label)
    if not start_id:
        return f"Start node not found: _{start_label}_"
    if not end_id:
        return f"End node not found: _{end_label}_"

    result = graph.get_path(start_id, end_id)
    if not result:
        return f"No path found between *{start_label}* and *{end_label}*."

    lines = [f"*Path from {start_label} → {end_label}:*"]
    for node in result:
        lines.append(_format_node(node))
    return "\n".join(lines)


def explain(node_label: str) -> str:
    """Show node details + neighbors + any hyperedges it participates in."""
    graph = _get_graph()
    if not graph.is_loaded():
        return "Graph not found. Run `/graphify` in Claude Code first."

    target_id = None
    target_node = None
    for nid, node in graph._nodes.items():
        candidates = [
            node.get("label", "").lower(),
            node.get("norm_label", "").lower(),
            nid.lower(),
        ]
        if any(node_label.lower() in c for c in candidates):
            target_id = nid
            target_node = node
            break

    if not target_node:
        return f"Node not found: _{node_label}_"

    lines = [
        f"*Explanation for {node_label}:*",
        f"- File: `{target_node.get('source_file', 'unknown')}`",
        f"- Location: {target_node.get('source_location', 'unknown')}",
        f"- Community: {target_node.get('community', 'unknown')}",
    ]

    edges = graph.get_neighbors(target_id)
    if edges:
        lines.append("\n*Connections:*")
        for edge in edges:
            lines.append(_format_edge(edge))

    # Find hyperedges containing this node
    hyper_matches = [h for h in graph._hyperedges if target_id in h.get("nodes", [])]
    if hyper_matches:
        lines.append("\n*Participates in:*")
        for h in hyper_matches:
            label = h.get("label", h.get("id", "unknown"))
            lines.append(f"- {label}")

    return "\n".join(lines)


def _resolve_node(graph: GraphifyGraph, label: str) -> tuple[Optional[str], Optional[dict]]:
    """Resolve a label to a node id and node dict."""
    for nid, node in graph._nodes.items():
        candidates = [
            node.get("label", "").lower(),
            node.get("norm_label", "").lower(),
            nid.lower(),
        ]
        if any(label.lower() in c for c in candidates):
            return nid, node
    return None, None


def build_llm_context(subcmd: str, arg: str) -> str:
    """Build structured graph context for LLM consumption.

    Queries the graph locally and returns a detailed text block
    suitable for injection into an LLM prompt.
    """
    graph = _get_graph()
    if not graph.is_loaded():
        return "Graph not found. Run `/graphify` in Claude Code first."

    lines: list[str] = []

    if subcmd == "query":
        nodes = graph.query_nodes(arg, top_k=10)
        lines.append(f"Graphify query results for '{arg}':")
        if not nodes:
            lines.append("No matching nodes found.")
        else:
            for node in nodes:
                label = node.get("label", node["id"])
                source = node.get("source_file", "unknown")
                loc = node.get("source_location", "")
                comm = node.get("community", "unknown")
                lines.append(f"\nNode: {label}")
                lines.append(f"  file: {source} {loc}")
                lines.append(f"  community: {comm}")
                nb = graph.get_neighbors(node["id"])[:3]
                if nb:
                    lines.append("  connections:")
                    for edge in nb:
                        tgt = edge["node"]
                        rel = edge["relation"]
                        lines.append(f"    - {rel} → {tgt.get('label', tgt['id'])}")

    elif subcmd == "neighbors":
        target_id, target_node = _resolve_node(graph, arg)
        if not target_node:
            lines.append(f"Node not found: {arg}")
        else:
            label = target_node.get("label", target_id)
            lines.append(f"Graphify neighbors for '{label}':")
            lines.append(f"  file: {target_node.get('source_file', 'unknown')}")
            edges = graph.get_neighbors(target_id)
            if edges:
                lines.append("  connections:")
                for edge in edges[:10]:
                    tgt = edge["node"]
                    rel = edge["relation"]
                    lines.append(f"    - {rel} → {tgt.get('label', tgt['id'])} (file: {tgt.get('source_file', 'unknown')})")
            else:
                lines.append("  No connections found.")

    elif subcmd == "explain":
        target_id, target_node = _resolve_node(graph, arg)
        if not target_node:
            lines.append(f"Node not found: {arg}")
        else:
            label = target_node.get("label", target_id)
            lines.append(f"Graphify explanation for '{label}':")
            lines.append(f"  file: {target_node.get('source_file', 'unknown')}")
            lines.append(f"  location: {target_node.get('source_location', 'unknown')}")
            lines.append(f"  community: {target_node.get('community', 'unknown')}")

            edges = graph.get_neighbors(target_id)
            if edges:
                lines.append("  connections:")
                for edge in edges[:10]:
                    tgt = edge["node"]
                    rel = edge["relation"]
                    lines.append(f"    - {rel} → {tgt.get('label', tgt['id'])} (file: {tgt.get('source_file', 'unknown')})")

            hyper_matches = [h for h in graph._hyperedges if target_id in h.get("nodes", [])]
            if hyper_matches:
                lines.append("  participates in groups:")
                for h in hyper_matches:
                    lines.append(f"    - {h.get('label', h.get('id', 'unknown'))}")

    elif subcmd == "path":
        path_args = arg.split(None, 1)
        if len(path_args) < 2:
            lines.append("Usage: path <start> <end>")
        else:
            start_id, _ = _resolve_node(graph, path_args[0])
            end_id, _ = _resolve_node(graph, path_args[1])
            if not start_id:
                lines.append(f"Start node not found: {path_args[0]}")
            elif not end_id:
                lines.append(f"End node not found: {path_args[1]}")
            else:
                result = graph.get_path(start_id, end_id)
                if not result:
                    lines.append(f"No path found between {path_args[0]} and {path_args[1]}.")
                else:
                    lines.append(f"Graphify path from {path_args[0]} to {path_args[1]}:")
                    for node in result:
                        lines.append(f"  → {node.get('label', node['id'])} (file: {node.get('source_file', 'unknown')})")

    else:
        lines.append(f"Unknown graphify subcommand: {subcmd}")

    return "\n".join(lines)


def _demo() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(query_nodes("slack bot"))
    print("\n---\n")
    print(neighbors("chat_bot"))
    print("\n---\n")
    print(explain("chat_bot"))


if __name__ == "__main__":
    _demo()
