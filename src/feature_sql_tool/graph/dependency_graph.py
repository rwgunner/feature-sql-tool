from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set

from feature_sql_tool.models.graph import DependencyEdge, DependencyNode


class DependencyGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, DependencyNode] = {}
        self.edges: List[DependencyEdge] = []
        self._upstream: Dict[str, Set[str]] = defaultdict(set)
        self._downstream: Dict[str, Set[str]] = defaultdict(set)

    def add_node(self, node: DependencyNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: DependencyEdge) -> None:
        self.edges.append(edge)
        self._upstream[edge.to_node].add(edge.from_node)
        self._downstream[edge.from_node].add(edge.to_node)

    def upstream(self, node_id: str) -> Set[str]:
        return self._upstream.get(node_id, set())

    def downstream(self, node_id: str) -> Set[str]:
        return self._downstream.get(node_id, set())

    def reachable_upstream(self, node_id: str) -> Set[str]:
        visited: Set[str] = set()
        stack = [node_id]

        while stack:
            current = stack.pop()
            for upstream_node in self.upstream(current):
                if upstream_node not in visited:
                    visited.add(upstream_node)
                    stack.append(upstream_node)

        return visited
