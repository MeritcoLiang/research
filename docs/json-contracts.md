# JSON 契约

Pipeline v0.3 已经将 JSON 契约从“文档约定”升级为代码中的 parser 层：

```text
src/tsgo/parsing.py         # 负责 JSON 提取与基础解析
src/tsgo/json_contracts.py  # 负责 operator-level schema coercion
```

v0.3 的 LLM-backed operators 必须走以下路径：

```text
raw model output -> parse_json_object -> parse_*_packet -> ThoughtState / Score / validation metadata
```

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

Parser：

```python
parse_generate_packet(raw_text) -> list[str]
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

Parser：

```python
parse_normalize_packet(raw_text) -> dict
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

Parser：

```python
parse_score_packets(raw_text, weights=...) -> list[dict]
```

Score parser 支持两种匹配方式：

```text
优先按 state_id 匹配；
没有 state_id 时按返回顺序 fallback。
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

Parser：

```python
parse_improve_packet(raw_text) -> dict
```

## AggregateOperator

```json
{
  "draft": "聚合后的最终候选答案",
  "selected_claims": [],
  "conflicts": [],
  "resolutions": [],
  "aggregation_policy": "diversity_aware_claim_level_merge"
}
```

Parser：

```python
parse_aggregate_packet(raw_text) -> dict
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

Parser：

```python
parse_validation_packet(raw_text) -> dict
```

## Parser 原则

`src/tsgo/parsing.py`：

- 支持直接 JSON；
- 支持 Markdown code fence 中的 JSON；
- 支持从文本中提取最外层 object / array；
- 遇到不可解析内容时抛 `JsonParseError`。

`src/tsgo/json_contracts.py`：

- 将 score clamp 到 0..1；
- 将未知 `claim_type` fallback 到 `unknown`；
- 将 string / list 兼容为 `list[str]`；
- 将 claims coercion 成 `Claim` dataclass；
- 将 validation coercion 成发布门禁 metadata；
- 不做重型自动修复。

复杂 JSON repair、重试、模型自修复放到后续 v0.4+。
