from __future__ import annotations

from collections import defaultdict

from feature_sql_tool.graph.canonicalizer import NodeCanonicalizer
from feature_sql_tool.graph.unified_graph_builder import UnifiedFeatureGraph
from feature_sql_tool.models.reusable_subgraph import ReusableSubgraph


class ReusableSubgraphDetector:
    def __init__(self) -> None:
        self.canonicalizer = NodeCanonicalizer()

    def detect(self, unified_graph: UnifiedFeatureGraph) -> list[ReusableSubgraph]:
        groups = defaultdict(list)
        for node in unified_graph.nodes.values():
            if node.node_type not in {'source_column', 'intermediate_feature', 'aggregate_feature'}:
                continue
            groups[self.canonicalizer.canonical_key(node)].append(node)

        reusable: list[ReusableSubgraph] = []
        for idx, (signature, nodes) in enumerate(groups.items(), start=1):
            if len(nodes) < 2:
                continue
            node_type = nodes[0].node_type
            subgraph_type = 'computed_relation'
            if node_type == 'source_column':
                subgraph_type = 'base_relation'
            elif node_type == 'aggregate_feature':
                subgraph_type = 'aggregate_relation'
            reusable.append(
                ReusableSubgraph(
                    subgraph_id=f"reusable_{idx}",
                    subgraph_type=subgraph_type,
                    node_ids=[node.node_id for node in nodes],
                    signature=str(signature),
                    grain=nodes[0].grain,
                )
            )
        return reusable
