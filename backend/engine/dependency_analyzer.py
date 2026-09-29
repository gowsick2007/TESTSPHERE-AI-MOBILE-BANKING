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


def get_impacted_files(
    changed_files: List[str],
    graph: Optional[nx.DiGraph] = None,
    max_depth: int = 3
) -> Dict[str, Any]:
    """
    Locates direct, indirect, and transitive impacted files with depth-bounded traversal.
    Guarantees safe termination on cyclic and disconnected graphs.
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
                "has_cycles": False,
                "traversal_depth": 0,
                "visited_nodes": [],
                "missing_nodes": changed_files,
                "impacted_modules": [],
                "impact_reasons": {},
                "error": str(exc),
            }

    if graph.number_of_nodes() == 0:
        logger.warning("Dependency graph is empty — safe RUN applied")
        return {
            "direct": [],
            "indirect": [],
            "all_impacted": [],
            "graph_available": False,
            "has_cycles": False,
            "traversal_depth": 0,
            "visited_nodes": [],
            "missing_nodes": changed_files,
            "impacted_modules": [],
            "impact_reasons": {},
            "error": "Empty dependency graph",
        }

    # Detect cycles safely without infinite loops
    has_cycles = False
    try:
        has_cycles = not nx.is_directed_acyclic_graph(graph)
    except Exception:
        has_cycles = False

    direct: set[str] = set()
    indirect: set[str] = set()
    visited_nodes: set[str] = set()
    missing_nodes: list[str] = []
    impact_reasons: Dict[str, str] = {}
    impacted_modules: set[str] = set()
    max_depth_reached = 0

    for changed_file in changed_files:
        if changed_file not in graph:
            missing_nodes.append(changed_file)
            continue

        visited_nodes.add(changed_file)
        impact_reasons[changed_file] = "CHANGED_FILE"

        # Direct dependents (predecessors: who depends on this changed file)
        preds = set(graph.predecessors(changed_file))
        for p in preds:
            direct.add(p)
            visited_nodes.add(p)
            impact_reasons[p] = "DIRECT_DEPENDENCY_PREDECESSOR"
            max_depth_reached = max(max_depth_reached, 1)

        # Direct dependencies (successors: who does the changed file depend on)
        succs = set(graph.successors(changed_file))
        for s in succs:
            direct.add(s)
            visited_nodes.add(s)
            impact_reasons[s] = "DIRECT_DEPENDENCY_SUCCESSOR"
            max_depth_reached = max(max_depth_reached, 1)

        # Multi-hop transitive traversal with explicit depth limit and cycle guard
        if max_depth >= 2:
            # 2-hop predecessors
            for p in preds:
                for p2 in graph.predecessors(p):
                    if p2 not in direct and p2 != changed_file:
                        indirect.add(p2)
                        visited_nodes.add(p2)
                        impact_reasons[p2] = "INDIRECT_DEPENDENCY_DEPTH_2"
                        max_depth_reached = max(max_depth_reached, 2)
            # 2-hop successors
            for s in succs:
                for s2 in graph.successors(s):
                    if s2 not in direct and s2 != changed_file:
                        indirect.add(s2)
                        visited_nodes.add(s2)
                        impact_reasons[s2] = "INDIRECT_DEPENDENCY_DEPTH_2"
                        max_depth_reached = max(max_depth_reached, 2)

        # Bounded BFS traversal up to max_depth for transitive connections
        if max_depth >= 3:
            try:
                undirected = graph.to_undirected()
                lengths = nx.single_source_shortest_path_length(undirected, changed_file, cutoff=max_depth)
                for node, dist in lengths.items():
                    visited_nodes.add(node)
                    if node != changed_file and node not in direct:
                        if dist >= 2:
                            indirect.add(node)
                            max_depth_reached = max(max_depth_reached, dist)
                            if node not in impact_reasons:
                                impact_reasons[node] = f"TRANSITIVE_DEPENDENCY_DEPTH_{dist}"
            except Exception:
                pass

    # Extract impacted modules from edge attributes
    for node in visited_nodes:
        if node in graph:
            for _, _, data in graph.edges(node, data=True):
                mod = data.get("module")
                if mod:
                    impacted_modules.add(mod)
            for _, _, data in graph.in_edges(node, data=True):
                mod = data.get("module")
                if mod:
                    impacted_modules.add(mod)

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
        "has_cycles": has_cycles,
        "traversal_depth": max_depth_reached,
        "visited_nodes": sorted(list(visited_nodes)),
        "missing_nodes": sorted(missing_nodes),
        "impacted_modules": sorted(list(impacted_modules)),
        "impact_reasons": impact_reasons,
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
