# 03 Problem Decomposer

## 目的

将用户请求拆成更小的工作单元，使每个单元都可以独立生成、评分、改进和聚合。

## 输入

```text
user_query
TaskInfo
ContextPacket
Rubric
```

## 输出

`list[Subtask]`：

```text
id
question
task_type
required_outputs
dependencies
metadata
```

## 伪代码

```python
def decompose_problem(user_query: str, context: ContextPacket, rubric: Rubric) -> list[Subtask]:
    if is_simple_task(user_query):
        return [Subtask(id="s0", question=user_query, task_type="unknown")]

    candidate_subtasks = propose_subtasks(user_query, context, rubric)
    candidate_subtasks = remove_duplicates(candidate_subtasks)
    candidate_subtasks = order_by_dependency(candidate_subtasks)
    candidate_subtasks = enforce_coverage(candidate_subtasks, context.hard_constraints)

    return candidate_subtasks
```

## 拆解规则

一个好的 subtask 应该：

- 可以被独立回答；
- 容易验证；
- 足够小，适合分支搜索；
- 能映射到最终答案的一个或多个部分；
- 可以追溯到用户意图。

## 失败模式

- 对简单请求过度拆解。
- 生成无法独立验证的 subtasks。
- 丢失关键用户约束。
- 产生循环依赖。

## 验收标准

- 每个 subtask 有稳定 ID。
- required outputs 明确。
- 必要时 dependencies 明确。
- 所有 subtasks 合起来覆盖原始请求。
