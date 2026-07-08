# Prompter 接口映射

当前研究脚手架假设存在一个 prompter 抽象，包含五个 prompt 生成方法：

```text
generate_prompt(num_branches)
score_prompt(state_dicts)
improve_prompt()
aggregation_prompt(state_dicts)
validation_prompt()
```

Pipeline v0.1 将这些方法视为 thought-state operators 的 prompt-level 适配器。

## 映射关系

| Prompter 方法 | Operator | 阶段 | 预期作用 |
| --- | --- | --- | --- |
| `generate_prompt(num_branches)` | `GenerateOperator` | 04 Candidate Generator | 生成多样化候选分支。 |
| `score_prompt(state_dicts)` | `ScoreOperator` | 06 Verifier / Scorer | 按 rubric 给一个或多个状态评分。 |
| `improve_prompt()` | `ImproveOperator` | 07 Improver | 根据 verifier critique 修复特定缺陷状态。 |
| `aggregation_prompt(state_dicts)` | `AggregateOperator` | 08 Aggregator | 按 claim 粒度合并 top states。 |
| `validation_prompt()` | `ValidateOperator` | 09 Final Validator | 判断最终状态是否可以发布。 |

## 契约升级

Prompter 返回字符串。Pipeline v0.1 会在字符串外层套上结构化契约：

```text
Prompter -> prompt string
ModelClient -> raw model output
Parser -> structured packet
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
