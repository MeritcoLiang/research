# 实施路线图

## v0.1：设计脚手架

状态：已完成。

范围：

- README
- 架构文档
- 阶段文档
- 所有阶段的伪代码
- Python schema 骨架
- operator 接口骨架
- 确定性 pipeline controller 骨架
- 示例 trace 对象

## v0.2：具体 pipeline runner + Web UI adapter

状态：已完成。

目标：跑通一个完整的 deterministic mock pipeline，并让测试 demo 与 Web UI 输入 message 共享同一个 runtime。

已完成：

1. 实现不依赖 LLM 的 deterministic mock operators。
2. 增加 `ModelClient` 接口和 `EchoModelClient`。
3. 增加结构化 JSON parser helper。
4. 将 prompter 风格的方法接入 stage operator 边界。
5. 将 trace 持久化为本地 JSONL。
6. 增加 `TraceEvent` 事件流。
7. 增加 `Trace -> GraphSnapshot` 转换。
8. 将 demo adapter 移入 `tests/demo_pipeline_v02.py`。
9. 增加 FastAPI Web backend。
10. 增加 React + React Flow frontend 骨架。
11. 添加 mock pipeline、event stream、graph adapter、Web message equivalence 测试。

交付物：

```text
python tests/demo_pipeline_v02.py "user query"
```

和：

```text
uvicorn tsgo.web.app:app --reload
cd web && npm run dev
```

两条路径都调用：

```python
tsgo.runtime.run_pipeline_message(message)
```

## v0.3：LLM-backed operators

状态：已完成 scaffold。

目标：用 LLM-backed operators 替换 mock operators 的内部实现，同时保持 `ThoughtState / OperatorResult / Trace / TraceEvent / GraphSnapshot` 契约不变。

已完成：

1. 增加 `json_contracts.py`，用于解析 LLM JSON 输出。
2. 增加 `llm_operators.py`，包含 LLM-backed Generate / Normalize / Score / Improve / Aggregate / Validate。
3. 增加 `ScriptedModelClient` 和 `CallbackModelClient`，用于无 API key 的回归测试。
4. 增加 `build_v03_controller()` 和 `run_llm_pipeline_message()`。
5. 增加 `tests/demo_pipeline_v03.py`。
6. 增加 `tests/test_llm_pipeline.py`。
7. Aggregator 改为 diversity-aware top-k，避免只聚合第一个 subtask。
8. README 与 `docs/pipeline-v0.3.md` 已更新。

交付物：

```text
python tests/demo_pipeline_v03.py "进入 Pipeline v0.3" --num-branches 1
```

## v0.4：工具感知 verifier

目标：当纯语言验证不可靠时，引入外部工具。

任务：

- 代码执行 hooks
- 检索 hooks
- 引用验证 hooks
- 计算 hooks
- policy / safety checker hooks
- Web UI 中展示 tool call / tool output / verifier result

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
