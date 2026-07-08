# 10 Trace Logger

## Purpose

Persist the full run so the system can be debugged, replayed, evaluated, and later converted into training or preference data.

## Inputs

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

## Outputs

Persisted trace object:

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

## Pseudocode

```python
def persist_trace(trace: Trace, sink: TraceSink) -> None:
    serialized = trace.to_dict()
    validate_trace_schema(serialized)
    sink.write(serialized)
```

## Trace uses

```text
Debugging: inspect why a final answer passed.
Eval: measure quality across a benchmark set.
Regression: catch prompt or model changes that degrade quality.
Optimization: compare branch counts and search policies.
Training: export preference pairs, critiques, and repaired states.
```

## Failure modes

- Logs only the final answer.
- Drops parent-child lineage.
- Stores raw model outputs without parsed structure.
- Does not capture failed states, which are important training data.
- Cannot reproduce the exact configuration used.

## Acceptance criteria

- Every state has an ID and parent IDs.
- Scores and critiques are preserved.
- Rejected states are preserved.
- Operator logs and errors are preserved.
- Trace includes enough metadata to replay or audit the run.
