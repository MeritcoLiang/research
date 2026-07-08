# Implementation Roadmap

## v0.1: Design scaffold

Status: landed.

Scope:

- README
- architecture documentation
- stage documentation
- pseudocode for all stages
- Python schema skeleton
- operator interface skeleton
- deterministic pipeline controller skeleton
- example trace object

## v0.2: Concrete pipeline runner

Goal: run a complete mocked pipeline end-to-end.

Tasks:

1. Implement concrete no-LLM operators for deterministic tests.
2. Add a model-client interface.
3. Add structured JSON parser and repair utilities.
4. Connect the existing prompter-style prompt methods to stage operators.
5. Persist traces to local JSONL.
6. Add unit tests for state lineage and stage contracts.

Deliverable:

```text
python -m tsgo.demo "user query"
```

returns a replayable trace with generated, scored, improved, aggregated, and validated states.

## v0.3: Real LLM integration

Goal: replace mock operators with LLM-backed operators.

Tasks:

1. Implement `GenerateOperator` with strategy-conditioned branching.
2. Implement `NormalizeOperator` with structured claim extraction.
3. Implement `ScoreOperator` with rubric-aware scoring.
4. Implement `ImproveOperator` with critique-guided revision.
5. Implement `AggregateOperator` with claim-level merge.
6. Implement `ValidateOperator` with release-gate checks.

## v0.4: Tool-aware verifier

Goal: use external tools when language-only validation is weak.

Tasks:

- code execution hooks
- retrieval hooks
- citation verification hooks
- calculation hooks
- policy/safety checker hooks

## v0.5: DAG controller

Goal: move from fixed linear pipeline to task-specific DAG execution.

Tasks:

- explicit state graph store
- edge metadata
- dependency-aware scheduler
- per-subtask branching
- top-k pruning

## v1.0: Thought-State Graph Orchestration Engine

Goal: arbitrary graph search over thought states.

Capabilities:

- best-first search
- beam search
- MCTS-style expansion
- learned or hybrid verifier
- adaptive test-time compute
- trace-to-training-data export
