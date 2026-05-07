from feature_sql_tool.graph.dependency_graph import DependencyGraph
from feature_sql_tool.graph.graph_classifier import GraphClassifier
from feature_sql_tool.graph.filter_only_classifier import FilterOnlyClassifier
from feature_sql_tool.models.graph import DependencyEdge, DependencyNode


def test_string_literal_only_nodes_are_hidden_but_semantic_aliases_remain():
    graph = DependencyGraph()
    graph.add_node(DependencyNode(
        node_id='fin:feature_x',
        node_type='final_feature',
        name='feature_x',
        scope_name='scope_final',
    ))
    graph.add_node(DependencyNode(
        node_id='int:feature__scope_1:FAILED_PAYMENT',
        node_type='intermediate_feature',
        name='FAILED_PAYMENT',
        scope_name='feature__scope_1',
        expression_sql="'FAILED_PAYMENT'",
    ))
    graph.add_node(DependencyNode(
        node_id='int:feature__scope_1:CHARGEBACK',
        node_type='intermediate_feature',
        name='CHARGEBACK',
        scope_name='feature__scope_1',
        expression_sql="'CHARGEBACK'",
    ))
    graph.add_node(DependencyNode(
        node_id='int:feature__scope_1:event_type',
        node_type='intermediate_feature',
        name='event_type',
        scope_name='feature__scope_1',
        expression_sql="'FAILED_PAYMENT'",
    ))
    graph.add_node(DependencyNode(
        node_id='int:feature__scope_1:event_weight',
        node_type='intermediate_feature',
        name='event_weight',
        scope_name='feature__scope_1',
        expression_sql='CASE WHEN channel = \'CASH\' THEN 2 ELSE 1 END',
    ))
    graph.add_edge(DependencyEdge(
        from_node='int:feature__scope_1:FAILED_PAYMENT',
        to_node='fin:feature_x',
        dependency_type='value',
        clause_type='select',
        scope_name='feature__scope_1',
    ))
    graph.add_edge(DependencyEdge(
        from_node='int:feature__scope_1:CHARGEBACK',
        to_node='fin:feature_x',
        dependency_type='filter',
        clause_type='where',
        scope_name='feature__scope_1',
    ))
    graph.add_edge(DependencyEdge(
        from_node='int:feature__scope_1:event_type',
        to_node='fin:feature_x',
        dependency_type='value',
        clause_type='select',
        scope_name='feature__scope_1',
    ))
    graph.add_edge(DependencyEdge(
        from_node='int:feature__scope_1:event_weight',
        to_node='fin:feature_x',
        dependency_type='value',
        clause_type='select',
        scope_name='feature__scope_1',
    ))

    intermediates = GraphClassifier().classify_intermediate_features(graph)

    assert 'int:feature__scope_1:FAILED_PAYMENT' not in intermediates
    assert 'int:feature__scope_1:CHARGEBACK' not in intermediates
    assert 'int:feature__scope_1:event_type' in intermediates
    assert 'int:feature__scope_1:event_weight' in intermediates

    filter_only = FilterOnlyClassifier().classify(graph, 'fin:feature_x')
    assert 'int:feature__scope_1:CHARGEBACK' not in filter_only
