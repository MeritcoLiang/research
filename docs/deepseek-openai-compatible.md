# DeepSeek OpenAI-compatible API

本文档说明如何把 DeepSeek 接入现有 LLM Operators。

语义边界：DeepSeek 只是某些 Operator 内部调用真实模型的实现方式，不是新的执行层。主线仍然是：

```text
ThoughtGraph -> GraphController -> Operator -> ThoughtState
```

## 1. 前置条件

安装依赖：

```bash
pip install -e '.[deepseek]'
```

准备 `.env`：

```bash
cp .env.example .env
```

填入：

```bash
DEEPSEEK_API_KEY="<deepseek-api-key>"
```

## 2. 环境变量

必需：

```bash
DEEPSEEK_API_KEY="<deepseek-api-key>"
```

可选：

```bash
DEEPSEEK_BASE_URL="https://api.deepseek.com"
DEEPSEEK_MODEL="deepseek-v4-pro"
DEEPSEEK_TEMPERATURE="0.2"
DEEPSEEK_MAX_TOKENS="2048"
DEEPSEEK_TIMEOUT="90"
DEEPSEEK_REASONING_EFFORT="high"
DEEPSEEK_THINKING="enabled"
DEEPSEEK_SYSTEM_MESSAGE="你是 Thought-State Graph Orchestration Engine 中的 Operator。必须严格遵守请求的结构化输出约束。"
```

## 3. 快速运行

```bash
python tests/demo_pipeline_v03_deepseek.py "进入 Pipeline v0.3" --num-branches 1
```

建议先使用 `--num-branches 1` 控制调用次数。当前 v0.3 LLM Operators 的调用次数大致为：

```text
subtask_count * num_branches  # generate
+ candidate_count             # normalize
+ 1                           # score batch
+ 1                           # aggregate
+ 1                           # validate
```

默认 v0.3 会拆 4 个 subtasks，因此 `--num-branches 1` 大约会产生 11 次模型调用。

## 4. 代码入口

```python
from tsgo.deepseek_client import DeepSeekOpenAIChatModelClient
from tsgo.runtime import run_llm_pipeline_message

client = DeepSeekOpenAIChatModelClient.from_env()
trace = run_llm_pipeline_message(
    "进入 Pipeline v0.3",
    model_client=client,
    num_branches=1,
)
```

## 5. 实现说明

代码位置：

```text
src/tsgo/deepseek_client.py
```

该 client：

1. 从 `.env` / 环境变量读取 `DEEPSEEK_API_KEY`；
2. 使用 OpenAI Python client；
3. 使用 OpenAI-compatible `chat.completions.create()`；
4. 默认 base URL 为 `https://api.deepseek.com`；
5. 默认模型为 `deepseek-v4-pro`；
6. 返回 `response.choices[0].message.content` 作为 `ModelClient.generate(prompt)` 的结果。

## 6. 模型与兼容说明

DeepSeek 官方文档说明其 API 使用兼容 OpenAI / Anthropic 的 API 格式；OpenAI base URL 是：

```text
https://api.deepseek.com
```

官方当前示例模型包含：

```text
deepseek-v4-flash
deepseek-v4-pro
```

`deepseek-chat` 和 `deepseek-reasoner` 仍可兼容，但官方文档提示它们将在 2026-07-24 废弃，因此本项目默认使用 `deepseek-v4-pro`。

## 7. 常见问题

### 401

检查：

```bash
DEEPSEEK_API_KEY
```

### 输出无法解析 JSON

当前 v0.3 仍通过 LLM Operators 的 JSON parser 解析模型输出。后续进入 structured-only Operator 后，会把输出字段迁移为 Pydantic schema / `output_type`，减少 prompt JSON 依赖。

### 关闭 thinking / reasoning_effort

某些模型或部署可能不支持 thinking 参数。可以在 `.env` 中设置为空：

```bash
DEEPSEEK_REASONING_EFFORT=""
DEEPSEEK_THINKING=""
```
