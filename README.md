# Thought-State Graph Orchestration Engine

本仓库是 **Thought-State Graph Orchestration Engine（思维状态图编排引擎）** 的工程落地区。当前实现目标已经进入 **Pipeline v0.2**：在 v0.1 的设计脚手架基础上，跑通 Prompter 契约、mock operators、JSON parser、trace 持久化、事件流、Web UI 和测试目录下的 demo adapter。

项目的核心判断是：高质量 AI 回答不应该来自一次简单的 prompt-response 调用。每一个中间 thought 都应该被结构化、评分、改进、验证、聚合和记录。

## 当前目标：Pipeline v0.2

Pipeline v0.2 暂时不接入真实 LLM，也不实现任意图调度。它先验证工程闭环：

```text
Prompter integration
  -> structured JSON contracts
  -> mock model boundary
  -> deterministic operators
  -> realtime trace events
  -> trace persistence
  -> test demo adapter
  -> Web UI adapter
```

当前 pipeline 阶段顺序仍然沿用 v0.1：

```text
User Query
  -> 00 Task Intake
  -> 01 Context Builder
  -> 02 Rubric Builder
  -> 03 Problem Decomposer
  -> 04 Candidate Generator
  -> 05 Thought Normalizer
  -> 06 Verifier / Scorer
  -> 07 Improver
  -> 08 Aggregator
  -> 09 Final Validator
  -> 10 Trace Logger
```

第一条工程原则：

> 每个阶段都消费结构化状态，并返回结构化状态。

第二条工程原则：

> Web UI 输入 message 和 `python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"` 必须调用同一个 runtime 入口。

## 快速运行

测试目录下的 demo adapter：

```bash
pip install -e .
python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
```

可选：输出 pretty JSON trace：

```bash
python tests/demo_pipeline_v02.py "进入 Pipeline v0.2" \
  --trace-path traces/pipeline_traces.jsonl \
  --pretty-trace traces/latest_trace.json
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

## 单一 runtime 入口

CLI demo 和 Web UI 都调用：

```python
tsgo.runtime.run_pipeline_message(message)
```

调用链：

```text
tests/demo_pipeline_v02.py
  -> tsgo.runtime.run_pipeline_message
  -> PipelineController
  -> mock operators
  -> Trace / TraceEvents

Web UI message
  -> tsgo.web.sessions.SessionManager.handle_user_message
  -> tsgo.runtime.run_pipeline_message
  -> PipelineController
  -> mock operators
  -> Trace / TraceEvents / Graph
```

因此两条路径的 pipeline 语义一致，差异只在输出介质：一个输出到 terminal，一个输出到 WebSocket + 实时流程图。

## 仓库结构

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── tsgo/
│       ├── __init__.py
│       ├── events.py
│       ├── graph.py
│       ├── mock_operators.py
│       ├── model_client.py
│       ├── operators.py
│       ├── parsing.py
│       ├── pipeline.py
│       ├── prompter.py
│       ├── runtime.py
│       ├── schema.py
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
│   ├── test_event_stream.py
│   ├── test_graph_adapter.py
│   ├── test_mock_pipeline.py
│   └── test_web_message_equivalence.py
└── web/
    ├── index.html
    ├── package.json
    ├── tsconfig.json
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

- [架构说明](docs/architecture.md)
- [Pipeline v0.1](docs/pipeline-v0.1.md)
- [Pipeline v0.2](docs/pipeline-v0.2.md)
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
2. `Operator`：把一个或多个状态转换成一个或多个状态的算子。
3. `PipelineController`：执行当前固定阶段顺序的 Pipeline v0.2 控制器。
4. `Trace`：记录全部状态、评分、改进和验证结果的可回放轨迹。
5. `TraceEvent`：Web UI 和测试用于实时观察 pipeline 的事件。
6. `GraphSnapshot`：将 Trace 映射为前端可渲染的 nodes / edges。
7. `run_pipeline_message()`：CLI demo 和 Web UI 共用的唯一 runtime 入口。

## Prompter 接口映射

现有 prompter 抽象可以直接映射到 pipeline：

| Prompter 方法 | Pipeline 阶段 | 作用 |
| --- | --- | --- |
| `generate_prompt(num_branches)` | 04 Candidate Generator | 分支扩展 |
| `score_prompt(state_dicts)` | 06 Verifier / Scorer | 多状态评估 |
| `improve_prompt()` | 07 Improver | 基于 critique 的修复 |
| `aggregation_prompt(state_dicts)` | 08 Aggregator | claim 级综合 |
| `validation_prompt()` | 09 Final Validator | 发布门禁 |

更详细的工程约定见 [Prompter 接口映射](docs/prompter-interface.md)。

## 开发状态

当前状态：**Pipeline v0.2 Web UI + event stream 设计已落地**。

已经完成：

- 所有阶段的中文文档
- Python schema / operator / pipeline controller 骨架
- Prompter 契约与默认 prompt templates
- ModelClient 边界与 EchoModelClient
- JSON parser helper
- deterministic mock operators
- JSONL / JSON trace sinks
- `TraceEvent` 事件流
- `Trace -> GraphSnapshot` 转换
- `tests/demo_pipeline_v02.py` demo adapter
- FastAPI Web backend
- React + React Flow Web frontend骨架
- mock pipeline、event stream、graph adapter、Web message equivalence 测试

尚未完成：

- 真实 model client 集成
- production-grade JSON repair
- 工具执行运行时
- learned verifier / reward model
- DAG / 任意图调度器

## 下一阶段

下一阶段是 **Pipeline v0.3**：

```text
LLM-backed operators
  -> structured JSON parser hardening
  -> scorer / improver / aggregator 真实模型接入
  -> trace-based evals
  -> operator-level regression tests
```

v0.3 稳定后，系统可以继续演进为：

```text
linear pipeline -> DAG controller -> graph controller -> search policy engine -> learned verifier loop
```
