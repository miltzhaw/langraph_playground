# Causal DAG Summary

**Events:** 17 | **Causal Edges:** 13

## Events by Type

| Event Type | Count | Agents |
|---|---|---|
| GOAL_COMPLETED | 2 | analyzer, summarizer |
| GOAL_CREATED | 4 | analyzer, classifier, coordinator, summarizer |
| GOAL_FAILED | 2 | classifier, coordinator |
| REASONING_STEP | 6 | analyzer, classifier, coordinator, summarizer |
| TOOL_INVOKED | 3 | analyzer, classifier, summarizer |

## Causal Edges by Reason

| Reason | Count |
|---|---|
| inferred_by_proximity | 7 |
| intra_agent_sequence | 6 |