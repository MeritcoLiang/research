# Thought-State Graph Orchestration Engine 主线

本项目的核心目标是 **Thought-State Graph Orchestration Engine**。

LLM、Agents SDK、structured output、tools、provider client 都是执行后端；它们服务于图，不应该反过来主导系统设计。

## 核心对象

v0.4 开始，系统的中心对象是：

```text
ThoughtGraph
  nodes:
    ThoughtState
    Subtask
  edges:
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

## 为什么要这样修正

v0.3 引入 LLM-backed operators 后，路线有偏向“模型接入层”的风险。现在修正为：

```text
错误主线：Provider / Agents SDK / API compatibility first
正确主线：ThoughtGraph / state transitions / search policy / trace replay first
```

Agents SDK 的位置应该是：

```text
Agent SDK = operator execution backend
```

而不是：

```text
Agent SDK = orchestration engine
```

## 分层

```text
Thought-State Graph Engine
  -> GraphController / SearchPolicy
  -> Operator
  -> Execution backend
       - deterministic mock
       - LLM-backed structured output
       - Agents SDK backend
       - minimal tools
  -> TraceEvent
  -> Web UI GraphSnapshot
```

## 当前状态

已经落地：

```text
ThoughtGraph
ThoughtEdge
trace_to_thought_graph
GraphRunResult
ThoughtStateGraphEngine
run_pipeline_graph
run_llm_pipeline_graph
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

只有当 operator 需要真实模型执行时，才接入 Agents SDK structured output。

## 不做什么

不做：

```text
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

但这些只是 execution backend，不是主线。
