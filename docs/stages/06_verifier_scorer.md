# 06 Verifier / Scorer

## Purpose

Evaluate normalized thought states using the task-specific rubric. This stage should produce multi-dimensional scores, critique, critical errors, and improvement instructions.

## Inputs

```text
Normalized ThoughtState[]
ContextPacket
Rubric
optional tool outputs
```

## Outputs

Scored `ThoughtState[]` with:

```text
score
critique
failure_modes
claim verifier notes
status="scored"
```

## Pseudocode

```python
def score_thoughts(states: list[ThoughtState], context: ContextPacket, rubric: Rubric) -> list[ThoughtState]:
    prompt = prompter.score_prompt(
        state_dicts=[state.to_dict() for state in states],
        context=context,
        rubric=rubric,
        scoring_schema={
            "correctness": "0..1",
            "completeness": "0..1",
            "relevance": "0..1",
            "clarity": "0..1",
            "groundedness": "0..1",
            "safety": "0..1",
            "actionability": "0..1",
            "overall": "0..1",
            "strengths": "string[]",
            "weaknesses": "string[]",
            "critical_errors": "string[]",
            "improvement_instructions": "string[]",
        },
    )
    raw = model.generate(prompt)
    score_packets = parse_scores(raw)

    scored = []
    for state, packet in zip(states, score_packets):
        scored.append(state_with_score_and_critique(state, packet))
    return scored
```

## Scoring layers

```text
L1: deterministic rule checks
L2: LLM judge or reward model
L3: tool/environment validation when available
```

## Failure modes

- Uses only one overall score.
- Rewards verbosity instead of correctness.
- Fails to separate critical errors from minor issues.
- Lets a candidate judge itself without independent checks.

## Acceptance criteria

- Scores are multi-dimensional.
- Critique is actionable.
- Critical errors are explicitly marked.
- Claims receive verifier notes when possible.
- The same rubric can be used later by the aggregator.
