# 05 Thought Normalizer

## Purpose

Convert raw candidate drafts into structured thought states. This stage makes downstream scoring and aggregation reliable.

## Inputs

```text
Generated ThoughtState
ContextPacket
Rubric
```

## Outputs

Normalized `ThoughtState[]` with:

```text
summary
claims
assumptions
missing_info
failure_modes
status="normalized"
```

## Pseudocode

```python
def normalize_thought(candidate: ThoughtState, context: ContextPacket, rubric: Rubric) -> ThoughtState:
    prompt = build_normalization_prompt(
        draft=candidate.draft,
        context=context,
        rubric=rubric,
        required_schema={
            "summary": "string",
            "claims": "Claim[]",
            "assumptions": "string[]",
            "missing_info": "string[]",
            "risks": "string[]",
        },
    )
    raw = model.generate(prompt)
    parsed = parse_and_repair_json(raw)

    return ThoughtState(
        id=new_state_id("normalized"),
        parent_ids=[candidate.id],
        stage="thought_normalizer",
        user_query=candidate.user_query,
        task_type=candidate.task_type,
        draft=candidate.draft,
        summary=parsed.summary,
        claims=parsed.claims,
        assumptions=parsed.assumptions,
        missing_info=parsed.missing_info,
        failure_modes=parsed.risks,
        status="normalized",
        metadata={"source_candidate_id": candidate.id},
    )
```

## Normalization rules

- Claims should be atomic.
- Assumptions should be explicit.
- Unsupported claims should not be deleted yet; mark them for verification.
- Risks and uncertainty should be carried forward.

## Failure modes

- Summarizes away important details.
- Merges multiple claims into one vague claim.
- Fails to preserve original draft.
- Invents claims not present in the candidate.

## Acceptance criteria

- Every normalized state has at least a summary.
- Important candidate claims are represented as `Claim` objects.
- Parent lineage points back to the raw candidate.
- The original draft remains available.
