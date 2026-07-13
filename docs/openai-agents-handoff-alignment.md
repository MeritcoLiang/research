# OpenAI Agents SDK Handoff Alignment

本文档记录本项目对 OpenAI Agents SDK `handoff` 语义的对齐方式。

官方文档要点：

- Handoff 是一个 agent 将任务委派给另一个 specialist agent。
- Handoff 在模型侧表现为 tool，例如 `transfer_to_refund_agent`。
- Triage / router agent 需要通过 `instructions` 告诉模型：什么情况下应该 hand off 到哪个 specialist。
- `handoff()` 绑定的是一个明确的目标 agent；如果有多个目标，需要为每个目标注册 handoff，并让模型按 instructions 选择。
- Handoff 发生后，接收 agent 接手 conversation，并能看到前序 conversation history，除非通过 input filter 改写。

对应到 Thought-State Graph Orchestration Engine：

```text
User Message
  -> Root ThoughtState
  -> ExpertRouter / Triage instructions
  -> handoff tool call: transfer_to_secondary_market_analyst
  -> SecondaryMarketAnalyst instruction context
  -> Task Intake
  -> Context Builder
  -> Rubric Builder
  -> Problem Decomposer
  -> Candidate Generator
  -> Thought Normalizer
  -> Verifier / Scorer
  -> Improver
  -> Aggregator
  -> Final Validator
```

## 本项目的 handoff 不变量

1. `SecondaryMarketAnalyst` 即使目前是唯一 expert profile，也仍然是一个真实 handoff 目标，不应从 UI 或 Trace 中折叠掉。
2. Handoff 的核心不是“存在一个专家名称”，而是：`ExpertRouter` 通过 instructions 判断用户请求是否应路由到该专家。
3. Handoff 输出必须是结构化 metadata，至少包含：
   - `selected_expert`
   - `handoff_reason`
   - `asset_or_market`
   - `time_horizon`
   - `user_intent`
   - `missing_context`
   - `compliance_constraints`
4. 后续 business stages 必须继承 `SecondaryMarketAnalyst` 的 instruction context，而不是把 expert profile 当作展示标签。
5. UI 流程图必须显示 handoff 节点，因为它是控制权转移，不是普通 state edge。

## Router instructions sketch

```text
You are ExpertRouter / Triage.

Do not answer the user's question.
Decide whether the request should be handed off to a specialist agent.

If the user asks about stocks, ETFs, indexes, sectors, bonds, FX,
commodities, crypto assets, price action, market risk/reward,
valuation, catalysts, flows, positioning, technicals, or event-driven
secondary-market analysis, call:

transfer_to_secondary_market_analyst

When calling the handoff, include structured handoff metadata:
- selected_expert = SecondaryMarketAnalyst
- handoff_reason
- asset_or_market
- time_horizon
- user_intent
- missing_context
- compliance_constraints

Do not produce investment advice.
Do not emit buy/sell/hold conclusions.
```

## Specialist instructions sketch

```text
You are SecondaryMarketAnalyst.

You produce structured, verifiable, risk-calibrated secondary-market research.
You must distinguish facts, assumptions, interpretations, scenarios, risks,
uncertainties, and missing data.

You must not provide personalized investment advice.
You must not fabricate real-time prices, financial data, news, or fund flows.
```

## Design implication

`ExpertRouter / Handoff` should remain a first-class visible step:

```text
root --handoff--> SecondaryMarketAnalyst --decomposes_to--> subtask s1/s2/...
```

The current deterministic implementation may emulate the router decision, but the semantic contract must remain compatible with a future Agents SDK implementation where the router model receives instructions and invokes the handoff tool.