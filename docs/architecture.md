# 架构说明

长期目标是构建一个 **Thought-State Graph Orchestration Engine（思维状态图编排引擎）**。当前仓库先落地第一层稳定工程基础：**Pipeline v0.1**。

Pipeline v0.1 暂时不是完整图引擎。它是一个确定性的编排脚手架，用来保证每个中间 thought 都可以被结构化、评分、改进、聚合和追踪。

## 设计原则

```text
不要在阶段之间传递裸字符串。
要传递 ThoughtState 对象。
```

裸字符串很难被可靠评分、合并、回放，也很难转成训练数据。结构化状态则可以。

## 系统分层

```text
Application / User Request
  -> PipelineController
  -> Operators
  -> Prompter / Model Client / Tool Runtime
  -> Structured Parser
  -> ThoughtState / Trace Store
```

## 核心对象

### ThoughtState

`ThoughtState` 是编排的原子单元。它可以表示：

- root 用户请求
- 被拆解的子答案
- 生成的候选答案
- 规范化后的 thought
- 评分后的 thought
- 改进后的 thought
- 聚合结果
- 最终验证后的回复

每个状态都包含：

```text
id
parent_ids
stage
user_query
draft
claims
assumptions
evidence
score
critique
status
metadata
```

### Operator

`Operator` 将一个或多个状态转换为一个或多个状态。

示例：

```text
GenerateOperator: root/subtask -> candidate states
NormalizeOperator: candidate -> structured claims
ScoreOperator: normalized states -> scored states
ImproveOperator: flawed state -> improved state
AggregateOperator: top states -> aggregated state
ValidateOperator: aggregated state -> validated final state
```

### Trace

`Trace` 是完整运行过程的可回放记录，是以下能力的基础：

- 调试
- 回归测试
- evals
- prompt 优化
- 未来的 SFT / DPO / RL 数据生成

## 演进路线

```text
Pipeline v0.1
  -> 接入具体 prompter 的 Pipeline v0.2
  -> DAG controller
  -> 任意 thought-state graph
  -> search policy engine
  -> learned verifier / reward model loop
```

关键点是：先稳定 state、operator contract 和 trace logging，再增加图搜索复杂度。

## v0.1 非目标

Pipeline v0.1 暂不实现：

- 任意图调度
- MCTS
- learned reward model
- 外部工具运行时
- 生产级 model client
- 持久化存储层

这些属于后续里程碑。
