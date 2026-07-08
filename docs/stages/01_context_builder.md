# 01 Context Builder

## Purpose

Turn raw context into an explicit `ContextPacket`. This stage separates hard constraints, soft preferences, available evidence, missing information, and possible tool plans.

## Inputs

```text
user_query
TaskInfo
conversation_context
uploaded_files
retrieved_sources optional
tool_outputs optional
```

## Outputs

`ContextPacket`:

```text
user_intent
hard_constraints
soft_preferences
available_context
missing_context
retrieved_evidence
tool_plan
metadata
```

## Pseudocode

```python
def build_context(user_query: str, task_info: TaskInfo) -> ContextPacket:
    intent = infer_user_intent(user_query, task_info)
    hard_constraints = extract_hard_constraints(user_query)
    soft_preferences = extract_soft_preferences(user_query)

    evidence = collect_available_evidence(user_query, task_info)
    missing = detect_missing_context(user_query, task_info, evidence)
    tool_plan = plan_tools(task_info, missing)

    return ContextPacket(
        user_intent=intent,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        available_context=summarize_context(evidence),
        missing_context=missing,
        retrieved_evidence=evidence,
        tool_plan=tool_plan,
    )
```

## Failure modes

- Treats a soft preference as a hard constraint.
- Drops a hard constraint during summarization.
- Fails to flag missing information.
- Retrieves context but does not preserve source metadata.

## Acceptance criteria

- User intent is stated explicitly.
- Hard constraints are machine-readable.
- Missing context is not hidden.
- Evidence is carried forward with IDs so claims can reference it later.
