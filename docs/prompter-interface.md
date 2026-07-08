# Prompter Interface Mapping

The current research scaffold assumes a prompter abstraction with five prompt-generation methods:

```text
generate_prompt(num_branches)
score_prompt(state_dicts)
improve_prompt()
aggregation_prompt(state_dicts)
validation_prompt()
```

Pipeline v0.1 treats those methods as prompt-level adapters for thought-state operators.

## Mapping

| Prompter method | Operator | Stage | Expected role |
| --- | --- | --- | --- |
| `generate_prompt(num_branches)` | `GenerateOperator` | 04 Candidate Generator | Generate diverse candidate branches. |
| `score_prompt(state_dicts)` | `ScoreOperator` | 06 Verifier / Scorer | Score one or more states against the rubric. |
| `improve_prompt()` | `ImproveOperator` | 07 Improver | Repair a specific flawed state using verifier critique. |
| `aggregation_prompt(state_dicts)` | `AggregateOperator` | 08 Aggregator | Merge top states at claim level. |
| `validation_prompt()` | `ValidateOperator` | 09 Final Validator | Decide whether the final state is releasable. |

## Contract upgrade

The prompter returns strings. Pipeline v0.1 wraps those strings with structured contracts:

```text
Prompter -> prompt string
ModelClient -> raw model output
Parser -> structured packet
Operator -> ThoughtState / OperatorResult
Trace -> replayable run record
```

This separation keeps the future graph engine independent from any single model provider or prompt template.

## Required parser outputs

Each operator should parse model output into a known schema:

```text
GenerateOperator -> candidate drafts
NormalizeOperator -> claims, assumptions, risks, missing info
ScoreOperator -> multi-dimensional score, critique, critical errors
ImproveOperator -> repaired draft and change summary
AggregateOperator -> final draft, selected claims, conflicts, resolutions
ValidateOperator -> pass/fail, blocking issues, required edits, confidence
```

## Design note

The prompter should remain a prompt-construction layer, not the orchestration layer. The orchestration layer owns:

- stage order
- branching policy
- state IDs
- parent lineage
- thresholds
- retry policy
- trace logging
- aggregation policy
