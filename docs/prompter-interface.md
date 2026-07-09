# Prompter 接口映射

当前研究脚手架采用一个 provider-neutral 的 prompter 抽象，包含五个 prompt 生成方法：

```text
generate_prompt(num_branches)
score_prompt(state_dicts)
improve_prompt()
aggregation_prompt(state_dicts)
validation_prompt()
```

这个接口来自原始 `prompter.py` 抽象，也正好对应 thought-state 编排中的五类核心操作：生成、评分、改进、聚合、验证。

## 映射关系

| Prompter 方法 | v0.3 Operator | 阶段 | 预期作用 |
| --- | --- | --- | --- |
| `generate_prompt(num_branches)` | `LLMCandidateGeneratorOperator` | 04 Candidate Generator | 生成多样化候选分支。 |
| `score_prompt(state_dicts)` | `LLMVerifierScorerOperator` | 06 Verifier / Scorer | 按 rubric 给一个或多个状态评分。 |
| `improve_prompt()` | `LLMImproverOperator` | 07 Improver | 根据 verifier critique 修复特定缺陷状态。 |
| `aggregation_prompt(state_dicts)` | `LLMAggregatorOperator` | 08 Aggregator | 按 claim 粒度合并 top states。 |
| `validation_prompt()` | `LLMFinalValidatorOperator` | 09 Final Validator | 判断最终状态是否可以发布。 |

`ThoughtNormalizerOperator` 目前没有放进 Prompter 抽象，因为原始 prompter 接口没有 normalization prompt；v0.3 在 `llm_operators.py` 内部构造 normalization prompt。

## 契约升级

Prompter 返回 prompt 字符串。Pipeline v0.3 会在字符串外层套上结构化契约：

```text
Prompter -> prompt string
ModelClient -> raw model output
json_contracts.py -> structured packet
Operator -> ThoughtState / OperatorResult
Trace -> replayable run record
```

这种分层让未来图引擎不依赖任何单一模型供应商或具体 prompt 模板。

## 必需的 parser 输出

每个 operator 都应该把模型输出解析成已知 schema：

```text
GenerateOperator -> candidate drafts
NormalizeOperator -> claims, assumptions, risks, missing info
ScoreOperator -> multi-dimensional score, critique, critical errors
ImproveOperator -> repaired draft and change summary
AggregateOperator -> final draft, selected claims, conflicts, resolutions
ValidateOperator -> pass/fail, blocking issues, required edits, confidence
```

## 设计说明

Prompter 应该只负责构造 prompt，不应该承担编排职责。编排层负责：

- 阶段顺序
- 分支策略
- state IDs
- parent lineage
- 阈值
- retry policy
- trace logging
- aggregation policy
