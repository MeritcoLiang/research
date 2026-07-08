# Stage Index

Pipeline v0.1 has eleven stages. Each stage has a stable contract so it can later become a node type in the full thought-state graph engine.

| Stage | Document | Main output |
| --- | --- | --- |
| 00 | [Task Intake](stages/00_task_intake.md) | `TaskInfo` |
| 01 | [Context Builder](stages/01_context_builder.md) | `ContextPacket` |
| 02 | [Rubric Builder](stages/02_rubric_builder.md) | `Rubric` |
| 03 | [Problem Decomposer](stages/03_problem_decomposer.md) | `Subtask[]` |
| 04 | [Candidate Generator](stages/04_candidate_generator.md) | generated `ThoughtState[]` |
| 05 | [Thought Normalizer](stages/05_thought_normalizer.md) | normalized `ThoughtState[]` |
| 06 | [Verifier / Scorer](stages/06_verifier_scorer.md) | scored `ThoughtState[]` |
| 07 | [Improver](stages/07_improver.md) | improved `ThoughtState[]` |
| 08 | [Aggregator](stages/08_aggregator.md) | aggregated `ThoughtState` |
| 09 | [Final Validator](stages/09_final_validator.md) | validated final `ThoughtState` |
| 10 | [Trace Logger](stages/10_trace_logger.md) | persisted `Trace` |

## Cross-stage invariants

Every stage must preserve:

1. `user_query`
2. state lineage through `id` and `parent_ids`
3. hard user constraints
4. trace metadata
5. enough structured fields for downstream scoring and aggregation

## Stage contract template

Each stage document follows this shape:

```text
Purpose
Inputs
Outputs
Pseudocode
Failure modes
Acceptance criteria
```
