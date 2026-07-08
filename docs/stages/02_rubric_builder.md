# 02 Rubric Builder

## Purpose

Create the objective function before candidates are generated. The rubric prevents the scorer and aggregator from being anchored by the first draft.

## Inputs

```text
user_query
TaskInfo
ContextPacket
```

## Outputs

`Rubric`:

```text
items: list[RubricItem]
hard_constraints
soft_preferences
```

## Pseudocode

```python
def build_rubric(user_query: str, task_info: TaskInfo, context: ContextPacket) -> Rubric:
    if task_info.task_type == "coding":
        items = coding_rubric()
    elif task_info.task_type == "research":
        items = research_rubric()
    elif task_info.task_type == "reasoning":
        items = reasoning_rubric()
    else:
        items = general_answer_quality_rubric()

    items = adapt_weights(items, difficulty=task_info.difficulty, intent=context.user_intent)

    return Rubric(
        items=items,
        hard_constraints=context.hard_constraints,
        soft_preferences=context.soft_preferences,
    )
```

## Default general rubric

```text
correctness: 0.30
completeness: 0.20
actionability: 0.20
groundedness: 0.15
clarity: 0.10
risk_control: 0.05
```

## Failure modes

- Generates a generic rubric that ignores task type.
- Gives too much weight to style and too little to correctness.
- Does not include hard constraints.
- Creates criteria that cannot be scored.

## Acceptance criteria

- Rubric exists before candidate generation.
- Weights sum to a sensible objective.
- Hard constraints are included.
- Scorer and aggregator can consume the same rubric.
