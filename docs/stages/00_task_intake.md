# 00 Task Intake

## Purpose

Classify the user request before spending heavy inference budget. This stage decides which downstream path should be used and how much test-time compute is justified.

## Inputs

```text
user_query
conversation_context optional
available_artifacts optional
```

## Outputs

`TaskInfo`:

```text
task_type
difficulty
requires_tools
requires_citations
requires_computation
requires_user_context
answer_format
metadata
```

## Pseudocode

```python
def task_intake(user_query: str) -> TaskInfo:
    signals = analyze_query(user_query)

    task_type = classify_task_type(signals)
    difficulty = estimate_difficulty(signals)

    return TaskInfo(
        user_query=user_query,
        task_type=task_type,
        difficulty=difficulty,
        requires_tools=detect_tool_need(signals),
        requires_citations=detect_citation_need(signals),
        requires_computation=detect_computation_need(signals),
        requires_user_context=detect_user_context_need(signals),
        answer_format=infer_answer_format(signals),
        metadata={"signals": signals},
    )
```

## Failure modes

- Misclassifies a research task as pure reasoning.
- Misses the need for citations or tools.
- Underestimates difficulty and allocates too few branches.
- Ignores explicit user constraints.

## Acceptance criteria

- The stage returns a structured `TaskInfo` object.
- Hard requirements in the user query are preserved.
- Downstream stages can choose branch count and verifier type from the result.
- Ambiguity is captured as metadata rather than silently discarded.
