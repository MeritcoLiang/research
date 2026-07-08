# 07 Improver

## 目的

根据 verifier feedback 修复有潜力但有缺陷的 states。该阶段不应该自由重写答案，而应该做有针对性的修改：保留正确内容，修复已识别问题。

## 输入

```text
Scored ThoughtState[]
ContextPacket
Rubric
improvement thresholds
max_improvement_rounds
```

## 输出

改进后的 `ThoughtState[]`，包含：

```text
parent_ids=[original_state.id]
draft
critique
metadata.improvement_round
status="improved"
```

## 伪代码

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

## 改进决策

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

## 失败模式

- 从头重写，丢失原本正确内容。
- 增加新的无依据 claims。
- 只改进文风，没有改进 correctness。
- 无限循环。

## 验收标准

- 改进状态有 parent lineage。
- 修改能映射到 verifier feedback。
- 正确内容被保留。
- 修复后的状态进入 aggregation 前会重新 normalize 和 score。
