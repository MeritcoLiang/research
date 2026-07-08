# Thought-State Graph Orchestration Engine

本仓库是 **Thought-State Graph Orchestration Engine（思维状态图编排引擎）** 的工程落地区。当前实现目标已经进入 **Pipeline v0.2**：在 v0.1 的设计脚手架基础上，跑通 Prompter 契约、mock operators、JSON parser、trace 持久化和 demo CLI。

项目的核心判断是：高质量 AI 回答不应该来自一次简单的 prompt-response 调用。每一个中间 thought 都应该被结构化、评分、改进、验证、聚合和记录。

## 当前目标：Pipeline v0.2

Pipeline v0.2 暂时不接入真实 LLM，也不实现任意图调度。它先验证工程闭环：

```text
Prompter integration
  -> structured JSON contracts
  -> mock model boundary
  -> deterministic operators
  -> trace persistence
  -> one end-to-end demo
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

## 快速运行

```bash
pip install -e .
python -m tsgo.demo "进入 Pipeline v0.2"
```

可选：输出 pretty JSON trace：

```bash
python -m tsgo.demo "进入 Pipeline v0.2" \
  --trace-path traces/pipeline_traces.jsonl \
  --pretty-trace traces/latest_trace.json
```

运行后会输出 `trace_id`、`final_state_id`、`final_status`、`state_count` 和最终 draft 预览，并将完整 trace 追加写入 JSONL。

## 为什么要这样做

“多生成几个答案再合并”是有价值的，但还不够。更强的系统设计应该是：

```text
生成多样化候选
  -> 规范化为 claims / assumptions / risks
  -> 用任务专属 rubric 评分
  -> 只改进有潜力但有缺陷的状态
  -> 按 claim 粒度聚合
  -> 发布前做最终验证
  -> 记录完整 trace，用于调试、评测和未来训练数据
```

这样可以为以下能力打基础：

- 自适应 test-time compute
- claim 级验证
- 冲突感知聚合
- 可复现回答轨迹
- 未来的 beam search、best-first search、MCTS 和任意 thought graph 搜索策略

## 仓库结构

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── tsgo/
│       ├── __init__.py
│       ├── demo.py
│       ├── mock_operators.py
│       ├── model_client.py
│       ├── operators.py
│       ├── parsing.py
│       ├── pipeline.py
│       ├── prompter.py
│       ├── schema.py
│       └── trace_store.py
├── docs/
│   ├── architecture.md
│   ├── pipeline-v0.1.md
│   ├── pipeline-v0.2.md
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
└── tests/
    └── test_mock_pipeline.py
```

## 文档入口

每个阶段都有独立文档，包含：

- 目的
- 输入
- 输出
- 伪代码
- 失败模式
- 验收标准

建议从这里开始阅读：

- [架构说明](docs/architecture.md)
- [Pipeline v0.1](docs/pipeline-v0.1.md)
- [Pipeline v0.2](docs/pipeline-v0.2.md)
- [阶段索引](docs/stage-index.md)
- [Prompter 接口映射](docs/prompter-interface.md)
- [Pipeline 伪代码](docs/pseudocode/pipeline_v0_1.md)
- [Operator 伪代码](docs/pseudocode/operators.md)

## 核心抽象

当前实现使用四个核心抽象：

1. `ThoughtState`：一个候选答案、子答案、批评、修订、聚合结果或最终回复。
2. `Operator`：把一个或多个状态转换成一个或多个状态的算子。
3. `PipelineController`：执行当前固定阶段顺序的 Pipeline v0.2 控制器。
4. `Trace`：记录全部状态、评分、改进和验证结果的可回放轨迹。

v0.2 新增运行时边界：

- `Prompter`：只负责构造 prompt，不负责编排。
- `ModelClient`：后续真实 LLM 接入点。
- `JsonlTraceSink` / `JsonTraceSink`：trace 持久化。
- `build_mock_operators()`：deterministic mock pipeline operator set。
- `run_demo()`：端到端 demo 入口。

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

当前状态：**Pipeline v0.2 mock runner 已落地**。

已经完成：

- 所有阶段的中文文档
- 所有阶段的伪代码
- Python schema 骨架
- operator 接口骨架
- 确定性 pipeline controller 骨架
- Prompter 契约与默认 prompt templates
- ModelClient 边界与 EchoModelClient
- JSON parser helper
- deterministic mock operators
- JSONL / JSON trace sinks
- `python -m tsgo.demo` 端到端 demo
- mock pipeline 单元测试

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
