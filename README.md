# Thought-State Graph Orchestration Engine

本仓库是 **Thought-State Graph Orchestration Engine（思维状态图编排引擎）** 的工程落地区。当前主线已经修正为：**ThoughtGraph 是核心产物；LLM、Agents SDK、structured output、tools、provider client 都只是 Operator 的实现细节**。

高质量 AI 回答不应该来自一次简单的 prompt-response 调用。每一个中间 thought 都应该被结构化、评分、改进、验证、聚合、记录，并进入可查询的 thought-state graph。

## 当前状态

当前已经推进到：

```text
SecondaryMarketAnalyst Stage flow 已可运行
Web UI 会实时反馈并更新流程图
Pipeline v0.3 已支持真实 Azure OpenAI 调用（az login）
Pipeline v0.3 已支持真实 DeepSeek 调用（OpenAI-compatible API）
.env.example 已设计完成，.env 保持本地私密
```

主流程：

```text
User Message
  -> ExpertRouter / Handoff
  -> 10 Business Stages
  -> Trace
  -> ThoughtGraph
  -> GraphRunResult
```

主对象：

```text
ThoughtGraph
  nodes:
    ThoughtState
    Subtask
    ExpertProfile
  edges:
    handoff
    decomposes_to
    generates
    normalizes
    scores
    improves
    aggregates
    validates
    feedback
    tool
```

## 工程原则

1. 每个 Operator 都消费结构化状态，并返回结构化状态。
2. Web UI 输入 message 必须走同一个 Stage flow runtime，并实时产出 TraceEvent / GraphSnapshot。
3. v0.3+ 的主产物是 `ThoughtGraph`，不是 prompt、provider、agent 或 API response。
4. Operator 是唯一的执行语义。LLM、Agents SDK、tools、rules 都只是 Operator 的实现方式。
5. Agents SDK 未来只用于实现某些 Operator；GraphController 才是 orchestration engine。
6. `.env` 只在本地保存真实密钥；仓库只提交 `.env.example`。

## 环境变量

复制模板：

```bash
cp .env.example .env
```

`.env` 中包含：

```text
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
AZURE_OPENAI_TEMPERATURE
AZURE_OPENAI_MAX_OUTPUT_TOKENS
AZURE_OPENAI_TIMEOUT
AZURE_OPENAI_TOKEN_SCOPE

DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
DEEPSEEK_MODEL
DEEPSEEK_TEMPERATURE
DEEPSEEK_MAX_TOKENS
DEEPSEEK_TIMEOUT
DEEPSEEK_REASONING_EFFORT
DEEPSEEK_THINKING
```

`.env` 和 `.env.*` 默认被 git 忽略，`.env.example` 会被追踪。

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

SecondaryMarketAnalyst Stage flow：

```bash
pip install -e .
python tests/demo_secondary_market_stage_flow.py "请用二级市场分析师视角分析 AAPL 的中期机会和风险。"
```

Azure OpenAI 真实模型调用，使用 `az login`：

```bash
az login
pip install -e '.[azure]'
cp .env.example .env
# 填写 AZURE_OPENAI_ENDPOINT 和 AZURE_OPENAI_DEPLOYMENT
python tests/demo_pipeline_v03_azure.py "进入 Pipeline v0.3" --num-branches 1
```

DeepSeek 真实模型调用：

```bash
pip install -e '.[deepseek]'
cp .env.example .env
# 填写 DEEPSEEK_API_KEY
python tests/demo_pipeline_v03_deepseek.py "进入 Pipeline v0.3" --num-branches 1
```

Graph-first runtime：

```python
from tsgo.runtime import run_secondary_market_graph

result = run_secondary_market_graph("请用二级市场分析师视角分析 AAPL 的中期机会和风险。")
thought_graph = result.thought_graph
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
tsgo.runtime.run_pipeline_graph(message)
```

SecondaryMarketAnalyst Stage flow runtime：

```python
tsgo.runtime.run_secondary_market_stage_flow(message)
tsgo.runtime.run_secondary_market_graph(message)
```

v0.3 LLM runtime：

```python
tsgo.runtime.run_llm_pipeline_message(
    message,
    model_client=model_client,
)

tsgo.runtime.run_llm_pipeline_graph(
    message,
    model_client=model_client,
)
```

Azure OpenAI client：

```python
from tsgo.azure_openai_client import AzureOpenAIResponsesModelClient
from tsgo.runtime import run_llm_pipeline_message

client = AzureOpenAIResponsesModelClient.from_env()
trace = run_llm_pipeline_message("进入 Pipeline v0.3", model_client=client, num_branches=1)
```

DeepSeek client：

```python
from tsgo.deepseek_client import DeepSeekOpenAIChatModelClient
from tsgo.runtime import run_llm_pipeline_message

client = DeepSeekOpenAIChatModelClient.from_env()
trace = run_llm_pipeline_message("进入 Pipeline v0.3", model_client=client, num_branches=1)
```

## 调用链

```text
tests/demo_secondary_market_stage_flow.py
  -> tsgo.runtime.run_secondary_market_stage_flow
  -> PipelineController
  -> SecondaryMarketAnalyst Operators
  -> Expert handoff event
  -> 10 Business Stages
  -> Trace / TraceEvents / GraphSnapshot
  -> ThoughtGraph 可选

Web UI message
  -> tsgo.web.sessions.SessionManager.handle_user_message
  -> tsgo.runtime.run_secondary_market_stage_flow
  -> PipelineController
  -> SecondaryMarketAnalyst Operators
  -> Trace / TraceEvents / GraphSnapshot

tests/demo_pipeline_v03_azure.py
  -> AzureOpenAIResponsesModelClient.from_env
  -> tsgo.runtime.run_llm_pipeline_message
  -> PipelineController
  -> LLM Operators
  -> Azure OpenAI Responses API
  -> Trace / TraceEvents
  -> ThoughtGraph 可选

tests/demo_pipeline_v03_deepseek.py
  -> DeepSeekOpenAIChatModelClient.from_env
  -> tsgo.runtime.run_llm_pipeline_message
  -> PipelineController
  -> LLM Operators
  -> DeepSeek OpenAI-compatible Chat Completions API
  -> Trace / TraceEvents
  -> ThoughtGraph 可选
```

## 仓库结构

```text
.
├── .env.example
├── README.md
├── pyproject.toml
├── src/
│   └── tsgo/
│       ├── __init__.py
│       ├── azure_openai_client.py
│       ├── deepseek_client.py
│       ├── env.py
│       ├── engine.py
│       ├── events.py
│       ├── experts/
│       ├── graph.py
│       ├── json_contracts.py
│       ├── llm_operators.py
│       ├── model_client.py
│       ├── operators.py
│       ├── pipeline.py
│       ├── runtime.py
│       ├── schema.py
│       ├── thought_graph.py
│       └── web/
├── docs/
│   ├── azure-openai-az-login.md
│   ├── deepseek-openai-compatible.md
│   ├── event-stream.md
│   ├── json-contracts.md
│   ├── pipeline-v0.3.md
│   ├── stage-instructions-secondary-market-analyst.md
│   ├── stage-prompts-secondary-market-analyst.md
│   ├── thought-state-graph-engine.md
│   └── web-ui.md
├── tests/
│   ├── demo_pipeline_v03_azure.py
│   ├── demo_pipeline_v03_deepseek.py
│   ├── demo_secondary_market_stage_flow.py
│   ├── test_azure_openai_client.py
│   ├── test_deepseek_client.py
│   └── test_secondary_market_stage_flow.py
└── web/
```

## 文档入口

建议从这里开始阅读：

- [Thought-State Graph Engine 主线](docs/thought-state-graph-engine.md)
- [Azure OpenAI with az login](docs/azure-openai-az-login.md)
- [DeepSeek OpenAI-compatible API](docs/deepseek-openai-compatible.md)
- [Pipeline v0.3](docs/pipeline-v0.3.md)
- [SecondaryMarketAnalyst Stage Instructions](docs/stage-instructions-secondary-market-analyst.md)
- [SecondaryMarketAnalyst Stage Prompts](docs/stage-prompts-secondary-market-analyst.md)
- [Web UI 设计](docs/web-ui.md)
- [事件流设计](docs/event-stream.md)
- [JSON 契约](docs/json-contracts.md)
- [阶段索引](docs/stage-index.md)
- [Prompter 接口映射](docs/prompter-interface.md)

## 核心抽象

1. `ThoughtState`：一个候选答案、子答案、批评、修订、聚合结果或最终回复。
2. `Subtask`：问题拆解得到的子任务，也是 graph node。
3. `ExpertProfile`：专家选择结果，也是 graph node；当前已支持 `SecondaryMarketAnalyst`。
4. `ThoughtEdge`：thought graph 的有向边。
5. `ThoughtGraph`：系统主产物，包含 states、subtasks、expert profiles、edges、root、final state。
6. `Operator`：唯一的执行语义；负责把输入状态转换成输出状态。
7. `GraphRunResult`：一次运行的 `Trace + ThoughtGraph`。
8. `PipelineController`：当前线性执行策略，后续会被 GraphController 替代或包裹。
9. `TraceEvent`：Web UI 和测试用于实时观察 pipeline 的事件。
10. `GraphSnapshot`：将 Trace 映射为前端可渲染的 nodes / edges。
11. `ModelClient`：LLM Operators 内部使用的临时辅助接口，不是 graph engine 主抽象。

## 开发状态

已经完成：

- SecondaryMarketAnalyst 10-stage flow
- Web UI 实时流程图
- `Trace -> GraphSnapshot`
- `Trace -> ThoughtGraph`
- `.env.example` 与可选 dotenv 加载
- `AzureOpenAIResponsesModelClient`，支持 `az login`
- `DeepSeekOpenAIChatModelClient`，支持 OpenAI-compatible API
- `tests/demo_pipeline_v03_azure.py`
- `tests/demo_pipeline_v03_deepseek.py`
- `tests/test_azure_openai_client.py`
- `tests/test_deepseek_client.py`
- diversity-aware aggregation

尚未完成：

- GraphController
- frontier selection
- graph search policy
- Web UI final lineage / full graph 切换
- 使用 Agents SDK 实现部分 Operator
- Azure OpenAI / DeepSeek structured-only Operator 收敛
- 最小 verifier tools

## 下一阶段

下一阶段是 **v0.4 GraphController 主路径**：

```text
GraphController
  -> frontier selection
  -> state expansion policy
  -> diversity-aware pruning
  -> final lineage extraction
  -> graph replay
  -> Web UI final lineage / full graph toggle
```

Agents SDK 和模型接入在 v0.5+ 只作为 Operator 的实现方式引入，不再喧宾夺主。
