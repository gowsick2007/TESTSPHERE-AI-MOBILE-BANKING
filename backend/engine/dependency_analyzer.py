"""
TestSphere AI — Dependency Analyzer
Uses NetworkX to traverse the dependency graph and locate direct/indirect affected files.
"""
import logging
from typing import Optional, Dict, List, Any
import networkx as nx
from backend.engine.data_access import get_all_dependencies

logger = logging.getLogger(__name__)


_cached_graph: Optional[nx.DiGraph] = None


def clear_dependency_graph_cache():
    global _cached_graph
    _cached_graph = None


def build_dependency_graph(force_refresh: bool = False) -> nx.DiGraph:
    """
    Build directed dependency graph from database edges.
    Edges point from: source_file ➔ depends_on
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


def get_impacted_files(changed_files: List[str], graph: Optional[nx.DiGraph] = None) -> Dict[str, Any]:
    """
    Locates direct and indirect impacted files.
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

        # Direct dependents (reverse direction of dependencies: who depends on this changed file?)
        preds = set(graph.predecessors(changed_file))
        direct.update(preds)
        # Who depends on my dependents? (2-hop)
        for p in preds:
            indirect.update(graph.predecessors(p))

        # Direct dependencies (who does the changed file depend on?)
        succs = set(graph.successors(changed_file))
        direct.update(succs)
        # Who do my dependencies depend on? (2-hop)
        for s in succs:
            indirect.update(graph.successors(s))

        # BFS shortest path traversal for indirect impact (cutoff depth 3)
        try:
            undirected = graph.to_undirected()
            reachable = set(nx.single_source_shortest_path_length(undirected, changed_file, cutoff=3).keys())
            reachable.discard(changed_file)
            indirect.update(reachable - direct)
        except Exception:
            pass

    changed_set = set(changed_files)
    direct -= changed_set
    indirect -= changed_set
    indirect -= direct

    all_impacted = direct | indirect | changed_set

    return {
        "direct": sorted(list(direct)),
        "indirect": sorted(list(indirect)),
        "all_impacted": sorted(list(all_impacted)),
        "graph_available": True,
        "error": None,
    }


def get_graph_data_for_visualization(changed_files: List[str]) -> Dict[str, Any]:
    """Prepares structured Cytoscape/Plotly nodes/edges for the interactive UI graph."""
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

        # Check if the node is inside high risk module
        is_high_risk = False
        attrs = graph.nodes[node]
        # We can extract module info from adjacent edges
        mod = ""
        for n1, n2, e_data in graph.edges(node, data=True):
            mod = e_data.get("module", "")
            break
        if not mod:
            for n1, n2, e_data in graph.in_edges(node, data=True):
                mod = e_data.get("module", "")
                break

        nodes.append({
            "id": node,
            "label": node.split("/")[-1],
            "status": status,
            "module": mod
        })

    for src, dst in graph.edges():
        edges.append({"source": src, "target": dst})

    return {"nodes": nodes, "edges": edges, "impact": impact}


def has_dependency_path(file_a: str, file_b: str) -> bool:
    """Return True if any dependency path connects file_a and file_b."""
    try:
        graph = build_dependency_graph()
        undirected = graph.to_undirected()
        return nx.has_path(undirected, file_a, file_b)
    except (nx.exception.NetworkXError, nx.exception.NodeNotFound):
        return False
