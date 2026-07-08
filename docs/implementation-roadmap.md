# 实施路线图

## v0.1：设计脚手架

状态：已完成。

范围：

- README
- 架构文档
- 阶段文档
- 所有阶段的伪代码
- Python schema 骨架
- operator 接口骨架
- 确定性 pipeline controller 骨架
- 示例 trace 对象

## v0.2：具体 pipeline runner

状态：已完成 mock runner。

目标：跑通一个完整的 deterministic mock pipeline。

已完成：

1. 实现不依赖 LLM 的 deterministic mock operators。
2. 增加 `ModelClient` 接口和 `EchoModelClient`。
3. 增加结构化 JSON parser helper。
4. 将 prompter 风格的方法接入 stage operator 边界。
5. 将 trace 持久化为本地 JSONL。
6. 添加 mock pipeline 端到端单元测试。
7. 增加 CLI demo。

交付物：

```text
python -m tsgo.demo "user query"
```

返回一个可回放 trace，其中包含 generated、scored、improved、aggregated 和 validated states，并将 trace 写入 JSONL。

## v0.3：真实 LLM 集成

目标：用 LLM-backed operators 替换 mock operators。

任务：

1. 实现真实 `GenerateOperator`，支持 strategy-conditioned branching。
2. 实现真实 `NormalizeOperator`，负责结构化 claim 抽取。
3. 实现真实 `ScoreOperator`，按 rubric 输出多维评分。
4. 实现真实 `ImproveOperator`，基于 critique 做 targeted revision。
5. 实现真实 `AggregateOperator`，按 claim-level merge 输出最终答案。
6. 实现真实 `ValidateOperator`，作为发布门禁。
7. 强化 JSON parser / repair，确保 LLM 输出稳定落入 schema。
8. 增加 operator-level regression tests。

## v0.4：工具感知 verifier

目标：当纯语言验证不可靠时，引入外部工具。

任务：

- 代码执行 hooks
- 检索 hooks
- 引用验证 hooks
- 计算 hooks
- policy / safety checker hooks

## v0.5：DAG controller

目标：从固定线性 pipeline 升级到按任务定制的 DAG 执行。

任务：

- 显式 state graph store
- edge metadata
- 依赖感知 scheduler
- 按 subtask 分支
- top-k pruning

## v1.0：Thought-State Graph Orchestration Engine

目标：在 thought states 上进行任意图搜索。

能力：

- best-first search
- beam search
- MCTS-style expansion
- learned 或 hybrid verifier
- adaptive test-time compute
- trace-to-training-data export
