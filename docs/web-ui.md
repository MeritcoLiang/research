# Web UI 设计

Web UI 的目标是让用户在浏览器里输入 message、选择 LLM / Operator 实现，并实时看到 Thought-State Graph Orchestration Engine 的 Stage 调用流程图。

当前 Web UI 支持三种任务发送模式：

```text
stage_flow     # SecondaryMarketAnalyst deterministic Stage flow，不调用真实 LLM
azure_openai   # SecondaryMarketAnalyst Stage flow + Azure OpenAI 实现 LLM Operators
deepseek       # SecondaryMarketAnalyst Stage flow + DeepSeek 实现 LLM Operators
```

## 可视化原则

流程图的用户可见标签必须语义化，不展示内部 `state_id`。`state_id` 只作为 React Flow 的内部 key 和调试 metadata 使用。

主流程采用**从左到右**的层级展开：

```text
root -> expert SecondaryMarketAnalyst -> subtask s1/s2/... -> candidates -> normalized -> scored -> aggregation -> validation
```

边线使用 React Flow 默认 Bezier edge，并显式设置：

```text
sourcePosition = Right
targetPosition = Left
edge.type = default
markerEnd = ArrowClosed
```

## 紧凑且稳定的流程图布局

前端 `web/src/graph/eventReducer.ts` 会在每次节点 upsert、patch 或 snapshot hydrate 后重新计算全图布局，避免“某个子节点先到、父节点后到”导致位置漂移。

紧凑布局常量：

```text
root:        x = 0
expert:      x = 150
subtask:     x = 320
candidate:   x = 520
normalized:  x = 720
scored:      x = 920
improved:    x = 1120
aggregation: x = 1320
validation:  x = 1500

GROUP_TOP        = 28
BRANCH_GAP       = 32
MIN_GROUP_HEIGHT = 88
```

每个 subtask 分组高度会根据该 subtask 下 candidate branch 数动态计算：

```text
group_height = max(88, branch_count * 32 + 56)
```

因此真实 LLM 默认 `num_branches=1` 时图会很紧凑；deterministic stage flow 使用 6 branches 时仍能完整展开。

## root / expert / subtask 为什么没有 Prompt preview

`Prompt preview` 只表示**真实 LLM 调用的输入 prompt**。因此只有使用 LLM 的 Operator 节点，例如 candidate、normalized、scored、aggregated、validated，才会有：

```text
prompt_preview
raw_model_preview
llm_input
llm_output
```

以下节点不会有 LLM prompt：

```text
root                 # 用户输入节点
expert Secondary...  # ExpertRouter / handoff 结果
subtask s1/s2/...    # ProblemDecomposer 的结构化输出
```

这些节点现在会展示：

```text
operator_input
operator_output
no_llm_reason
```

右侧节点详情会明确说明“该节点没有直接调用 LLM”，而不是空白或让用户误以为数据缺失。

## LLM 输入 / 输出完整查看

节点详情默认展示摘要和 preview，避免右侧面板被长 prompt 或长模型输出撑爆。

当节点包含完整 LLM 信息时，会出现按钮：

```text
查看完整 LLM 输入
查看完整 LLM 输出
```

点击后会打开弹出窗口，展示完整 prompt 或完整 raw model output。

同样地，对于 control 节点或 deterministic Operator，会显示：

```text
查看完整输入
查看完整输出
```

用于查看完整的 `operator_input` / `operator_output`。

## LLM 选择与发送任务

`ChatPanel` 提供 LLM / Operator 实现选择框：

```text
Stage Flow（无真实 LLM） -> llm_provider = stage_flow
Azure OpenAI（az login） -> llm_provider = azure_openai
DeepSeek                 -> llm_provider = deepseek
```

前端通过 WebSocket 发送：

```json
{
  "type": "user_message",
  "content": "请用二级市场分析师视角分析 AAPL 的中期机会和风险。",
  "num_branches": 1,
  "llm_provider": "deepseek"
}
```

前端发送分支数策略：

```text
stage_flow   -> num_branches = 6
azure_openai -> num_branches = 1
deepseek     -> num_branches = 1
```

真实 LLM 默认使用 1 个 branch，避免 Web UI 长时间无响应和模型调用成本过高。

后端 `SessionManager.handle_user_message()` 根据 `llm_provider` 选择运行方式：

```text
stage_flow   -> run_secondary_market_stage_flow()
azure_openai -> AzureOpenAIResponsesModelClient.from_env() + run_secondary_market_llm_stage_flow()
deepseek     -> DeepSeekOpenAIChatModelClient.from_env() + run_secondary_market_llm_stage_flow()
```

注意：LLM 选择只是选择 Operator 的实现方式，不引入新的执行语义层。

## 历史 Session 加载

Web UI 可以加载 `traces/web/*.jsonl` 中的历史 trace，并重新绘制流程图。

后端 API：

```text
GET /api/history              # 列出历史 trace
GET /api/history/{history_id} # 返回历史 trace summary + GraphSnapshot
```

前端 `ChatPanel` 提供“历史 Session”下拉框：

```text
选择历史 trace -> 加载流程图
刷新列表
```

加载历史 trace 时不重新调用 LLM，只读取本地 JSONL 最后一条 trace，重建 GraphSnapshot 并在 FlowCanvas 中展示。

## 普通浏览器缓存与 session 恢复

普通浏览器会保留 `localStorage`，无痕浏览器不会。后端 session 当前保存在内存里，因此后端重启后，普通浏览器里旧的 `tsgo_session_id` 可能已经不存在，导致普通浏览器不可用，而无痕浏览器因为没有旧缓存反而可以正常创建新 session。

修复策略：

```text
1. 前端增加 tsgo_storage_version。
2. 版本变化时清理 tsgo_session_id、tsgo_latest_graph、tsgo_latest_summary。
3. WebSocket 建连时后端使用 ensure_session(session_id)，如果是合法但过期的 session_id，则自动重建空 WebSession。
4. 前端在 WebSocket error 时会删除旧 session_id 并重新创建 session。
```

这样普通浏览器中的旧 session/cache 不会再阻塞任务发送；历史 trace 仍然通过 `/api/history` 从本地 trace 文件加载。

## 页面高度与滚动

页面不再展示 EventTimeline。事件仍然保留在前端 state 中，用于运行状态、调试和未来 Inspector 扩展，但不占用主页面空间。

FlowCanvas 的高度跟随流程图内容动态计算：

```text
canvas_height = max(460, max_node_y + 120)
canvas_width  = max(900, max_node_x + 180)
```

纵向空间由浏览器页面滚动条承载，避免在流程图内部再出现局部纵向滚动；横向展开较长时，FlowCanvas 区域保留横向滚动条。

## 节点详情

`StateInspector` 不默认贴整块 JSON，而是按阅读顺序分区展示：

```text
概览
输入
输出
专家选择
Subtask
验证结果
LLM 调用
其他元信息
调试：原始 metadata
```

输入区展示父节点、subtask、分支、prompt id、Operator 类型和 Operator 输入预览；输出区展示摘要、Operator 输出预览、claims、critique、聚合选择和策略；验证区展示 pass、confidence、blocking issues、required edits 和 warnings。原始 metadata 仅作为 debug 折叠项保留。

## 后端结构

```text
src/tsgo/runtime.py          # runtime 入口
src/tsgo/events.py           # TraceEvent / EventSink
src/tsgo/graph.py            # Trace -> GraphSnapshot
src/tsgo/experts/            # 专家化 Operators
src/tsgo/azure_openai_client.py
src/tsgo/deepseek_client.py
src/tsgo/web/app.py          # FastAPI app
src/tsgo/web/sessions.py     # session manager / Web message adapter + history loader
src/tsgo/web/event_bus.py    # AsyncQueueEventSink
src/tsgo/web/schemas.py      # API schemas
```

## 前端结构

```text
web/
├── package.json
├── index.html
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── App.tsx
    ├── style.css
    ├── types.ts
    ├── graph/eventReducer.ts
    └── components/
        ├── ChatPanel.tsx
        ├── FlowCanvas.tsx
        └── StateInspector.tsx
```

## 运行方式

后端：

```bash
pip install -e '.[web,llm]'
uvicorn tsgo.web.app:app --reload
```

前端：

```bash
cd web
npm install
npm run dev
```

默认前端使用 Vite proxy，把同源 `/api` 和 `/ws` 转发到：

```text
http://localhost:8000
ws://localhost:8000
```

## API

```text
POST /api/sessions
POST /api/sessions/{session_id}/messages
GET  /api/sessions/{session_id}/traces/{trace_id}/graph
GET  /api/history
GET  /api/history/{history_id}
WS   /ws/sessions/{session_id}
```

HTTP message body：

```json
{
  "message": "请用二级市场分析师视角分析 AAPL 的中期机会和风险。",
  "num_branches": 1,
  "llm_provider": "deepseek"
}
```

## WebSocket 消息

服务端推送：

```text
run_started
trace_event
graph_node_upsert
graph_edge_upsert
graph_node_patch
pipeline_completed
error
```

`run_started` 会在后端正式开始任务时立即返回，避免真实 LLM 调用期间前端看起来“没有响应”。

## 页面布局

```text
┌──────────────────────────────────────────────────────────┐
│ Header: session / trace / run status                     │
├────────────────────┬───────────────────────┬─────────────┤
│ ChatPanel          │ FlowCanvas             │ Inspector   │
│ 输入 + LLM选择      │ 左到右语义流程图          │ 节点详情      │
└────────────────────┴───────────────────────┴─────────────┘
```
