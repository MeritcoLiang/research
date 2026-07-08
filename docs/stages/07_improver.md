# 07 Improver

## Purpose

Repair promising but flawed states using verifier feedback. This stage should not freely regenerate the answer; it should make targeted changes that preserve correct content and fix identified weaknesses.

## Inputs

```text
Scored ThoughtState[]
ContextPacket
Rubric
improvement thresholds
max_improvement_rounds
```

## Outputs

Improved `ThoughtState[]` with:

```text
parent_ids=[original_state.id]
draft
critique
metadata.improvement_round
status="improved"
```

## Pseudocode

```python
def improve_states(states: list[ThoughtState], context: ContextPacket, rubric: Rubric) -> list[ThoughtState]:
    improved = []

    for state in states:
        if not should_improve(state):
            continue

        prompt = prompter.improve_prompt(
            state=state.to_dict(),
            rubric=rubric,
            context=context,
            instructions={
                "preserve_correct_content": True,
                "fix_only_verifier_issues": True,
                "remove_unsupported_claims": True,
                "do_not_introduce_unverified_new_claims": True,
            },
        )
        raw = model.generate(prompt)
        repaired = parse_improved_state(raw)

        improved.append(ThoughtState(
            id=new_state_id("improved"),
            parent_ids=[state.id],
            stage="improver",
            user_query=state.user_query,
            task_type=state.task_type,
            draft=repaired.draft,
            critique=repaired.change_summary,
            status="improved",
            metadata={"improvement_round": state.metadata.get("improvement_round", 0) + 1},
        ))

    return improved
```

## Improve decision

```python
def should_improve(state):
    return (
        state.score.overall < MIN_OVERALL_SCORE
        and state.score.relevance >= MIN_RELEVANCE
        and state.score.safety >= MIN_SAFETY
        and has_actionable_critique(state)
        and not has_unrecoverable_critical_error(state)
    )
```

## Failure modes

- Rewrites from scratch and loses good content.
- Adds new unsupported claims.
- Improves style but not correctness.
- Loops indefinitely.

## Acceptance criteria

- Improvement has parent lineage.
- Changes map to verifier feedback.
- Correct content is preserved.
- Repaired states are re-normalized and re-scored before aggregation.
