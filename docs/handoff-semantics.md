# Handoff Semantics

本项目中的 handoff 不是 UI 上的普通中间节点，也不是直接把某个固定专家写死到流程里。它表示：一个负责路由的 agent 根据 instructions 判断当前任务应由哪个 specialist 接管，然后通过目标特定的 handoff tool 转移控制权。

## 对齐 OpenAI Agents SDK 的语义

OpenAI Agents SDK 中，handoff 的核心含义是：

```text
Triage / routing agent
  -> receives instructions and available handoffs
  -> invokes a target-specific handoff tool
  -> transfers control to the selected specialist agent
  -> selected specialist owns the next part of the conversation
```

因此，handoff 至少需要保留以下信息：

```text
source_agent              # 例如 ExpertRouter
router instructions        # 路由规则，不回答用户，只决定是否 handoff
handoff tool name          # 例如 transfer_to_secondary_market_analyst
handoff description        # 何时应该使用这个 handoff
handoff input schema       # reason / asset / horizon / missing_context 等
selected target agent      # 例如 SecondaryMarketAnalyst
target instructions        # 专家接管后的行为约束
handoff input/output       # 实际工具调用参数与转移结果
```

## 当前项目映射

当前只有一个 expert profile：`SecondaryMarketAnalyst`。这不意味着 handoff 可以被折叠成普通函数调用。正确语义是：

```text
User Message / root
  -> ExpertRouter receives routing instructions
  -> ExpertRouter invokes transfer_to_secondary_market_analyst
  -> SecondaryMarketAnalyst takes over
  -> ContextBuilder
  -> RubricBuilder
  -> ProblemDecomposer
  -> CandidateGenerator
  -> ThoughtNormalizer
  -> VerifierScorer
  -> Improver
  -> Aggregator
  -> FinalValidator
```

即使当前只有一个目标，`ExpertRouter` 节点仍有现实意义，因为它记录了“为什么该问题应该由二级市场专家接管”，也为未来增加更多专家提供了可扩展路由协议。

## Deterministic stage_flow 与 LLM stage_flow

`stage_flow` 是 deterministic runtime，用于快速验证 ThoughtGraph、TraceEvent 和 Web UI。它可以保留可解释的 handoff metadata。

`azure_openai` / `deepseek` 的 LLM stage flow 应该更接近真实 Agents SDK 语义：第一步由 LLM-backed `ExpertRouter` 根据 instructions 产出目标特定 handoff 调用，然后由 `SecondaryMarketAnalyst` 专家 stage flow 接管。

## 约束

- UI 必须展示 handoff，而不是隐藏 `SecondaryMarketAnalyst`。
- `SecondaryMarketAnalyst` 不是一个视觉标签，而是接管后续 stage flow 的 specialist instruction context。
- 后续引入更多 expert profile 时，应注册多个 handoff tool，让 router 根据 instructions 选择目标。
- handoff 的 `input_type`/schema 只能携带路由时生成的小型 metadata，例如 reason、asset、horizon、missing_context；它不应该替代专家主输入，也不应该把应用状态混进 handoff 参数。
