# 05 Thought Normalizer

## 目的

将原始 candidate drafts 转换为结构化 thought states。该阶段让后续评分和聚合更加可靠。

## 输入

```text
Generated ThoughtState
ContextPacket
Rubric
```

## 输出

规范化后的 `ThoughtState[]`，包含：

```text
summary
claims
assumptions
missing_info
failure_modes
status="normalized"
```

## 伪代码

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

## 规范化规则

- Claims 应该是原子化的。
- Assumptions 应该被显式记录。
- 暂时不要删除无依据 claims；先标记出来，交给 verifier 判断。
- Risks 和 uncertainty 必须向后传递。

## 失败模式

- 总结时丢掉重要细节。
- 把多个 claims 合并成一个含糊 claim。
- 没有保留原始 draft。
- 发明 candidate 中不存在的 claims。

## 验收标准

- 每个 normalized state 至少有 summary。
- candidate 的重要 claims 被表示为 `Claim` 对象。
- parent lineage 指回原始 candidate。
- 原始 draft 仍然可用。
