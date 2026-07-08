# 08 Aggregator

## 目的

将 top states 综合成最终候选答案。Aggregation 是 claim 级、冲突感知的过程，不是简单拼接段落。

## 输入

```text
Scored and improved ThoughtState[]
ContextPacket
Rubric
top_k_for_aggregation
```

## 输出

聚合后的 `ThoughtState`，包含：

```text
parent_ids=[top_state_ids]
draft
claims
metadata.conflicts
metadata.resolutions
status="aggregated"
```

## 伪代码

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

## 冲突裁决优先级

```text
1. 用户硬约束
2. Verifier score
3. Evidence / tool validation
4. 工程可执行性
5. 清晰度与简洁度
```

## 失败模式

- 因为某个 claim 看起来有用，就把低质量 claim 合并进去。
- 对冲突建议做平均，而不是明确选择。
- 生成更长但 hallucination 更多的答案。
- 丢失 uncertainty 标记。

## 验收标准

- Aggregated state 有多个 parents。
- 冲突被记录下来。
- 低置信 claims 被删除或标记为不确定。
- 最终答案结构服从用户意图，而不是 candidate 顺序。
