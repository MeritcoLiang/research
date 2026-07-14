# AIDC Progress Studio

一个完全独立的 AIDC / 数据中心项目进展研究工程。它不依赖 `tsgo`、原 Thought-State Graph Web UI、原 session API 或 Vite 服务。

```text
浏览器
  -> FastAPI 单端口服务
     -> POST /api/runs
     -> WebSocket /ws/runs/{run_id}
     -> OpenAI Agents SDK + WebSearchTool
     -> AIDCProgressReport
     -> data/runs + data/reports
```

## 主要功能

- 独立任务表单：项目名、County、州、别名、地点线索和检索截止日期；
- Azure OpenAI 与 OpenAI 两种 provider；
- Agents SDK 流式事件：Web Search、工具输出、推理和报告生成；
- 历史任务持久化；
- 概览、分项状态、时间线、来源和原始 JSON；
- Markdown / JSON 报告下载；
- 单端口部署，不需要单独启动 Node/Vite；
- Windows PowerShell、Linux/macOS、Docker 三种启动方式。

## 工程结构

```text
aidc-progress-studio/
├── pyproject.toml
├── .env.example
├── run.ps1
├── run.sh
├── Dockerfile
├── src/aidc_progress_studio/
│   ├── agent.py          # Agents SDK + WebSearchTool + streaming
│   ├── api.py            # FastAPI / REST / WebSocket / static UI
│   ├── models.py         # 输入、报告和运行记录契约
│   ├── provider.py       # OpenAI / Azure OpenAI
│   ├── service.py        # 后台任务生命周期
│   ├── store.py          # JSON/Markdown 持久化和订阅
│   ├── sources.py        # County-aware source registry
│   ├── instructions.py   # AIDCProgressExpert instructions
│   ├── render.py         # Markdown 输出
│   └── static/           # 独立交互界面
└── tests/
```

该目录可以直接复制到新仓库，不需要保留父工程中的任何文件。

## Windows 启动

```powershell
cd aidc-progress-studio
Copy-Item .env.example .env
notepad .env

powershell -ExecutionPolicy Bypass -File .\run.ps1
```

打开：

```text
http://127.0.0.1:8080
```

`run.ps1` 是 UTF-8 with BOM，并自动创建 `.venv`。更新依赖时：

```powershell
.\run.ps1 -ForceInstall
```

## Linux / macOS

```bash
cd aidc-progress-studio
cp .env.example .env
./run.sh
```

## Azure OpenAI

使用 API Key：

```dotenv
AIDC_PROVIDER="azure"
AZURE_OPENAI_ENDPOINT="https://<resource>.services.ai.azure.com"
AZURE_OPENAI_DEPLOYMENT="gpt-5.4"
AZURE_OPENAI_API_KEY="<key>"
```

使用 Azure CLI 身份：

```powershell
az login
```

```dotenv
AIDC_PROVIDER="azure"
AZURE_OPENAI_ENDPOINT="https://<resource>.services.ai.azure.com"
AZURE_OPENAI_DEPLOYMENT="gpt-5.4"
AZURE_OPENAI_API_KEY=""
AZURE_OPENAI_TOKEN_SCOPE="https://ai.azure.com/.default"
```

Azure deployment 必须支持 Responses API hosted Web Search。

## OpenAI

```dotenv
AIDC_PROVIDER="openai"
OPENAI_API_KEY="<key>"
AIDC_OPENAI_MODEL="gpt-5.4"
```

## API

```text
GET  /api/health
GET  /api/config
POST /api/runs
GET  /api/runs
GET  /api/runs/{run_id}
GET  /api/runs/{run_id}/report.json
GET  /api/runs/{run_id}/report.md
WS   /ws/runs/{run_id}
```

创建任务：

```json
{
  "research": {
    "name": "AWS Stone Ridge",
    "county": "Loudoun County",
    "state": "Virginia",
    "aliases": ["Reeds Farm Lane"],
    "location_hints": ["Stone Ridge"],
    "as_of_date": "2026-07-14",
    "lookback_years": 8
  },
  "runtime": {
    "provider": "azure",
    "model": "gpt-5.4",
    "search_context_size": "high",
    "max_turns": 30
  }
}
```

## 数据目录

默认：

```text
data/runs/<run_id>.json
data/reports/<run_id>.json
data/reports/<run_id>.md
```

覆盖：

```dotenv
AIDC_DATA_DIR="D:/aidc-progress-data"
```

## 测试

```bash
python -m pip install -e ".[dev]"
pytest -q
```

测试不调用模型或 Web Search。
