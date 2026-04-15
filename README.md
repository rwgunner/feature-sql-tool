# feature-sql-tool

Updated iteration of `feature-sql-tool` focused on:

- recursive column resolution through CTEs and scope aliases
- computed-vs-passthrough alias classification
- intermediate feature extraction
- `filter_only_intermediate_features` classification through graph reachability
- multi-feature unified graph building
- safe SQL optimization by merging features with identical logical query shape

## Current scope

This package is an updated implementation scaffold with working core logic for:

- scope parsing
- recursive lineage for one feature
- `filter_only` classification
- safe grouping of multiple feature queries into shared aggregate CTEs when their `WITH/FROM/JOIN/WHERE/GROUP/HAVING/QUALIFY` signatures are identical

## Notes

The optimizer intentionally uses **safe reuse only**. It merges features only when their normalized query shape matches exactly.
