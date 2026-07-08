# Architecture

The long-term target is a **Thought-State Graph Orchestration Engine**. The current repository lands the first stable engineering layer: **Pipeline v0.1**.

Pipeline v0.1 is deliberately not a full graph engine. It is a deterministic orchestration scaffold that makes every intermediate thought structured, scoreable, improvable, aggregatable, and traceable.

## Design principle

```text
Do not pass raw strings between stages.
Pass ThoughtState objects.
```

A raw string cannot be reliably scored, merged, replayed, or converted into training data. A structured state can.

## System layers

```text
Application / User Request
  -> PipelineController
  -> Operators
  -> Prompter / Model Client / Tool Runtime
  -> Structured Parser
  -> ThoughtState / Trace Store
```

## Core objects

### ThoughtState

A `ThoughtState` is the atomic orchestration unit. It can represent:

- a root user request
- a decomposed sub-answer
- a generated candidate
- a normalized thought
- a scored thought
- an improved thought
- an aggregation
- a final validated answer

Every state has:

```text
id
parent_ids
stage
user_query
draft
claims
assumptions
evidence
score
critique
status
metadata
```

### Operator

An `Operator` transforms one or more states into one or more states.

Examples:

```text
GenerateOperator: root/subtask -> candidate states
NormalizeOperator: candidate -> structured claims
ScoreOperator: normalized states -> scored states
ImproveOperator: flawed state -> improved state
AggregateOperator: top states -> aggregated state
ValidateOperator: aggregated state -> validated final state
```

### Trace

A `Trace` is a replayable record of the full run. It is the foundation for:

- debugging
- regression testing
- evals
- prompt optimization
- future SFT/DPO/RL data generation

## Evolution path

```text
Pipeline v0.1
  -> Pipeline v0.2 with concrete prompter integration
  -> DAG controller
  -> arbitrary thought-state graph
  -> search policy engine
  -> learned verifier / reward model loop
```

The key is to stabilize state, operator contracts, and trace logging before adding graph search complexity.

## Non-goals for v0.1

Pipeline v0.1 does not implement:

- arbitrary graph scheduling
- MCTS
- learned reward models
- external tool runtime
- production model client
- persistence layer

Those are later milestones.
