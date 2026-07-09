# 阶段索引

Pipeline v0.1 一共有 11 个阶段。每个阶段都有稳定契约，后续可以自然升级为完整 thought-state graph engine 中的一类节点。

| 阶段 | 文档 | 主要输出 |
| --- | --- | --- |
| 00 | [Task Intake](stages/00_task_intake.md) | `TaskInfo` |
| 01 | [Context Builder](stages/01_context_builder.md) | `ContextPacket` |
| 02 | [Rubric Builder](stages/02_rubric_builder.md) | `Rubric` |
| 03 | [Problem Decomposer](stages/03_problem_decomposer.md) | `Subtask[]` |
| 04 | [Candidate Generator](stages/04_candidate_generator.md) | generated `ThoughtState[]` |
| 05 | [Thought Normalizer](stages/05_thought_normalizer.md) | normalized `ThoughtState[]` |
| 06 | [Verifier / Scorer](stages/06_verifier_scorer.md) | scored `ThoughtState[]` |
| 07 | [Improver](stages/07_improver.md) | improved `ThoughtState[]` |
| 08 | [Aggregator](stages/08_aggregator.md) | aggregated `ThoughtState` |
| 09 | [Final Validator](stages/09_final_validator.md) | validated final `ThoughtState` |
| 10 | [Trace Logger](stages/10_trace_logger.md) | persisted `Trace` |

## 专家化 Instructions

- [SecondaryMarketAnalyst Stage Instructions](stage-instructions-secondary-market-analyst.md)：二级市场分析师专家 profile、handoff、10 个业务 Stage 的完整 instructions 设计。

## 跨阶段不变量

每个阶段都必须保留：

1. `user_query`
2. 通过 `id` 和 `parent_ids` 表示的状态谱系
3. 用户硬约束
4. trace metadata
5. 足够支持下游评分与聚合的结构化字段

## 阶段文档模板

每个阶段文档都遵循以下结构：

```text
目的
输入
输出
伪代码
失败模式
验收标准
```
