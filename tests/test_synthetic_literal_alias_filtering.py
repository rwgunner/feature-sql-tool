from __future__ import annotations

from feature_sql_tool.graph.dependency_graph import DependencyGraph
from feature_sql_tool.graph.filter_only_classifier import FilterOnlyClassifier
from feature_sql_tool.graph.graph_classifier import GraphClassifier
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode


def test_classifiers_hide_synthetic_literal_aliases_from_set_branches() -> None:
    graph = DependencyGraph()
    final_id = 'fin:feature'

    graph.add_node(DependencyNode(final_id, 'final_feature', 'feature'))
    graph.add_node(
        DependencyNode(
            node_id='int:feature__scope_2:2',
            node_type='intermediate_feature',
            name='2',
            scope_name='feature__scope_2',
            expression_sql='2',
        )
    )
    graph.add_node(
        DependencyNode(
            node_id='int:feature__scope_2:__pos_3',
            node_type='intermediate_feature',
            name='__pos_3',
            scope_name='feature__scope_2',
            expression_sql='2',
        )
    )
    graph.add_node(
        DependencyNode(
            node_id='int:feature__scope_10:priority',
            node_type='intermediate_feature',
            name='priority',
            scope_name='feature__scope_10',
            expression_sql='1',
        )
    )
    graph.add_node(
        DependencyNode(
            node_id='int:feature__scope_11:rn',
            node_type='intermediate_feature',
            name='rn',
            scope_name='feature__scope_11',
            expression_sql='ROW_NUMBER() OVER (ORDER BY priority)',
        )
    )

    # Make every intermediate look filter-only to ensure the filter-only classifier
    # applies the same public-output cleanup as the intermediate classifier.
    for node_id in (
        'int:feature__scope_2:2',
        'int:feature__scope_2:__pos_3',
        'int:feature__scope_10:priority',
        'int:feature__scope_11:rn',
    ):
        graph.add_edge(
            DependencyEdge(
                from_node=node_id,
                to_node=final_id,
                dependency_type='filter',
                clause_type='where',
            )
        )

    intermediate = GraphClassifier().classify_intermediate_features(graph)
    filter_only = FilterOnlyClassifier().classify(graph, final_id)

    assert 'int:feature__scope_2:2' not in intermediate
    assert 'int:feature__scope_2:__pos_3' not in intermediate
    assert 'int:feature__scope_10:priority' in intermediate
    assert 'int:feature__scope_11:rn' in intermediate

    assert 'int:feature__scope_2:2' not in filter_only
    assert 'int:feature__scope_2:__pos_3' not in filter_only
    assert 'int:feature__scope_10:priority' in filter_only
    assert 'int:feature__scope_11:rn' in filter_only
