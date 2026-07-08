# 02 Rubric Builder

## 目的

在生成候选之前，先建立任务的目标函数。Rubric 可以避免 scorer 和 aggregator 被第一个候选答案锚定。

## 输入

```text
user_query
TaskInfo
ContextPacket
```

## 输出

`Rubric`：

```text
items: list[RubricItem]
hard_constraints
soft_preferences
```

## 伪代码

```python
def build_rubric(user_query: str, task_info: TaskInfo, context: ContextPacket) -> Rubric:
    if task_info.task_type == "coding":
        items = coding_rubric()
    elif task_info.task_type == "research":
        items = research_rubric()
    elif task_info.task_type == "reasoning":
        items = reasoning_rubric()
    else:
        items = general_answer_quality_rubric()

    items = adapt_weights(items, difficulty=task_info.difficulty, intent=context.user_intent)

    return Rubric(
        items=items,
        hard_constraints=context.hard_constraints,
        soft_preferences=context.soft_preferences,
    )
```

## 默认通用 rubric

```text
correctness: 0.30
completeness: 0.20
actionability: 0.20
groundedness: 0.15
clarity: 0.10
risk_control: 0.05
```

## 失败模式

- 生成了不区分任务类型的通用 rubric。
- 过度奖励文风，低估 correctness。
- 没有纳入硬约束。
- 创建了无法评分的标准。

## 验收标准

- candidate generation 之前已经存在 rubric。
- 权重构成合理目标函数。
- 硬约束被纳入 rubric。
- scorer 和 aggregator 可以使用同一套 rubric。
