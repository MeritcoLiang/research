# Web UI 设计

Web UI 的目标是让用户在浏览器里输入 message，同时实时看到 Pipeline v0.2 的调用流程图。

关键要求：

```text
Web UI 输入 message
  == python tests/demo_pipeline_v02.py "进入 Pipeline v0.2"
```

两者都调用同一个函数：

```python
tsgo.runtime.run_pipeline_message(message)
```

区别只在输出介质：

```text
CLI demo -> terminal + trace file
Web UI   -> browser + WebSocket events + trace file
```

## 后端结构

```text
src/tsgo/runtime.py          # 唯一 pipeline runtime 入口
src/tsgo/events.py           # TraceEvent / EventSink
src/tsgo/graph.py            # Trace -> GraphSnapshot
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
  "content": "进入 Pipeline v0.2",
  "num_branches": 4
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
│ 用户输入            │ 实时 ThoughtState 图     │ 节点详情      │
├────────────────────┴───────────────────────┴─────────────┤
│ EventTimeline                                             │
└──────────────────────────────────────────────────────────┘
```

## 等价性测试

`tests/test_web_message_equivalence.py` 会验证：

```text
run_pipeline_message(message)
```

和：

```text
SessionManager.handle_user_message(message)
```

产生同样的标准化 trace shape。

不比较 UUID / timestamp，因为它们天然随机；比较 stage counts、status counts、final status、final draft marker 和 events 是否存在。
