# 01 Context Builder

## 目的

将原始上下文整理为显式的 `ContextPacket`。该阶段负责区分硬约束、软偏好、已有证据、缺失信息以及可能需要的工具计划。

## 输入

```text
user_query
TaskInfo
conversation_context
uploaded_files
retrieved_sources 可选
tool_outputs 可选
```

## 输出

`ContextPacket`：

```text
user_intent
hard_constraints
soft_preferences
available_context
missing_context
retrieved_evidence
tool_plan
metadata
```

## 伪代码

```python
def build_context(user_query: str, task_info: TaskInfo) -> ContextPacket:
    intent = infer_user_intent(user_query, task_info)
    hard_constraints = extract_hard_constraints(user_query)
    soft_preferences = extract_soft_preferences(user_query)

    evidence = collect_available_evidence(user_query, task_info)
    missing = detect_missing_context(user_query, task_info, evidence)
    tool_plan = plan_tools(task_info, missing)

    return ContextPacket(
        user_intent=intent,
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        available_context=summarize_context(evidence),
        missing_context=missing,
        retrieved_evidence=evidence,
        tool_plan=tool_plan,
    )
```

## 失败模式

- 把软偏好当作硬约束。
- 在总结上下文时丢失硬约束。
- 没有标记缺失信息。
- 检索了上下文，但没有保留 source metadata。

## 验收标准

- 用户意图被显式写出。
- 硬约束是机器可读的。
- 缺失上下文不会被隐藏。
- 证据带有 ID，后续 claims 可以引用。
