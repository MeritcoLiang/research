# 00 Task Intake

## 目的

在投入大量 inference 预算之前，先对用户请求进行分类。该阶段决定后续应走哪类处理路径，以及应该分配多少 test-time compute。

## 输入

```text
user_query
conversation_context 可选
available_artifacts 可选
```

## 输出

`TaskInfo`：

```text
task_type
difficulty
requires_tools
requires_citations
requires_computation
requires_user_context
answer_format
metadata
```

## 伪代码

```python
def task_intake(user_query: str) -> TaskInfo:
    signals = analyze_query(user_query)

    task_type = classify_task_type(signals)
    difficulty = estimate_difficulty(signals)

    return TaskInfo(
        user_query=user_query,
        task_type=task_type,
        difficulty=difficulty,
        requires_tools=detect_tool_need(signals),
        requires_citations=detect_citation_need(signals),
        requires_computation=detect_computation_need(signals),
        requires_user_context=detect_user_context_need(signals),
        answer_format=infer_answer_format(signals),
        metadata={"signals": signals},
    )
```

## 失败模式

- 把 research task 误判为纯 reasoning task。
- 漏掉 citations 或 tools 的需求。
- 低估难度，导致分支数量不足。
- 忽略用户显式约束。

## 验收标准

- 阶段返回结构化 `TaskInfo` 对象。
- 用户请求中的硬要求被保留下来。
- 下游阶段可以根据结果选择 branch count 和 verifier 类型。
- 模糊性被记录到 metadata，而不是静默丢弃。
