# 03 Problem Decomposer

## Purpose

Split the user request into smaller units that can be generated, scored, improved, and aggregated independently.

## Inputs

```text
user_query
TaskInfo
ContextPacket
Rubric
```

## Outputs

`list[Subtask]`:

```text
id
question
task_type
required_outputs
dependencies
metadata
```

## Pseudocode

```python
def decompose_problem(user_query: str, context: ContextPacket, rubric: Rubric) -> list[Subtask]:
    if is_simple_task(user_query):
        return [Subtask(id="s0", question=user_query, task_type="unknown")]

    candidate_subtasks = propose_subtasks(user_query, context, rubric)
    candidate_subtasks = remove_duplicates(candidate_subtasks)
    candidate_subtasks = order_by_dependency(candidate_subtasks)
    candidate_subtasks = enforce_coverage(candidate_subtasks, context.hard_constraints)

    return candidate_subtasks
```

## Decomposition rules

A good subtask should be:

- independently answerable;
- easy to verify;
- small enough to branch over;
- connected to one or more final answer sections;
- traceable to user intent.

## Failure modes

- Over-decomposes a simple request.
- Creates subtasks that cannot be independently verified.
- Drops a critical user constraint.
- Produces circular dependencies.

## Acceptance criteria

- Every subtask has a stable ID.
- Required outputs are explicit.
- Dependencies are explicit when needed.
- The union of subtasks covers the original request.
