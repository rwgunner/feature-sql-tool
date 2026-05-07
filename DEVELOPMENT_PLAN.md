# Development Plan 

Implemented in this archive:

1. Stronger scope registry with alias and relation metadata
2. Recursive `ColumnResolver` through CTE/subquery relations
3. Computed-vs-passthrough alias handling
4. `FeatureLineageExtractor` with recursive lineage and filter lineage collection
5. `FilterOnlyClassifier` based on graph path semantics
6. `UnifiedFeatureGraphBuilder` with canonical node merge
7. Safe multi-feature SQL planner that merges features with identical logical query shapes

Remaining extension ideas:

- cost-aware reuse across partially matching query shapes
- base-layer reuse when `FROM/JOIN/WHERE` matches but aggregate layer differs
- SQL rewriting for shared reusable filtered relations
- stronger support for complex UNION branches and window functions
