from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from feature_sql_tool.models.graph import DependencyNode
from feature_sql_tool.planner.canonicalizer import NodeCanonicalizer


class CommonSubgraphDetector:
    """A first-pass detector for identical source/intermediate nodes."""

    def __init__(self) -> None:
        self.canonicalizer = NodeCanonicalizer()

    def detect_reusable_nodes(self, nodes: Iterable[DependencyNode]) -> Dict[tuple, List[str]]:
        grouped = defaultdict(list)
        for node in nodes:
            key = self.canonicalizer.canonical_key(node)
            grouped[key].append(node.node_id)
        return {k: v for k, v in grouped.items() if len(v) > 1}
