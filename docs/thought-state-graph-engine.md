# Thought-State Graph Orchestration Engine 主线

本项目的核心目标是 **Thought-State Graph Orchestration Engine**。

LLM、Agents SDK、structured output、tools、provider client 都只是 **Operator 的实现细节**。它们服务于图，不应该反过来主导系统设计。

## 核心对象

系统的中心对象是：

```text
ThoughtGraph
  nodes:
    ThoughtState
    Subtask
    ExpertProfile
  edges:
    handoff
    decomposes_to
    generates
    normalizes
    scores
    improves
    aggregates
    validates
    feedback
    tool
```

新增代码：

```text
src/tsgo/thought_graph.py
src/tsgo/engine.py
src/tsgo/experts/secondary_market.py
```

其中：

```python
ThoughtGraph.from_trace(trace)
```

负责把已有 pipeline trace 转成 canonical graph。

```python
ThoughtStateGraphEngine(controller).run(message)
```

负责把任意 controller 的运行结果提升为：

```python
GraphRunResult(trace, thought_graph)
```

## Stage Flow 已跑通的形态

SecondaryMarketAnalyst 当前已经按文档跑通：

```text
User Message
  -> Root ThoughtState
  -> ExpertRouter / handoff: SecondaryMarketAnalyst
  -> 01 Task Intake
  -> 02 Context Builder
  -> 03 Rubric Builder
  -> 04 Problem Decomposer
  -> 05 Candidate Generator
  -> 06 Thought Normalizer
  -> 07 Verifier / Scorer
  -> 08 Improver
  -> 09 Aggregator
  -> 10 Final Validator
  -> Trace / ThoughtGraph / GraphSnapshot
```

对应实时 UI 事件：

```text
pipeline_started
state_created(root)
expert_handoff
edge_created(root -> expert)
stage_started / stage_completed
subtask_created
edge_created(expert -> subtask)
state_created(candidate/normalized/scored/aggregation/validation)
score_updated
pipeline_completed
trace_persisted
```

## 为什么要这样修正

v0.3 引入 LLM Operators 后，路线有偏向“模型接入层”的风险。现在修正为：

```text
错误主线：Provider / Agents SDK / API compatibility first
正确主线：ThoughtGraph / state transitions / search policy / trace replay first
```

Agents SDK 的位置应该是：

```text
Agents SDK = 某些 Operator 的实现方式
```

而不是：

```text
Agents SDK = orchestration engine
```

## 分层

```text
Thought-State Graph Engine
  -> GraphController / SearchPolicy
  -> Operator
       - deterministic implementation
       - LLM implementation
       - Agents SDK implementation
       - tool-using implementation
  -> TraceEvent
  -> Web UI GraphSnapshot
```

这里没有 `OperatorBackend`、`AgentBackend`、`ModelBackend` 这类额外语义层。Operator 是唯一的执行语义。

## 当前状态

已经落地：

```text
ThoughtGraph
ThoughtEdge
ExpertProfile graph node
trace_to_thought_graph
GraphRunResult
ThoughtStateGraphEngine
run_pipeline_graph
run_llm_pipeline_graph
run_secondary_market_stage_flow
run_secondary_market_graph
```

这些让系统的输出不再只是 `Trace`，而是显式的 `ThoughtGraph`。

## 后续 v0.4 的真实目标

v0.4 不应该先做 provider 兼容，也不应该先做完整 Agents SDK 接入。

v0.4 应该先做：

```text
GraphController
Frontier selection
State expansion policy
Diversity-aware pruning
Final lineage extraction
Graph replay
Web UI final lineage / full graph toggle
```

只有当某个 Operator 需要真实模型执行时，才在该 Operator 内使用 Agents SDK structured output。

## 不做什么

不做：

```text
OperatorBackend / AgentBackend / ModelBackend
通用 provider router
多模型竞价
大而全工具市场
任意 workflow DSL
MCTS 泛化框架
跨供应商兼容层
```

保留的模型范围：

```text
OpenAI
Azure OpenAI
DeepSeek
```

但这些只是 Operator 的实现细节，不是主线。
