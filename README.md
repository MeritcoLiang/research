# Thought-State Graph Orchestration Engine

本仓库是 **Thought-State Graph Orchestration Engine（思维状态图编排引擎）** 的工程落地区。当前主线已经修正为：**ThoughtGraph 是核心产物；LLM、Agents SDK、structured output、tools、provider client 都只是 Operator 的实现细节**。

项目的核心判断是：高质量 AI 回答不应该来自一次简单的 prompt-response 调用。每一个中间 thought 都应该被结构化、评分、改进、验证、聚合、记录，并进入可查询的 thought-state graph。

## 当前目标：Graph-first v0.3

v0.3 不只是 LLM Operator scaffold。现在已经补上核心图层：

```text
Trace -> ThoughtGraph -> GraphRunResult
```

主对象：

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

LLM Operators 仍然保留，但它们只是 Operator 的一种实现方式，不是系统主线。

## 工程原则

第一条：

> 每个 Operator 都消费结构化状态，并返回结构化状态。

第二条：

> Web UI 输入 message 和 `python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"` 必须调用同一个 v0.2 runtime 入口。

第三条：

> v0.3+ 的主产物是 `ThoughtGraph`，不是 prompt、provider、agent 或 API response。

第四条：

> Operator 是唯一的执行语义。LLM、Agents SDK、tools、rules 都只是 Operator 的实现方式。

第五条：

> Agents SDK 未来只用于实现某些 Operator；GraphController 才是 orchestration engine。

## 快速运行

v0.2 deterministic demo adapter：

```bash
pip install -e .
python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
```

v0.3 scripted LLM demo adapter：

```bash
pip install -e .
python tests/demo_pipeline_v03.py "进入 Pipeline v0.3" --num-branches 1
```

Graph-first runtime：

```python
from tsgo.runtime import run_pipeline_graph

result = run_pipeline_graph("进入 Pipeline v0.2")
thought_graph = result.thought_graph
```

Web UI 后端：

```bash
pip install -e '.[web]'
uvicorn tsgo.web.app:app --reload
```

Web UI 前端：

```bash
cd web
npm install
npm run dev
```

## Runtime 入口

v0.2 mock runtime：

```python
tsgo.runtime.run_pipeline_message(message)
tsgo.runtime.run_pipeline_graph(message)
```

v0.3 LLM runtime：

```python
tsgo.runtime.run_llm_pipeline_message(
    message,
    model_client=model_client,
)

tsgo.runtime.run_llm_pipeline_graph(
    message,
    model_client=model_client,
)
```

调用链：

```text
tests/demo_pipeline_v02.py
  -> tsgo.runtime.run_pipeline_message
  -> PipelineController
  -> mock operators
  -> Trace / TraceEvents
  -> ThoughtGraph 可选

Web UI message
  -> tsgo.web.sessions.SessionManager.handle_user_message
  -> tsgo.runtime.run_pipeline_message
  -> PipelineController
  -> mock operators
  -> Trace / TraceEvents / GraphSnapshot

tests/demo_pipeline_v03.py
  -> tsgo.runtime.run_llm_pipeline_message
  -> PipelineController
  -> LLM Operators
  -> ModelClient / JSON contracts
  -> Trace / TraceEvents
  -> ThoughtGraph 可选
```

## 仓库结构

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── tsgo/
│       ├── __init__.py
│       ├── engine.py
│       ├── events.py
│       ├── graph.py
│       ├── json_contracts.py
│       ├── llm_operators.py
│       ├── mock_operators.py
│       ├── model_client.py
│       ├── operators.py
│       ├── parsing.py
│       ├── pipeline.py
│       ├── prompter.py
│       ├── runtime.py
│       ├── schema.py
│       ├── thought_graph.py
│       ├── trace_store.py
│       └── web/
│           ├── __init__.py
│           ├── app.py
│           ├── event_bus.py
│           ├── schemas.py
│           └── sessions.py
├── docs/
│   ├── architecture.md
│   ├── event-stream.md
│   ├── json-contracts.md
│   ├── pipeline-v0.1.md
│   ├── pipeline-v0.2.md
│   ├── pipeline-v0.3.md
│   ├── stage-instructions-secondary-market-analyst.md
│   ├── thought-state-graph-engine.md
│   ├── web-ui.md
│   ├── implementation-roadmap.md
│   ├── prompter-interface.md
│   ├── stage-index.md
│   ├── pseudocode/
│   │   ├── pipeline_v0_1.md
│   │   └── operators.md
│   └── stages/
│       ├── 00_task_intake.md
│       ├── 01_context_builder.md
│       ├── 02_rubric_builder.md
│       ├── 03_problem_decomposer.md
│       ├── 04_candidate_generator.md
│       ├── 05_thought_normalizer.md
│       ├── 06_verifier_scorer.md
│       ├── 07_improver.md
│       ├── 08_aggregator.md
│       ├── 09_final_validator.md
│       └── 10_trace_logger.md
├── examples/
│   └── pipeline_trace_example.json
├── tests/
│   ├── demo_pipeline_v02.py
│   ├── demo_pipeline_v03.py
│   ├── test_event_stream.py
│   ├── test_graph_adapter.py
│   ├── test_llm_pipeline.py
│   ├── test_mock_pipeline.py
│   ├── test_thought_graph.py
│   └── test_web_message_equivalence.py
└── web/
    ├── index.html
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── style.css
        ├── types.ts
        ├── graph/eventReducer.ts
        └── components/
            ├── ChatPanel.tsx
            ├── EventTimeline.tsx
            ├── FlowCanvas.tsx
            └── StateInspector.tsx
```

## 文档入口

建议从这里开始阅读：

- [Thought-State Graph Engine 主线](docs/thought-state-graph-engine.md)
- [架构说明](docs/architecture.md)
- [Pipeline v0.1](docs/pipeline-v0.1.md)
- [Pipeline v0.2](docs/pipeline-v0.2.md)
- [Pipeline v0.3](docs/pipeline-v0.3.md)
- [SecondaryMarketAnalyst Stage Instructions](docs/stage-instructions-secondary-market-analyst.md)
- [Web UI 设计](docs/web-ui.md)
- [事件流设计](docs/event-stream.md)
- [JSON 契约](docs/json-contracts.md)
- [阶段索引](docs/stage-index.md)
- [Prompter 接口映射](docs/prompter-interface.md)
- [Pipeline 伪代码](docs/pseudocode/pipeline_v0_1.md)
- [Operator 伪代码](docs/pseudocode/operators.md)

## 核心抽象

当前实现使用这些核心抽象：

1. `ThoughtState`：一个候选答案、子答案、批评、修订、聚合结果或最终回复。
2. `Subtask`：问题拆解得到的子任务，也是 graph node。
3. `ThoughtEdge`：thought graph 的有向边。
4. `ThoughtGraph`：系统主产物，包含 states、subtasks、edges、root、final state。
5. `Operator`：唯一的执行语义；负责把输入状态转换成输出状态。
6. `GraphRunResult`：一次运行的 `Trace + ThoughtGraph`。
7. `PipelineController`：当前线性执行策略，后续会被 GraphController 替代或包裹。
8. `Trace`：记录全部状态、评分、改进和验证结果的可回放轨迹。
9. `TraceEvent`：Web UI 和测试用于实时观察 pipeline 的事件。
10. `GraphSnapshot`：将 Trace 映射为前端可渲染的 nodes / edges。
11. `ModelClient`：v0.3 LLM Operators 内部使用的临时辅助接口，不是 graph engine 主抽象。

## Prompter 接口映射

现有 prompter 抽象可以直接映射到 pipeline 的五类 thought 操作：

| Prompter 方法 | Pipeline 阶段 | 作用 |
| --- | --- | --- |
| `generate_prompt(num_branches)` | 04 Candidate Generator | 分支扩展 |
| `score_prompt(state_dicts)` | 06 Verifier / Scorer | 多状态评估 |
| `improve_prompt()` | 07 Improver | 基于 critique 的修复 |
| `aggregation_prompt(state_dicts)` | 08 Aggregator | claim 级综合 |
| `validation_prompt()` | 09 Final Validator | 发布门禁 |

Prompter 继续保留为兼容层，但主线是 `ThoughtGraph -> GraphController -> Operator`。

## 开发状态

当前状态：**ThoughtGraph core 已补齐，v0.3 主线已从 LLM 接入修正回 Graph Orchestration Engine**。

已经完成：

- v0.2 Web UI + event stream + trace graph
- `TraceEvent` 事件流
- `Trace -> GraphSnapshot` 转换
- 左到右语义流程图布局
- JSONL / JSON trace sinks
- `tests/demo_pipeline_v02.py` demo adapter
- `tests/demo_pipeline_v03.py` scripted LLM demo adapter
- `json_contracts.py` 结构化 JSON parser
- `llm_operators.py` LLM Operators
- `ThoughtGraph` / `ThoughtEdge` / `ThoughtStateGraphEngine`
- `run_pipeline_graph()` / `run_llm_pipeline_graph()`
- `tests/test_thought_graph.py`
- SecondaryMarketAnalyst 专家化 Stage instructions
- diversity-aware aggregation

尚未完成：

- GraphController
- frontier selection
- graph search policy
- Web UI final lineage / full graph 切换
- 使用 Agents SDK 实现部分 Operator
- OpenAI / Azure OpenAI / DeepSeek 最小模型接入
- 最小 verifier tools

## 下一阶段

下一阶段是 **v0.4 GraphController 主路径**：

```text
GraphController
  -> frontier selection
  -> state expansion policy
  -> diversity-aware pruning
  -> final lineage extraction
  -> graph replay
  -> Web UI final lineage / full graph toggle
```

Agents SDK 和模型接入在 v0.5+ 只作为 Operator 的实现方式引入，不再喧宾夺主。
