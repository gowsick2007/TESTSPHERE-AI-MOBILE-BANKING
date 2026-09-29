"""
TestSphere AI — Dependency Graph Hardening Tests (Phase 2)
Verifies:
- Direct, indirect, and transitive dependency impact
- Cycle detection and safe termination (no infinite loops)
- Depth limits and traversal depth tracking
- Visited nodes and missing nodes tracking
- Impact reasons dictionary
- Disconnected and empty graph resilience
"""
import pytest
import networkx as nx

from backend.engine.dependency_analyzer import get_impacted_files


def test_acyclic_graph_traversal():
    """Verify standard acyclic dependency traversal with depth limits."""
    G = nx.DiGraph()
    # auth.py ➔ session.py ➔ token.py ➔ crypto.py
    G.add_edge("auth.py", "session.py", module="Authentication")
    G.add_edge("session.py", "token.py", module="Authentication")
    G.add_edge("token.py", "crypto.py", module="Security")

    res = get_impacted_files(["auth.py"], graph=G, max_depth=3)
    assert res["graph_available"] is True
    assert res["has_cycles"] is False
    assert "session.py" in res["direct"]
    assert "token.py" in res["indirect"]
    assert "crypto.py" in res["indirect"]
    assert res["traversal_depth"] >= 2
    assert "auth.py" in res["visited_nodes"]
    assert "session.py" in res["visited_nodes"]
    assert "Authentication" in res["impacted_modules"]
    assert "Security" in res["impacted_modules"]
    assert res["impact_reasons"]["auth.py"] == "CHANGED_FILE"
    assert "DIRECT_DEPENDENCY" in res["impact_reasons"]["session.py"]


def test_cyclic_graph_safe_termination():
    """Traversing a cyclic graph must safely terminate without infinite recursion."""
    G = nx.DiGraph()
    # Circular dependency: A ➔ B ➔ C ➔ A
    G.add_edge("moduleA.py", "moduleB.py", module="CircularMod")
    G.add_edge("moduleB.py", "moduleC.py", module="CircularMod")
    G.add_edge("moduleC.py", "moduleA.py", module="CircularMod")

    res = get_impacted_files(["moduleA.py"], graph=G, max_depth=3)
    assert res["graph_available"] is True
    assert res["has_cycles"] is True
    # Must terminate and include cycle members
    assert "moduleB.py" in res["direct"] or "moduleC.py" in res["direct"]
    assert len(res["all_impacted"]) == 3
    assert set(res["all_impacted"]) == {"moduleA.py", "moduleB.py", "moduleC.py"}
    assert res["error"] is None


def test_missing_nodes_and_disconnected_graph():
    """Files missing from graph or in disconnected components must be handled gracefully."""
    G = nx.DiGraph()
    G.add_edge("connected1.py", "connected2.py", module="Connected")
    G.add_node("isolated.py")

    res = get_impacted_files(["nonexistent.py", "isolated.py"], graph=G, max_depth=2)
    assert res["graph_available"] is True
    assert "nonexistent.py" in res["missing_nodes"]
    assert "isolated.py" in res["visited_nodes"]
    assert "isolated.py" in res["all_impacted"]
    assert len(res["direct"]) == 0
    assert len(res["indirect"]) == 0


def test_depth_limit_enforcement():
    """Depth limits must restrict transitive reachability."""
    G = nx.DiGraph()
    # A ➔ B ➔ C ➔ D
    G.add_edge("A.py", "B.py", module="Mod")
    G.add_edge("B.py", "C.py", module="Mod")
    G.add_edge("C.py", "D.py", module="Mod")

    # max_depth = 1: only direct dependents
    res_depth_1 = get_impacted_files(["A.py"], graph=G, max_depth=1)
    assert "B.py" in res_depth_1["direct"]
    assert "C.py" not in res_depth_1["indirect"]
    assert "D.py" not in res_depth_1["indirect"]

    # max_depth = 3: includes transitive
    res_depth_3 = get_impacted_files(["A.py"], graph=G, max_depth=3)
    assert "B.py" in res_depth_3["direct"]
    assert "C.py" in res_depth_3["indirect"]
    assert "D.py" in res_depth_3["indirect"]
