# 实施路线图

## 设计约束

从 v0.4 开始，路线收敛为“小而强”的工程系统，不做大而全兼容层。

硬约束：

1. **Agents SDK 优先**：如果 OpenAI Agents SDK 能满足需求，就不直接接入 Responses API。
2. **Structured output 强制**：能用 `output_type` / structured output，就不保留 prompt JSON fallback。
3. **模型范围收窄**：LLM 只兼容 OpenAI、Azure OpenAI、DeepSeek。
4. **不做通用 provider router**：不接入 Anthropic、Gemini、LiteLLM、Any-LLM、Ollama、vLLM、OpenRouter 等泛化适配。
5. **不做多套并行路径**：同一阶段只保留一条主路径，除非真实运行验证证明必须拆分。
6. **Prompter 降级为兼容层**：主路径使用 structured schema、Agent output type、tools 和 guardrails。

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

## v0.4：Agents SDK 主路径

目标：用 OpenAI Agents SDK 替换当前 LLM operator 内部的手写 model loop。

保留：

```text
PipelineController
ThoughtState
Trace
TraceEvent
GraphSnapshot
Web UI
```

替换：

```text
Prompter -> ModelClient -> parse_json
```

为：

```text
Agent -> Runner -> output_type -> structured result
```

只实现这些文件：

```text
src/tsgo/agents/runtime.py
src/tsgo/agents/operators.py
src/tsgo/agents/schemas.py
src/tsgo/agents/model_config.py
```

不做：

```text
providers/base.py
MultiProvider
LiteLLMProvider
AnyLLMProvider
LocalHTTPProvider
通用 provider capability matrix
```

## v0.5：三类模型接入

目标：只接入 OpenAI、Azure OpenAI、DeepSeek。

实现顺序：

1. `OpenAIAgentBackend`：默认路径，使用 Agents SDK 原生 OpenAI model。
2. `AzureOpenAIAgentBackend`：只在 Agents SDK 的内置 provider / OpenAI-compatible client 能满足时实现。
3. `DeepSeekAgentBackend`：仅作为 OpenAI-compatible endpoint 接入；如果 structured output 不稳定，就不进入主路径。

不接入其他模型。

## v0.6：Structured-only operators

目标：删除 prompt JSON fallback，把所有 v0.3 JSON parser 降级为测试兼容层。

每个 operator 必须有 Pydantic output schema：

```text
GenerateOutput
NormalizeOutput
ScoreOutput
ImproveOutput
AggregateOutput
ValidateOutput
```

如果某个后端不支持 structured output：

```text
该后端不支持这个阶段。
```

不再做：

```text
模型输出文本 -> 猜 JSON -> 修 JSON -> fallback prompt
```

## v0.7：最小工具系统

目标：只把 verifier 必需工具接入 Agents SDK function tools。

第一批工具只做：

```text
run_python_check
run_unit_tests
verify_citation
calculate
```

工具注册不做通用 marketplace，不做动态插件系统。

## v0.8：收敛后的 Thought-State Graph Engine

目标：在不扩大模型兼容面的情况下，把当前线性 pipeline 升级为可搜索图。

只做：

```text
beam search
best-first search
diversity-aware aggregation
trace replay
Web UI final lineage / full graph 切换
```

不做：

```text
MCTS 泛化框架
任意 workflow DSL
跨供应商模型竞价/路由
插件市场
```
