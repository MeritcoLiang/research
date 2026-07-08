# 06 Verifier / Scorer

## 目的

使用任务专属 rubric 评估 normalized thought states。该阶段应该产出多维评分、critique、critical errors 和 improvement instructions。

## 输入

```text
Normalized ThoughtState[]
ContextPacket
Rubric
optional tool outputs
```

## 输出

评分后的 `ThoughtState[]`，包含：

```text
score
critique
failure_modes
claim verifier notes
status="scored"
```

## 伪代码

```python
def score_thoughts(states: list[ThoughtState], context: ContextPacket, rubric: Rubric) -> list[ThoughtState]:
    prompt = prompter.score_prompt(
        state_dicts=[state.to_dict() for state in states],
        context=context,
        rubric=rubric,
        scoring_schema={
            "correctness": "0..1",
            "completeness": "0..1",
            "relevance": "0..1",
            "clarity": "0..1",
            "groundedness": "0..1",
            "safety": "0..1",
            "actionability": "0..1",
            "overall": "0..1",
            "strengths": "string[]",
            "weaknesses": "string[]",
            "critical_errors": "string[]",
            "improvement_instructions": "string[]",
        },
    )
    raw = model.generate(prompt)
    score_packets = parse_scores(raw)

    scored = []
    for state, packet in zip(states, score_packets):
        scored.append(state_with_score_and_critique(state, packet))
    return scored
```

## 评分层级

```text
L1: deterministic rule checks
L2: LLM judge or reward model
L3: tool/environment validation when available
```

## 失败模式

- 只输出单一 overall score。
- 奖励冗长，而不是 correctness。
- 没有区分 critical errors 和 minor issues。
- 让 candidate 自己评判自己，缺少独立检查。

## 验收标准

- 分数是多维度的。
- Critique 是可执行的。
- Critical errors 被显式标记。
- 尽可能给每个 claim 附上 verifier notes。
- 同一套 rubric 后续可以被 aggregator 使用。
