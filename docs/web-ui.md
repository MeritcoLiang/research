# Web UI 设计

Web UI 的目标是让用户在浏览器里输入 message，同时实时看到 Thought-State Graph Orchestration Engine 的 Stage 调用流程图。

当前 Web UI 默认运行 **SecondaryMarketAnalyst Stage flow**。

关键要求：

```text
Web UI 输入 message
  == python tests/demo_secondary_market_stage_flow.py "请用二级市场分析师视角分析 AAPL 的中期机会和风险。"
```

两者都调用同一个函数：

```python
tsgo.runtime.run_secondary_market_stage_flow(message)
```

区别只在输出介质：

```text
CLI demo -> terminal + trace file
Web UI   -> browser + WebSocket events + trace file + GraphSnapshot
```

## 可视化原则

流程图的用户可见标签必须语义化，不展示内部 `state_id`。`state_id` 只作为 React Flow 的内部 key 和调试 metadata 使用。

主流程采用**从左到右**的层级展开，因为完整分支较多，横向布局比自上而下更舒展：

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

这样线条会从左侧矩形的右边接出，进入右侧矩形的左边，而不是从上下边或节点中心乱连。边的 `handoff` / `decomposes_to` / `parent` 类型保存在 edge data 中，不作为主图 label 展示，避免画面噪声。

推荐可见标签：

```text
root
expert SecondaryMarketAnalyst
subtask s1
candidate
s1 · bull case
normalized
scored
0.82
aggregation
validation
```

不推荐：

```text
candidate_8ac2...
normalized_f91b...
scored_42ab...
validated_98d...
```

## 布局规则

前端 `web/src/graph/eventReducer.ts` 使用语义布局常量：

```text
root:        x = 0
expert:      x = 260
subtask:     x = 540
candidate:   x = 880
normalized:  x = 1220
scored:      x = 1560
improved:    x = 1900
aggregation: x = 2240
validation:  x = 2540
```

每个 subtask 占一个纵向分组，每个 candidate 分支在该 subtask 分组内向下展开。normalized / scored / validation 节点优先跟随 parent 的 y 坐标，因此一条分支在视觉上形成横向链路。

刷新页面后，前端会从 `localStorage` 恢复最新 graph snapshot；一次 pipeline 完成时，后端返回完整 graph snapshot，前端用 snapshot hydrate 全图，避免仅依赖增量事件造成 root、expert 或 subtask 丢失。

## 后端结构

```text
src/tsgo/runtime.py          # 唯一 runtime 入口
src/tsgo/events.py           # TraceEvent / EventSink
src/tsgo/graph.py            # Trace -> GraphSnapshot
src/tsgo/experts/            # 专家化 Operators
src/tsgo/web/app.py          # FastAPI app
src/tsgo/web/sessions.py     # session manager / Web message adapter
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
        ├── StateInspector.tsx
        └── EventTimeline.tsx
```

## 运行方式

后端：

```bash
pip install -e '.[web]'
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

也可以通过 `VITE_API_BASE` / `VITE_WS_BASE` 覆盖。

## API

```text
POST /api/sessions
POST /api/sessions/{session_id}/messages
GET  /api/sessions/{session_id}/traces/{trace_id}/graph
WS   /ws/sessions/{session_id}
```

## WebSocket 消息

用户发送：

```json
{
  "type": "user_message",
  "content": "请用二级市场分析师视角分析 AAPL 的中期机会和风险。",
  "num_branches": 6
}
```

服务端推送：

```text
trace_event
graph_node_upsert
graph_edge_upsert
graph_node_patch
pipeline_completed
error
```

## 页面布局

```text
┌──────────────────────────────────────────────────────────┐
│ Header: session / trace / run status                     │
├────────────────────┬───────────────────────┬─────────────┤
│ ChatPanel          │ FlowCanvas             │ Inspector   │
│ 用户输入            │ 左到右语义流程图          │ 节点详情      │
├────────────────────┴───────────────────────┴─────────────┤
│ EventTimeline                                             │
└──────────────────────────────────────────────────────────┘
```

`StateInspector` 默认展示节点标签、阶段、状态、评分、摘要；内部 ID 和 metadata 放入“调试信息”折叠区。

## 等价性测试

`tests/test_web_message_equivalence.py` 会验证：

```text
run_secondary_market_stage_flow(message)
```

和：

```text
SessionManager.handle_user_message(message)
```

产生同样的标准化 trace shape。

不比较 UUID / timestamp，因为它们天然随机；比较 stage counts、status counts、final status、expert handoff、final draft marker 和 events 是否存在。
