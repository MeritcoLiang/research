# AIDCProgressExpert

`AIDCProgressExpert` 是一个使用 OpenAI Agents SDK 构建的单一专家 Agent。输入数据中心/AIDC 名称、County、州和可选地点线索后，它会优先检索政府、环境、输电、公用事业和当地媒体，生成可审计的项目进展报告。

它与当前 `SecondaryMarketAnalyst` 流程相互独立，不改变 Thought-State Graph 的既有执行语义；后续可以把它包装为 Operator 或 manager agent 的 tool。

## 1. 解决的问题

普通的 `项目名 + County + latest news` 搜索很容易漏掉真正决定项目状态的记录：

- 规划文件使用项目代号、申请人或持地 LLC，而不是运营商名称；
- Permit Portal 使用地址、Parcel/PIN 或 permit number；
- 输电文件可能只写 `large-load customer`；
- 环境许可的设备清单不代表园区已经投产；
- 多栋园区的一张 Certificate of Occupancy 不能代表全部建成。

因此 Agent 固定执行：

```text
输入名称/County/州
  -> 行政辖区确认
  -> 项目身份和别名发现
  -> 规划/议程
  -> Grading/Building/Inspection/CO
  -> DEQ/Stormwater/USACE
  -> SCC/Utility/Transmission/Substation
  -> GIS/Property/Incentive
  -> 法院/社区风险
  -> 当地新闻补充
  -> 冲突解决
  -> 时间线与当前阶段
  -> AIDCProgressReport
```

## 2. 工程结构

```text
src/tsgo/aidc_progress/
├── __init__.py       # 公共接口
├── agent.py          # Agent、WebSearchTool、Runner
├── cli.py            # aidc-progress 命令
├── instructions.py   # 完整专家 instructions
├── models.py         # Pydantic 输入/输出契约
├── provider.py       # OpenAI / Azure OpenAI 配置
├── render.py         # Markdown / JSON 输出
└── sources.py        # 通用及 Loudoun 信息源注册表

tests/
├── demo_aidc_progress_agent.py
├── test_aidc_progress_core.py
└── fixtures/aidc_loudoun_stone_ridge_request.json
```

## 3. 安装

```bash
pip install -e '.[aidc]'
cp .env.example .env
```

该 extra 锁定 `openai-agents>=0.18.2,<0.19.0`，避免 SDK 快速迭代导致接口漂移。

## 4. OpenAI 运行方式

`.env`：

```dotenv
AIDC_PROVIDER="openai"
OPENAI_API_KEY="<your-openai-api-key>"
AIDC_OPENAI_MODEL="gpt-5.4"
AIDC_SEARCH_CONTEXT_SIZE="high"
AIDC_MAX_TURNS="30"
AIDC_DISABLE_TRACING="true"
AIDC_OUTPUT_DIR="reports/aidc"
```

运行指定测试案例：

```bash
aidc-progress \
  --name "AWS Stone Ridge" \
  --county "Loudoun County" \
  --state "Virginia" \
  --alias "Reeds Farm Lane" \
  --location-hint "Stone Ridge" \
  --as-of-date "2026-07-14"
```

或直接执行 demo：

```bash
python tests/demo_aidc_progress_agent.py
```

## 5. Azure OpenAI + `az login`

先登录并确认账号对 Azure OpenAI 资源拥有调用权限：

```bash
az login
```

`.env`：

```dotenv
AIDC_PROVIDER="azure"
AZURE_OPENAI_ENDPOINT="https://<resource>.services.ai.azure.com"
AZURE_OPENAI_DEPLOYMENT="gpt-5.4"
AZURE_OPENAI_TOKEN_SCOPE="https://ai.azure.com/.default"
AZURE_OPENAI_TIMEOUT="180"
AIDC_SEARCH_CONTEXT_SIZE="high"
AIDC_MAX_TURNS="30"
AIDC_DISABLE_TRACING="true"
```

运行命令与 OpenAI 模式相同。

> `WebSearchTool` 是 Responses API hosted tool。Azure deployment 和 endpoint 必须支持对应的 web-search tool payload。若 Azure 资源不支持，应切换 `AIDC_PROVIDER=openai`；不要退化为无来源的模型记忆回答。

## 6. 输出文件

默认生成：

```text
reports/aidc/aws-stone-ridge-2026-07-14.json
reports/aidc/aws-stone-ridge-2026-07-14.md
```

JSON 是主产物，字段包括：

```text
request
identity
jurisdiction
current_stage
current_status
latest_verified_event
approval_status
construction_status
power_status
environmental_status
infrastructure_status
legal_and_community_status
timeline
sources
source_conflicts
unresolved_questions
research_gaps
confidence
as_of_date
```

Markdown 供人工阅读，保留所有 URL、事件日期、来源等级和不确定性。

## 7. Loudoun 测试案例

Fixture：

```json
{
  "name": "AWS Stone Ridge",
  "county": "Loudoun County",
  "state": "Virginia",
  "aliases": ["Reeds Farm Lane"],
  "location_hints": ["Stone Ridge"],
  "as_of_date": "2026-07-14",
  "lookback_years": 8
}
```

Loudoun registry 内置以下检索面：

- Loudoun Planning and Zoning；
- Public Hearing / Board of Supervisors；
- LandMARC；
- Building and Development permits；
- Mapping/GIS；
- Virginia DEQ；
- Virginia SCC DocketSearch；
- USACE Norfolk District；
- Dominion Energy；
- Loudoun Water；
- Loudoun Now、Loudoun Times-Mirror、The Burn、Washington Business Journal。

测试不预设“项目已开工”或“已投产”等结论。它验证的是：Agent 必须先确认 `AWS Stone Ridge` 与 `Reeds Farm Lane`、地址/Parcel、申请人/LLC、case/permit 的映射，再根据最强证据判断阶段。

## 8. 离线测试

不调用模型、不需要联网：

```bash
pytest -q tests/test_aidc_progress_core.py
```

当前覆盖：

- Loudoun 信息源类别完整性；
- 指定项目名称和地点别名进入查询；
- 生命周期检索覆盖；
- alias 去重；
- 报告质量检查；
- Markdown/JSON 输出；
- Azure endpoint 归一化。

## 9. 失败排查

### 缺少 Agents SDK

```text
AIDC Agent 需要安装：pip install -e '.[aidc]'
```

执行安装命令后重试。

### OpenAI 模式缺少 Key

```text
AIDC_PROVIDER=openai 时必须设置 OPENAI_API_KEY。
```

### Azure 模式缺少 endpoint/deployment

检查：

```dotenv
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
```

### Azure 身份失败

重新执行：

```bash
az login
az account show
```

并确认当前身份拥有资源的 OpenAI 调用角色。

### 找不到某个政府 Portal 的完整内容

Agent 应把它记录到 `research_gaps`，随后用 case number、地址、Parcel、permit number 去议程包、staff report、public notice、当地新闻或关联机构继续交叉检索，而不是编造状态。
