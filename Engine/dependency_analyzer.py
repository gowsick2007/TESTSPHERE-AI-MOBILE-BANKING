"""
TestSphere AI — Dependency Analyzer
Uses NetworkX to traverse the dependency graph and find impacted files.
"""
import logging
from typing import Optional
import networkx as nx
from Engine.data_access import get_all_dependencies

logger = logging.getLogger(__name__)


_cached_graph: Optional[nx.DiGraph] = None


def clear_dependency_graph_cache():
    global _cached_graph
    _cached_graph = None


def build_dependency_graph(force_refresh: bool = False) -> nx.DiGraph:
    """
    Build a directed dependency graph from the database.
    Edges point from source_file → depends_on.
    """
    global _cached_graph
    if _cached_graph is not None and not force_refresh:
        return _cached_graph

    deps = get_all_dependencies()
    G = nx.DiGraph()
    for row in deps:
        src = row["source_file"]
        dep = row["depends_on"]
        G.add_edge(src, dep, module=row.get("module", ""), depth=row.get("depth", 1))
    
    _cached_graph = G
    return G


def get_impacted_files(changed_files: list[str], graph: Optional[nx.DiGraph] = None) -> dict:
    """
    Return files directly and indirectly impacted by `changed_files`.

    Strategy:
      - Direct dependents: files that directly depend on (or are depended upon by) a changed file
      - Indirect dependents: reachable via BFS up to depth 3
      - Also returns files the changed files themselves depend on

    Returns:
        dict with keys: direct, indirect, all_impacted, graph_available
    """
    if graph is None:
        try:
            graph = build_dependency_graph()
        except Exception as exc:
            logger.warning("Could not build dependency graph: %s — safe RUN applied", exc)
            return {
                "direct": [],
                "indirect": [],
                "all_impacted": [],
                "graph_available": False,
                "error": str(exc),
            }

    if graph.number_of_nodes() == 0:
        logger.warning("Dependency graph is empty — safe RUN applied")
        return {
            "direct": [],
            "indirect": [],
            "all_impacted": [],
            "graph_available": False,
            "error": "Empty dependency graph",
        }

    direct: set[str] = set()
    indirect: set[str] = set()

    for changed_file in changed_files:
        if changed_file not in graph:
            continue

        # Predecessors: files that depend on the changed file (reverse edges)
        preds = set(graph.predecessors(changed_file))
        direct.update(preds)
        # Who depends on changed_file's dependents? (2-hop)
        for p in preds:
            indirect.update(graph.predecessors(p))

        # What does the changed file depend on? (downstream)
        succs = set(graph.successors(changed_file))
        direct.update(succs)
        for s in succs:
            indirect.update(graph.successors(s))

        # BFS from changed_file in both directions
        try:
            undirected = graph.to_undirected()
            reachable = set(nx.single_source_shortest_path_length(undirected, changed_file, cutoff=3).keys())
            reachable.discard(changed_file)
            indirect.update(reachable - direct)
        except Exception:
            pass

    # Remove changed files themselves from results
    changed_set = set(changed_files)
    direct -= changed_set
    indirect -= changed_set
    indirect -= direct

    all_impacted = direct | indirect | changed_set

    return {
        "direct": sorted(direct),
        "indirect": sorted(indirect),
        "all_impacted": sorted(all_impacted),
        "graph_available": True,
        "error": None,
    }


def get_graph_data_for_visualization(changed_files: list[str]) -> dict:
    """Return nodes and edges for Plotly visualization."""
    graph = build_dependency_graph()
    impact = get_impacted_files(changed_files, graph)

    nodes = []
    edges = []
    changed_set = set(changed_files)
    direct_set = set(impact["direct"])
    indirect_set = set(impact["indirect"])

    for node in graph.nodes():
        if node in changed_set:
            status = "changed"
        elif node in direct_set:
            status = "direct_impact"
        elif node in indirect_set:
            status = "indirect_impact"
        else:
            status = "unaffected"
        nodes.append({"id": node, "label": node.split("/")[-1], "status": status})

    for src, dst in graph.edges():
        edges.append({"source": src, "target": dst})

    return {"nodes": nodes, "edges": edges, "impact": impact}


def has_dependency_path(file_a: str, file_b: str) -> bool:
    """Return True if there is any path between file_a and file_b in the graph."""
    try:
        graph = build_dependency_graph()
        undirected = graph.to_undirected()
        return nx.has_path(undirected, file_a, file_b)
    except (nx.exception.NetworkXError, nx.exception.NodeNotFound):
        return False
