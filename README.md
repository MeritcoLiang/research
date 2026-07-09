# Thought-State Graph Orchestration Engine

本仓库是 **Thought-State Graph Orchestration Engine（思维状态图编排引擎）** 的工程落地区。当前实现目标已经进入 **Pipeline v0.3**：在 v0.2 的 mock runner、事件流、Web UI 和 trace graph 基础上，新增 LLM-backed operators 与结构化 JSON contracts。

项目的核心判断是：高质量 AI 回答不应该来自一次简单的 prompt-response 调用。每一个中间 thought 都应该被结构化、评分、改进、验证、聚合和记录。

## 当前目标：Pipeline v0.3

Pipeline v0.3 的目标不是推翻 v0.2，而是替换 operator 内部实现：

```text
v0.2: deterministic mock operators
v0.3: Prompter -> ModelClient -> JSON parser -> LLM-backed operators
```

保持不变的契约：

```text
ThoughtState
OperatorResult
PipelineController
Trace
TraceEvent
GraphSnapshot
```

新增能力：

```text
LLM-backed operators
  -> structured JSON contract parsers
  -> provider-neutral ModelClient
  -> ScriptedModelClient tests
  -> diversity-aware aggregation
  -> v0.3 demo adapter
```

当前 pipeline 阶段顺序仍然沿用 v0.1/v0.2：

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

> Web UI 输入 message 和 `python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"` 必须调用同一个 v0.2 runtime 入口。

第三条工程原则：

> v0.3 只替换 operator 内部模型调用，不破坏 v0.2 的 Trace / Event / Graph / Web UI 契约。

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
```

v0.3 LLM-backed runtime：

```python
tsgo.runtime.run_llm_pipeline_message(
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

Web UI message
  -> tsgo.web.sessions.SessionManager.handle_user_message
  -> tsgo.runtime.run_pipeline_message
  -> PipelineController
  -> mock operators
  -> Trace / TraceEvents / Graph

tests/demo_pipeline_v03.py
  -> tsgo.runtime.run_llm_pipeline_message
  -> PipelineController
  -> LLM-backed operators
  -> ModelClient / JSON contracts
  -> Trace / TraceEvents / Graph
```

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

- [架构说明](docs/architecture.md)
- [Pipeline v0.1](docs/pipeline-v0.1.md)
- [Pipeline v0.2](docs/pipeline-v0.2.md)
- [Pipeline v0.3](docs/pipeline-v0.3.md)
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
3. `PipelineController`：执行当前固定阶段顺序的控制器。
4. `Trace`：记录全部状态、评分、改进和验证结果的可回放轨迹。
5. `TraceEvent`：Web UI 和测试用于实时观察 pipeline 的事件。
6. `GraphSnapshot`：将 Trace 映射为前端可渲染的 nodes / edges。
7. `ModelClient`：v0.3 LLM-backed operators 的 provider-neutral 模型接口。
8. `run_pipeline_message()`：v0.2 mock runtime 入口。
9. `run_llm_pipeline_message()`：v0.3 LLM-backed runtime 入口。

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

当前状态：**Pipeline v0.3 LLM-backed operator scaffold 已落地**。

已经完成：

- v0.2 Web UI + event stream + trace graph
- `TraceEvent` 事件流
- `Trace -> GraphSnapshot` 转换
- 左到右语义流程图布局
- JSONL / JSON trace sinks
- `tests/demo_pipeline_v02.py` demo adapter
- `tests/demo_pipeline_v03.py` scripted LLM demo adapter
- `json_contracts.py` 结构化 JSON parser
- `llm_operators.py` LLM-backed operators
- `ScriptedModelClient` / `CallbackModelClient`
- diversity-aware aggregation
- mock pipeline、event stream、graph adapter、Web message equivalence、LLM pipeline 测试

尚未完成：

- 真实 provider client 集成，例如 OpenAI / Anthropic / 本地 HTTP 模型
- production-grade JSON repair
- 工具执行运行时
- learned verifier / reward model
- DAG / 任意图调度器

## 下一阶段

下一阶段是 **Pipeline v0.4**：

```text
Tool-aware verifier
  -> code execution hooks
  -> retrieval hooks
  -> citation verification hooks
  -> calculation hooks
  -> policy / safety checker hooks
```

v0.4 稳定后，系统可以继续演进为：

```text
linear pipeline -> DAG controller -> graph controller -> search policy engine -> learned verifier loop
```
