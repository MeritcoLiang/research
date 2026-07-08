# Pipeline v0.2

Pipeline v0.2 的目标是把 v0.1 的设计脚手架升级为一个**可端到端运行、可观察、可通过 Web UI 实时绘图的 mock pipeline**。

v0.2 仍然不接入真实 LLM，也不做任意图调度。它先验证工程闭环：Prompter 契约、ModelClient 边界、JSON parser、deterministic mock operators、Trace 持久化、TraceEvent 事件流、GraphSnapshot 转换、测试目录 demo adapter 和 Web UI adapter。

## v0.2 目标

```text
Prompter integration
  -> structured JSON contracts
  -> mock model boundary
  -> deterministic operators
  -> realtime TraceEvents
  -> trace persistence
  -> tests/demo_pipeline_v02.py
  -> Web UI adapter
```

## 单一 runtime 入口

CLI demo 和 Web UI 必须调用同一个函数：

```python
tsgo.runtime.run_pipeline_message(message)
```

等价关系：

```text
Web UI 输入 message
  == python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
```

不要求 `trace_id`、`state_id`、timestamp 完全相同，因为它们天然随机；要求 stage shape、status shape、final status、final draft marker 和 event 存在性一致。

## 新增模块

```text
src/tsgo/runtime.py        # 唯一 runtime 入口
src/tsgo/events.py         # TraceEvent / EventSink
src/tsgo/graph.py          # Trace -> GraphSnapshot
src/tsgo/prompter.py       # Prompter 抽象与默认中文 prompt templates
src/tsgo/model_client.py   # ModelClient 协议与 EchoModelClient
src/tsgo/parsing.py        # JSON 解析与轻量提取工具
src/tsgo/trace_store.py    # JSONL / JSON trace sinks
src/tsgo/mock_operators.py # v0.2 deterministic operators
src/tsgo/web/              # FastAPI Web UI backend
web/                       # React + React Flow frontend
```

## 运行方式

测试目录下的 demo adapter：

```bash
pip install -e .
python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
```

输出示例：

```json
{
  "trace_id": "trace_xxx",
  "final_state_id": "validated_xxx",
  "final_status": "validated",
  "state_count": 50,
  "event_count": 180,
  "trace_path": "traces/pipeline_traces.jsonl",
  "final_draft_preview": "# Pipeline v0.2 聚合结果..."
}
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

## v0.2 执行流程

```text
TaskIntakeOperator
  -> ContextBuilderOperator
  -> RubricBuilderOperator
  -> ProblemDecomposerOperator
  -> CandidateGeneratorOperator
  -> ThoughtNormalizerOperator
  -> VerifierScorerOperator
  -> ImproverOperator
  -> AggregatorOperator
  -> FinalValidatorOperator
  -> TraceLoggerOperator
```

每个 operator 都返回 `OperatorResult`。生成、规范化、评分、改进、聚合、验证阶段会产出新的 `ThoughtState`，并保留 `parent_ids`。

PipelineController 会在关键节点发出 `TraceEvent`：

```text
pipeline_started
stage_started
state_created
edge_created
score_updated
stage_completed
pipeline_completed
pipeline_error
```

## 为什么 v0.2 仍然使用 mock operators？

v0.2 的目标是验证编排契约，不是验证模型能力。先用 deterministic operators 可以确保：

- pipeline 不依赖外部 API key；
- trace 结构稳定；
- state lineage 可测试；
- event stream 可测试；
- Web UI 可以实时绘制流程图；
- v0.3 可以只替换 operator 内部实现，而不改 Controller / Schema / Runtime。

## v0.2 验收标准

v0.2 完成时应满足：

1. `python tests/demo_pipeline_v02.py "query"` 可以端到端运行；
2. Web UI 输入 message 与测试 demo adapter 共享同一个 runtime；
3. pipeline 返回 `Trace`；
4. trace 中包含 root、candidate、normalized、scored、aggregated、validated states；
5. trace 会被写入 JSONL；
6. PipelineController 会发出 `TraceEvent`；
7. `Trace` 可以转换为 Graph nodes / edges；
8. final state 状态为 `validated`；
9. tests 可以验证 mock pipeline、event stream、graph adapter 和 Web message equivalence。

## v0.2 非目标

暂不实现：

- 真实 LLM API 调用；
- production-grade JSON repair；
- 工具调用 runtime；
- RAG；
- learned verifier；
- DAG / graph scheduler。

这些属于 v0.3 及之后的工作。
