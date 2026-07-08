# 04 Candidate Generator

## 目的

生成多样化的候选 thought states。目标不是重复采样同一个答案，而是探索错误相关性较低的不同推理策略。

## 输入

```text
user_query
ContextPacket
Rubric
Subtask[]
num_branches
strategy set
```

## 输出

生成的 `ThoughtState[]`，包含：

```text
stage="candidate_generator"
draft
parent_ids
metadata.generation_strategy
metadata.branch_index
```

## 伪代码

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

## 推荐生成策略

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

## 失败模式

- 分支只是文风差异，不是真正策略差异。
- 高温分支引入无依据幻觉。
- candidate output 无法解析。
- 生成过程忽略 rubric 或 context。

## 验收标准

- 每个 candidate 都有 parent lineage。
- 每个 candidate 都记录 generation strategy。
- 分支覆盖互补视角。
- raw drafts 被保留，支持 trace replay。
