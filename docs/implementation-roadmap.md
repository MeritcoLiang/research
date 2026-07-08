# 实施路线图

## v0.1：设计脚手架

状态：已落地。

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

目标：跑通一个完整的 mock pipeline。

任务：

1. 实现不依赖 LLM 的确定性 mock operators，用于测试。
2. 增加 model-client 接口。
3. 增加结构化 JSON parser 与 repair 工具。
4. 将现有 prompter 风格的方法接入 stage operators。
5. 将 trace 持久化为本地 JSONL。
6. 为 state lineage 和 stage contracts 添加单元测试。

交付物：

```text
python -m tsgo.demo "user query"
```

返回一个可回放 trace，其中包含 generated、scored、improved、aggregated 和 validated states。

## v0.3：真实 LLM 集成

目标：用 LLM-backed operators 替换 mock operators。

任务：

1. 实现支持策略条件分支的 `GenerateOperator`。
2. 实现负责结构化 claim 抽取的 `NormalizeOperator`。
3. 实现 rubric-aware 的 `ScoreOperator`。
4. 实现基于 critique 修复的 `ImproveOperator`。
5. 实现 claim-level merge 的 `AggregateOperator`。
6. 实现发布门禁式 `ValidateOperator`。

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
