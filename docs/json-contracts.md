# JSON 契约

Pipeline v0.2 引入轻量 JSON parser，并为未来 LLM-backed operators 预留结构化输出契约。

v0.2 的 deterministic mock operators 不依赖 LLM 输出，但 prompt templates 已经明确要求模型返回 JSON。v0.3 接入真实模型时，应优先让每个 operator 返回以下结构。

## GenerateOperator

```json
{
  "branches": [
    {
      "draft": "候选答案正文",
      "strategy": "system_architect",
      "notes": []
    }
  ]
}
```

## NormalizeOperator

```json
{
  "summary": "候选答案摘要",
  "claims": [
    {
      "text": "原子 claim",
      "claim_type": "recommendation",
      "confidence": 0.72,
      "evidence_ids": [],
      "verifier_notes": []
    }
  ],
  "assumptions": [],
  "missing_info": [],
  "risks": []
}
```

## ScoreOperator

```json
{
  "scores": [
    {
      "state_id": "state_xxx",
      "correctness": 0.0,
      "completeness": 0.0,
      "relevance": 0.0,
      "clarity": 0.0,
      "groundedness": 0.0,
      "safety": 1.0,
      "actionability": 0.0,
      "overall": 0.0,
      "strengths": [],
      "weaknesses": [],
      "critical_errors": [],
      "improvement_instructions": []
    }
  ]
}
```

## ImproveOperator

```json
{
  "draft": "修复后的答案",
  "change_summary": [
    "修复了 verifier 指出的具体问题"
  ],
  "removed_claims": [],
  "added_claims": []
}
```

## AggregateOperator

```json
{
  "draft": "聚合后的最终候选答案",
  "selected_claims": [],
  "conflicts": [],
  "resolutions": [],
  "aggregation_policy": "claim_level_weighted_merge"
}
```

## ValidateOperator

```json
{
  "pass": true,
  "blocking_issues": [],
  "non_blocking_issues": [],
  "required_edits": [],
  "confidence": 0.86
}
```

## Parser 原则

`src/tsgo/parsing.py` 当前只做轻量处理：

- 支持直接 JSON；
- 支持 Markdown code fence 中的 JSON；
- 支持从文本中提取最外层 object / array；
- 不做复杂自动修复。

复杂 JSON repair 放到 v0.3 处理。
