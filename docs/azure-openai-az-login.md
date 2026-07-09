# Azure OpenAI with `az login`

本文档说明如何让现有 LLM Operators 使用 **Azure OpenAI + Azure CLI 登录态** 发起真实模型调用。

语义边界：Azure OpenAI 只是某些 Operator 内部调用真实模型的实现方式，不是新的执行层。主线仍然是：

```text
ThoughtGraph -> GraphController -> Operator -> ThoughtState
```

## 1. 前置条件

需要：

```bash
az login
```

并确保当前 Azure 用户对 Azure OpenAI / Azure AI Foundry 资源具备推理调用权限，例如 Cognitive Services OpenAI User 或等效角色。

安装依赖：

```bash
pip install -e '.[azure]'
```

该 extra 会安装：

```text
openai
azure-identity
```

## 2. 环境变量

必需：

```bash
export AZURE_OPENAI_ENDPOINT="https://<resource-name>.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT="<deployment-name>"
```

可选：

```bash
export AZURE_OPENAI_TEMPERATURE="0.2"
export AZURE_OPENAI_MAX_OUTPUT_TOKENS="2048"
export AZURE_OPENAI_TIMEOUT="90"
export AZURE_OPENAI_TOKEN_SCOPE="https://ai.azure.com/.default"
```

`AZURE_OPENAI_DEPLOYMENT` 是 Azure 部署名，不一定等于基础模型名。

## 3. 快速运行

```bash
python tests/demo_pipeline_v03_azure.py "进入 Pipeline v0.3" --num-branches 1
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
from tsgo.azure_openai_client import AzureOpenAIResponsesModelClient
from tsgo.runtime import run_llm_pipeline_message

client = AzureOpenAIResponsesModelClient.from_env()
trace = run_llm_pipeline_message(
    "进入 Pipeline v0.3",
    model_client=client,
    num_branches=1,
)
```

## 5. 实现说明

代码位置：

```text
src/tsgo/azure_openai_client.py
```

该 client：

1. 使用 `AzureCliCredential` 读取 `az login` 登录态；
2. 使用 `get_bearer_token_provider` 获取 Microsoft Entra token；
3. 使用 OpenAI Python client 访问 Azure OpenAI `/openai/v1/` endpoint；
4. 调用 Responses API；
5. 返回 `response.output_text` 作为 `ModelClient.generate(prompt)` 的结果。

## 6. 常见问题

### 401 / 403

检查：

```bash
az account show
```

确认当前账号与资源在同一 tenant / subscription，并且拥有 Azure OpenAI 推理调用权限。

### 404

确认：

```bash
AZURE_OPENAI_DEPLOYMENT
```

是部署名，不是模型名。

### 输出无法解析 JSON

当前 v0.3 仍通过 LLM Operators 的 JSON parser 解析模型输出。后续进入 structured-only Operator 后，会把输出字段迁移为 Pydantic schema / `output_type`，减少 prompt JSON 依赖。
