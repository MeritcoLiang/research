# Operator 伪代码

每个 operator 都遵循同一个契约：

```python
class Operator:
    def run(
        self,
        *,
        user_query: str,
        states: list[ThoughtState],
        trace: Trace,
        context: ContextPacket | None,
        rubric: Rubric | None,
        subtask: Subtask | None = None,
        **kwargs,
    ) -> OperatorResult:
        ...
```

## GenerateOperator

```python
def run_generate(user_query, states, trace, context, rubric, subtasks):
    generated = []
    for subtask in subtasks:
        strategies = choose_generation_strategies(subtask)
        for strategy in strategies:
            prompt = prompter.generate_prompt(
                num_branches=strategy.num_branches,
                user_query=user_query,
                context=context,
                rubric=rubric,
                subtask=subtask,
                strategy=strategy,
            )
            raw_outputs = model.generate(prompt)
            generated.extend(parse_candidate_states(raw_outputs, parent=subtask.id))
    return OperatorResult(new_states=generated)
```

## NormalizeOperator

```python
def run_normalize(states, context, rubric):
    normalized = []
    for state in states:
        prompt = build_normalization_prompt(state, context, rubric)
        raw = model.generate(prompt)
        parsed = parse_claims_assumptions_risks(raw)
        normalized.append(state.with_updates(
            stage="thought_normalizer",
            claims=parsed.claims,
            assumptions=parsed.assumptions,
            failure_modes=parsed.risks,
            status="normalized",
        ))
    return OperatorResult(new_states=normalized)
```

## ScoreOperator

```python
def run_score(states, context, rubric):
    prompt = prompter.score_prompt(
        state_dicts=[s.to_dict() for s in states],
        context=context,
        rubric=rubric,
    )
    raw_scores = model.generate(prompt)
    scores = parse_scores(raw_scores)
    return OperatorResult(new_states=attach_scores(states, scores))
```

## ImproveOperator

```python
def run_improve(states, context, rubric):
    improved = []
    for state in states:
        if not should_improve(state):
            continue
        prompt = prompter.improve_prompt(
            state=state.to_dict(),
            critique=state.critique,
            rubric=rubric,
            context=context,
        )
        raw = model.generate(prompt)
        improved.append(parse_improved_state(raw, parent=state.id))
    return OperatorResult(new_states=improved)
```

## AggregateOperator

```python
def run_aggregate(states, context, rubric):
    top_states = select_top_states(states)
    prompt = prompter.aggregation_prompt(
        state_dicts=[s.to_dict() for s in top_states],
        context=context,
        rubric=rubric,
        aggregation_policy="claim_level_weighted_merge",
    )
    raw = model.generate(prompt)
    aggregated = parse_aggregated_state(raw, parents=[s.id for s in top_states])
    return OperatorResult(new_states=[aggregated])
```

## ValidateOperator

```python
def run_validate(states, user_query, context, rubric):
    final_state = states[-1]
    prompt = prompter.validation_prompt(
        state=final_state.to_dict(),
        user_query=user_query,
        context=context,
        rubric=rubric,
    )
    raw = model.generate(prompt)
    validation = parse_validation(raw)
    if validation.pass_:
        return OperatorResult(new_states=[mark_validated(final_state, validation)])
    return OperatorResult(
        new_states=[mark_rejected_or_needs_repair(final_state, validation)],
        errors=validation.blocking_issues,
    )
```
