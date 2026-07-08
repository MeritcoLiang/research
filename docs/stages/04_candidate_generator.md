# 04 Candidate Generator

## Purpose

Generate diverse candidate thought states. The goal is not to sample the same answer repeatedly; the goal is to explore different reasoning strategies with low error correlation.

## Inputs

```text
user_query
ContextPacket
Rubric
Subtask[]
num_branches
strategy set
```

## Outputs

Generated `ThoughtState[]` with:

```text
stage="candidate_generator"
draft
parent_ids
metadata.generation_strategy
metadata.branch_index
```

## Pseudocode

```python
def generate_candidates(user_query, context, rubric, subtask, num_branches):
    strategies = choose_strategies(subtask, num_branches)
    candidates = []

    for strategy in strategies:
        prompt = prompter.generate_prompt(
            num_branches=strategy.branch_count,
            user_query=user_query,
            context=context,
            rubric=rubric,
            subtask=subtask,
            strategy=strategy.name,
        )
        raw_outputs = model.generate(prompt)

        for branch_index, draft in enumerate(parse_branches(raw_outputs)):
            candidates.append(ThoughtState(
                id=new_state_id("candidate"),
                parent_ids=[subtask.id],
                stage="candidate_generator",
                user_query=user_query,
                task_type=subtask.task_type,
                draft=draft,
                metadata={
                    "generation_strategy": strategy.name,
                    "branch_index": branch_index,
                },
            ))

    return candidates
```

## Recommended strategies

```text
Direct expert answer
System architect answer
Implementation-first answer
Evaluation-first answer
Research scientist answer
Skeptical reviewer answer
Risk reviewer answer
Minimal MVP answer
```

## Failure modes

- Branches are stylistic variants rather than genuinely different strategies.
- High-temperature branches hallucinate unsupported claims.
- Candidate output is not parseable.
- Generation ignores rubric or context.

## Acceptance criteria

- Each candidate has parent lineage.
- Each candidate records its generation strategy.
- Branches cover complementary perspectives.
- Raw drafts are preserved for trace replay.
