# 08 Aggregator

## Purpose

Synthesize top states into a final candidate answer. Aggregation is claim-level and conflict-aware; it is not a paragraph concatenation step.

## Inputs

```text
Scored and improved ThoughtState[]
ContextPacket
Rubric
top_k_for_aggregation
```

## Outputs

Aggregated `ThoughtState` with:

```text
parent_ids=[top_state_ids]
draft
claims
metadata.conflicts
metadata.resolutions
status="aggregated"
```

## Pseudocode

```python
def aggregate_states(states: list[ThoughtState], context: ContextPacket, rubric: Rubric) -> ThoughtState:
    top_states = select_top_states(states)

    all_claims = extract_all_claims(top_states)
    unique_claims = deduplicate_claims(all_claims)
    conflict_groups = detect_conflicts(unique_claims)

    resolutions = []
    for conflict in conflict_groups:
        resolutions.append(resolve_conflict(
            conflict,
            priority=[
                "hard_constraints",
                "verifier_score",
                "evidence_strength",
                "actionability",
            ],
        ))

    final_claims = select_final_claims(unique_claims, resolutions, rubric)
    draft = synthesize_answer(final_claims, context, rubric)

    return ThoughtState(
        id=new_state_id("aggregated"),
        parent_ids=[state.id for state in top_states],
        stage="aggregator",
        user_query=top_states[0].user_query,
        task_type=top_states[0].task_type,
        draft=draft,
        claims=final_claims,
        status="aggregated",
        metadata={
            "aggregation_policy": "claim_level_weighted_merge",
            "conflicts": conflict_groups,
            "resolutions": resolutions,
        },
    )
```

## Conflict resolution priority

```text
1. User hard constraints
2. Verifier score
3. Evidence/tool validation
4. Engineering actionability
5. Clarity and concision
```

## Failure modes

- Merges low-quality claims because they sound useful.
- Averages conflicting recommendations instead of choosing.
- Produces a longer answer with more hallucinations.
- Loses uncertainty markers.

## Acceptance criteria

- Aggregated state has multiple parents.
- Conflicts are recorded.
- Low-confidence claims are removed or marked uncertain.
- Final answer structure follows user intent, not candidate order.
