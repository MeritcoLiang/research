# 10 Trace Logger

## 目的

持久化完整运行过程，使系统可以被调试、回放、评测，并在未来转成训练或偏好数据。

## 输入

```text
Trace
all ThoughtState objects
TaskInfo
ContextPacket
Rubric
Subtask[]
operator logs
validation result
```

## 输出

持久化后的 trace 对象：

```text
trace_id
query
state lineage
scores
critiques
improvements
aggregation metadata
validation metadata
model/tool metadata
```

## 伪代码

```python
def persist_trace(trace: Trace, sink: TraceSink) -> None:
    serialized = trace.to_dict()
    validate_trace_schema(serialized)
    sink.write(serialized)
```

## Trace 用途

```text
Debugging: 检查最终答案为什么通过。
Eval: 在 benchmark set 上度量质量。
Regression: 捕捉 prompt 或 model 变化造成的质量退化。
Optimization: 比较 branch counts 和 search policies。
Training: 导出 preference pairs、critiques 和 repaired states。
```

## 失败模式

- 只记录最终答案。
- 丢失父子谱系。
- 只保存 raw model outputs，没有保存 parsed structure。
- 不保存 failed states，而这些往往是重要训练数据。
- 无法复现当时使用的配置。

## 验收标准

- 每个 state 都有 ID 和 parent IDs。
- scores 和 critiques 被保留。
- rejected states 被保留。
- operator logs 和 errors 被保留。
- trace 包含足够 metadata，可以 replay 或 audit 本次运行。
