# Pipeline v0.2

Pipeline v0.2 的目标是把 v0.1 的设计脚手架升级为一个**可端到端运行的 mock pipeline**。

v0.2 仍然不接入真实 LLM，也不做任意图调度。它先验证工程闭环：Prompter 契约、ModelClient 边界、JSON parser、deterministic mock operators、Trace 持久化和 demo CLI。

## v0.2 目标

```text
Prompter integration
  -> structured JSON contracts
  -> mock model boundary
  -> deterministic operators
  -> trace persistence
  -> one end-to-end demo
```

## 新增模块

```text
src/tsgo/prompter.py       # Prompter 抽象与默认中文 prompt templates
src/tsgo/model_client.py   # ModelClient 协议与 EchoModelClient
src/tsgo/parsing.py        # JSON 解析与轻量提取工具
src/tsgo/trace_store.py    # JSONL / JSON trace sinks
src/tsgo/mock_operators.py # v0.2 deterministic operators
src/tsgo/demo.py           # CLI demo
```

## 运行方式

安装为 editable package 后运行：

```bash
pip install -e .
python -m tsgo.demo "进入 Pipeline v0.2"
```

输出示例：

```json
{
  "trace_id": "trace_xxx",
  "final_state_id": "validated_xxx",
  "final_status": "validated",
  "state_count": 50,
  "trace_path": "traces/pipeline_traces.jsonl",
  "final_draft_preview": "# Pipeline v0.2 聚合结果..."
}
```

也可以输出 pretty JSON trace：

```bash
python -m tsgo.demo "进入 Pipeline v0.2" \
  --trace-path traces/pipeline_traces.jsonl \
  --pretty-trace traces/latest_trace.json
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

## 为什么 v0.2 仍然使用 mock operators？

v0.2 的目标是验证编排契约，不是验证模型能力。先用 deterministic operators 可以确保：

- pipeline 不依赖外部 API key；
- trace 结构稳定；
- state lineage 可测试；
- demo 可以在本地和 CI 中稳定运行；
- v0.3 可以只替换 operator 内部实现，而不改 Controller / Schema。

## v0.2 验收标准

v0.2 完成时应满足：

1. `python -m tsgo.demo "query"` 可以端到端运行；
2. pipeline 返回 `Trace`；
3. trace 中包含 root、candidate、normalized、scored、aggregated、validated states；
4. trace 会被写入 JSONL；
5. final state 状态为 `validated`；
6. Prompter 接口被保留，后续可以替换为真实 LLM-backed operators；
7. tests 可以验证 mock pipeline 的端到端行为。

## v0.2 非目标

暂不实现：

- 真实 LLM API 调用；
- production-grade JSON repair；
- 工具调用 runtime；
- RAG；
- learned verifier；
- DAG / graph scheduler。

这些属于 v0.3 及之后的工作。
