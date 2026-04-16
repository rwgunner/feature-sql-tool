from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Set

from feature_sql_tool.models.graph import DependencyEdge, DependencyNode


class DependencyGraph:
    def __init__(self) -> None:
        self.nodes: Dict[str, DependencyNode] = {}
        self.edges: List[DependencyEdge] = []
        self._up = defaultdict(set)
        self._down = defaultdict(set)
        self._edges_by_pair = defaultdict(list)
        self._edge_keys = set()

    def add_node(self, node: DependencyNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: DependencyEdge) -> None:
        edge_key = (
            edge.from_node,
            edge.to_node,
            edge.dependency_type,
            edge.clause_type,
            edge.scope_name,
            edge.expression_sql,
        )
        if edge_key in self._edge_keys:
            return
        self._edge_keys.add(edge_key)
        self.edges.append(edge)
        self._up[edge.to_node].add(edge.from_node)
        self._down[edge.from_node].add(edge.to_node)
        self._edges_by_pair[(edge.from_node, edge.to_node)].append(edge)

    def upstream(self, node_id: str) -> Set[str]:
        return set(self._up.get(node_id, set()))

    def downstream(self, node_id: str) -> Set[str]:
        return set(self._down.get(node_id, set()))

    def edges_by_type(self, dependency_types: Iterable[str]) -> List[DependencyEdge]:
        allowed = set(dependency_types)
        return [e for e in self.edges if e.dependency_type in allowed]

    def reachable_upstream(self, node_id: str, dependency_types: Iterable[str] | None = None) -> Set[str]:
        allowed = None if dependency_types is None else set(dependency_types)
        visited: Set[str] = set()
        queue = deque([node_id])
        while queue:
            cur = queue.popleft()
            for prev in self.upstream(cur):
                if allowed is not None and not any(e.dependency_type in allowed for e in self._edges_by_pair[(prev, cur)]):
                    continue
                if prev not in visited:
                    visited.add(prev)
                    queue.append(prev)
        return visited

    def path_exists(self, start_node: str, end_node: str, allowed_types: Iterable[str]) -> bool:
        allowed = set(allowed_types)
        queue = deque([start_node])
        visited = {start_node}
        while queue:
            cur = queue.popleft()
            if cur == end_node:
                return True
            for nxt in self.downstream(cur):
                if nxt in visited:
                    continue
                if not any(e.dependency_type in allowed for e in self._edges_by_pair[(cur, nxt)]):
                    continue
                visited.add(nxt)
                queue.append(nxt)
        return False

    def path_exists_with_required_types(
        self,
        start_node: str,
        end_node: str,
        allowed_types: Iterable[str],
        required_types: Iterable[str],
    ) -> bool:
        allowed = set(allowed_types)
        required = set(required_types)
        queue = deque([(start_node, False)])
        visited = {(start_node, False)}

        while queue:
            cur, seen_required = queue.popleft()
            if cur == end_node and seen_required:
                return True

            for nxt in self.downstream(cur):
                edges = self._edges_by_pair[(cur, nxt)]
                edge_types = {e.dependency_type for e in edges}
                if not edge_types & allowed:
                    continue
                next_seen_required = seen_required or bool(edge_types & required)
                state = (nxt, next_seen_required)
                if state in visited:
                    continue
                visited.add(state)
                queue.append(state)
        return False
