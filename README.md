# Thought-State Graph Orchestration Engine

This repository is the engineering landing zone for a staged **Thought-State Graph Orchestration Engine**. The current implementation target is **Pipeline v0.1**: a linear-but-branching thought-state orchestration pipeline that can later evolve into a full graph scheduler.

The project starts from the core insight that high-quality AI answers should not be produced by a single prompt-response call. Instead, every intermediate thought should be structured, scored, improved, validated, aggregated, and logged.

## Current target: Pipeline v0.1

Pipeline v0.1 intentionally avoids a full arbitrary graph engine at first. It establishes the stable interfaces that the future graph engine will need:

```text
User Query
  -> 00 Task Intake
  -> 01 Context Builder
  -> 02 Rubric Builder
  -> 03 Problem Decomposer
  -> 04 Candidate Generator
  -> 05 Thought Normalizer
  -> 06 Verifier / Scorer
  -> 07 Improver
  -> 08 Aggregator
  -> 09 Final Validator
  -> 10 Trace Logger
```

The first engineering rule is:

> Every stage consumes structured state and returns structured state.

## Why this matters

A simple multi-answer workflow is useful, but it is not enough. The stronger design is:

```text
Generate diverse candidates
  -> normalize into claims, assumptions, risks
  -> score with a task-specific rubric
  -> improve only the promising flawed states
  -> aggregate at claim level
  -> validate before final output
  -> log the complete trace for debugging, evals, and future training data
```

This gives us the foundations for:

- adaptive test-time compute
- claim-level verification
- conflict-aware aggregation
- reproducible answer traces
- future search policies such as beam search, best-first search, MCTS, and arbitrary thought graphs

## Repository structure

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── tsgo/
│       ├── __init__.py
│       ├── schema.py
│       ├── operators.py
│       └── pipeline.py
├── docs/
│   ├── architecture.md
│   ├── pipeline-v0.1.md
│   ├── implementation-roadmap.md
│   ├── stage-index.md
│   ├── pseudocode/
│   │   ├── pipeline_v0_1.md
│   │   └── operators.md
│   └── stages/
│       ├── 00_task_intake.md
│       ├── 01_context_builder.md
│       ├── 02_rubric_builder.md
│       ├── 03_problem_decomposer.md
│       ├── 04_candidate_generator.md
│       ├── 05_thought_normalizer.md
│       ├── 06_verifier_scorer.md
│       ├── 07_improver.md
│       ├── 08_aggregator.md
│       ├── 09_final_validator.md
│       └── 10_trace_logger.md
└── examples/
    └── pipeline_trace_example.json
```

## Stage documentation

Each stage has its own document with:

- purpose
- inputs
- outputs
- pseudocode
- failure modes
- acceptance criteria

Start here:

- [Architecture](docs/architecture.md)
- [Pipeline v0.1](docs/pipeline-v0.1.md)
- [Stage Index](docs/stage-index.md)
- [Pipeline pseudocode](docs/pseudocode/pipeline_v0_1.md)
- [Operator pseudocode](docs/pseudocode/operators.md)

## Core abstractions

The current implementation uses four core abstractions:

1. `ThoughtState`: one candidate answer, sub-answer, critique, revision, aggregation, or final response.
2. `Operator`: a transformation from one or more states into one or more states.
3. `PipelineController`: a deterministic v0.1 controller that executes the current stage order.
4. `Trace`: a replayable record of all states, scores, improvements, and validations.

## Prompter interface mapping

The existing prompter abstraction maps cleanly into the pipeline:

| Prompter method | Pipeline stage | Role |
| --- | --- | --- |
| `generate_prompt(num_branches)` | 04 Candidate Generator | Branch expansion |
| `score_prompt(state_dicts)` | 06 Verifier / Scorer | Multi-state evaluation |
| `improve_prompt()` | 07 Improver | Critique-guided revision |
| `aggregation_prompt(state_dicts)` | 08 Aggregator | Claim-level synthesis |
| `validation_prompt()` | 09 Final Validator | Release gate |

## Development status

Current status: **Pipeline v0.1 design scaffold landed**.

Implemented now:

- documentation for all stages
- pseudocode for all stages
- Python schema skeleton
- operator interface skeleton
- deterministic pipeline controller skeleton
- example trace object

Not implemented yet:

- model client integration
- concrete prompt templates
- JSON output parser and repair
- tool execution runtime
- learned verifier / reward model
- arbitrary graph scheduler

## Next milestone

The next milestone is **Pipeline v0.2**:

```text
Prompter integration
  -> structured JSON contracts
  -> mock LLM runner
  -> trace persistence
  -> one end-to-end demo
```

After v0.2 stabilizes, the system can evolve toward:

```text
linear pipeline -> DAG controller -> graph controller -> search policy engine -> learned verifier loop
```
