# Pipeline v0.3

Pipeline v0.3 的目标是把 v0.2 的 deterministic mock operators 升级为 **LLM-backed operators**，同时保持 v0.2 已经稳定的状态、事件、图和 trace 契约。

v0.3 的关键原则：

```text
替换 operator 内部实现，不替换 orchestration contract。
```

也就是说：

```text
PipelineController / ThoughtState / OperatorResult / Trace / TraceEvent / GraphSnapshot
```

这些外层契约保持不变，变化只发生在 operator 内部：从 deterministic mock 逻辑变成 `Prompter -> ModelClient -> JSON parser -> ThoughtState`。

## v0.3 新增模块

```text
src/tsgo/json_contracts.py   # LLM JSON 输出解析与 schema coercion
src/tsgo/llm_operators.py    # LLM-backed Generate / Normalize / Score / Improve / Aggregate / Validate
src/tsgo/model_client.py     # ScriptedModelClient / CallbackModelClient，用于测试与本地验证
```

## Runtime 入口

v0.2 入口仍然保留：

```python
tsgo.runtime.run_pipeline_message(message)
```

v0.3 新增入口：

```python
tsgo.runtime.run_llm_pipeline_message(
    message,
    model_client=model_client,
)
```

构建 controller：

```python
tsgo.runtime.build_v03_controller(
    model_client=model_client,
    prompter=DefaultPipelinePrompter(),
)
```

## v0.3 执行链路

```text
TaskIntakeOperator                 # 仍复用 deterministic 分类
ContextBuilderOperator             # 仍复用 deterministic 上下文整理
RubricBuilderOperator              # 仍复用 deterministic rubric
ProblemDecomposerOperator          # 仍复用 deterministic subtask 拆解
LLMCandidateGeneratorOperator      # model-backed
LLMThoughtNormalizerOperator       # model-backed
LLMVerifierScorerOperator          # model-backed
LLMImproverOperator                # model-backed
LLMAggregatorOperator              # model-backed + diversity-aware top-k
LLMFinalValidatorOperator          # model-backed
trace persistence                  # controller 末尾统一落盘
```

## JSON 合约

v0.3 强制每个 LLM-backed operator 经过 JSON parser：

```text
GenerateOperator   -> parse_generate_packet
NormalizeOperator  -> parse_normalize_packet
ScoreOperator      -> parse_score_packets
ImproveOperator    -> parse_improve_packet
AggregateOperator  -> parse_aggregate_packet
ValidateOperator   -> parse_validation_packet
```

解析层会做轻量 coercion：

- JSON code fence 提取；
- object / array 提取；
- 0..1 score clamp；
- claim_type fallback 到 `unknown`；
- string / list 兼容；
- missing state_id 时按顺序 fallback。

更详细 schema 见 [JSON 契约](json-contracts.md)。

## Diversity-aware aggregation

v0.2 暴露出一个问题：如果所有 scored states 得分相同，普通 top-k 会只选第一个 subtask 的候选。

v0.3 的 `LLMAggregatorOperator` 使用 diversity-aware top-k：

```text
先按 subtask_id 分组
每组选择最高分 state
再用全局最高分补齐 top_k
```

这样 final answer 至少能覆盖多个 subtask，而不是只吸收最早生成的一组候选。

## 本地 demo

v0.3 可以在无 API key 情况下用 `ScriptedModelClient` 验证完整 LLM-backed operator path：

```bash
python tests/demo_pipeline_v03.py "进入 Pipeline v0.3" --num-branches 1
```

该 demo 使用 scripted JSON responses，不验证模型能力，只验证：

```text
Prompter -> ModelClient -> JSON contracts -> LLM operators -> Trace / Events / Graph
```

## 测试

新增：

```text
tests/test_llm_pipeline.py
```

测试内容：

- `run_llm_pipeline_message()` 可以端到端跑通；
- LLM-backed states 带 `operator_mode = llm_v0.3`；
- final state 为 `validated`；
- trace 会完整落盘；
- scripted model 的 prompt 调用次数符合预期。

## v0.3 非目标

v0.3 当前不绑定任何单一模型供应商，也不强制引入 OpenAI / Anthropic / Gemini SDK。

真实 provider 只需要实现：

```python
class ModelClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...
```

这让 v0.3 保持 provider-neutral。后续可以按部署需求增加：

- OpenAIModelClient
- AnthropicModelClient
- LocalHTTPModelClient
- LiteLLMModelClient

## v0.3 完成标准

当前 v0.3 的完成标准：

1. LLM-backed operators 已存在；
2. 每个 model output 都经过结构化 JSON contract parser；
3. v0.2 mock runtime 不被破坏；
4. v0.3 runtime 可通过 scripted model 端到端运行；
5. Aggregator 使用 diversity-aware top-k；
6. Trace / Event / Graph 契约保持兼容；
7. 文档、demo、测试同步更新。
