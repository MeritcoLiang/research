# 事件流设计

Pipeline v0.2 增加 `TraceEvent`，用于让 CLI、测试和 Web UI 观察同一条 runtime 执行路径。

事件流展示的是系统显式状态，不展示模型隐藏 chain-of-thought。

## 事件模型

```python
@dataclass
class TraceEvent:
    event_id: str
    trace_id: str
    session_id: str | None
    event_type: str
    stage: str | None
    state_id: str | None
    parent_ids: list[str]
    payload: dict[str, Any]
    timestamp: str
```

## 事件类型

当前 PipelineController 会发出：

```text
pipeline_started
stage_started
state_created
edge_created
score_updated
stage_completed
pipeline_completed
pipeline_error
```

## 发出时机

```text
run() 开始
  -> pipeline_started
root 创建
  -> state_created
每个 stage 开始
  -> stage_started
operator 返回新状态
  -> state_created
  -> edge_created
  -> score_updated 可选
每个 stage 结束
  -> stage_completed
run() 完成
  -> pipeline_completed
异常
  -> pipeline_error
```

## EventSink

`EventSink` 是同步接口：

```python
class EventSink(Protocol):
    def emit(self, event: TraceEvent) -> None:
        ...
```

当前实现：

```text
NoopEventSink         # 默认，不做实时消费
InMemoryEventSink     # 测试使用
AsyncQueueEventSink   # WebSocket 使用
```

## WebSocket 映射

WebSocket 后端会发送两类消息：

1. 原始事件：

```json
{
  "type": "trace_event",
  "event": {
    "event_type": "state_created",
    "stage": "candidate_generator",
    "state_id": "candidate_xxx"
  }
}
```

2. 图增量：

```json
{
  "type": "graph_node_upsert",
  "trace_id": "trace_xxx",
  "node": {
    "id": "candidate_xxx",
    "stage": "candidate_generator",
    "status": "draft"
  }
}
```

## Graph reducer 映射

```text
state_created -> graph_node_upsert
edge_created  -> graph_edge_upsert
score_updated -> graph_node_patch
```

运行结束后，前端也可以通过完整 trace snapshot 重建流程图。

## 安全边界

允许展示：

- `ThoughtState`
- `claims`
- `assumptions`
- `score`
- `critique`
- `metadata`
- `operator logs`
- `trace events`

不展示：

- 模型隐藏 chain-of-thought
- 未经处理的私有 reasoning
- API key / 环境变量 / secrets
