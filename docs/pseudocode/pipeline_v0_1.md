# Pipeline v0.1 Pseudocode

```python
def run_pipeline(user_query: str) -> ThoughtState:
    trace = Trace(id=new_trace_id(), user_query=user_query)

    root = ThoughtState(
        id=new_state_id("root"),
        parent_ids=[],
        stage="root",
        user_query=user_query,
        draft=user_query,
    )
    trace.add_state(root)

    # 00. Task intake
    task_info = task_intake(user_query)
    trace.task_info = task_info

    # 01. Context builder
    context = build_context(user_query, task_info)
    trace.context = context

    # 02. Rubric builder
    rubric = build_rubric(user_query, task_info, context)
    trace.rubric = rubric

    # 03. Problem decomposer
    subtasks = decompose_problem(user_query, context, rubric)
    trace.subtasks = subtasks

    # 04. Candidate generator
    candidates = []
    for subtask in subtasks:
        branches = choose_branch_count(task_info, subtask)
        candidates.extend(
            generate_candidates(
                user_query=user_query,
                context=context,
                rubric=rubric,
                subtask=subtask,
                num_branches=branches,
            )
        )
    trace.add_states(candidates)

    # 05. Thought normalizer
    normalized = []
    for candidate in candidates:
        normalized_state = normalize_thought(candidate, context, rubric)
        normalized.append(normalized_state)
    trace.add_states(normalized)

    # 06. Verifier / scorer
    scored = []
    for state in normalized:
        scored_state = score_thought(state, context, rubric)
        scored.append(scored_state)
    trace.add_states(scored)

    # 07. Improver
    improved = []
    for state in scored:
        if should_improve(state):
            repaired = improve_thought(state, context, rubric)
            repaired = normalize_thought(repaired, context, rubric)
            repaired = score_thought(repaired, context, rubric)
            improved.append(repaired)
    trace.add_states(improved)

    # Select candidate pool
    candidate_pool = select_candidate_pool(scored + improved)

    # 08. Aggregator
    aggregated = aggregate_thoughts(candidate_pool, context, rubric)
    trace.add_state(aggregated)

    # 09. Final validator
    validation = validate_final_answer(aggregated, user_query, context, rubric)
    if not validation.pass_:
        aggregated = repair_final_answer(aggregated, validation.required_edits)
        validation = validate_final_answer(aggregated, user_query, context, rubric)
    trace.add_state(validation.state)

    # 10. Trace logger
    persist_trace(trace)

    return validation.state
```

## Candidate selection pseudocode

```python
def should_reject(state: ThoughtState) -> bool:
    return (
        has_critical_error(state)
        or state.score.relevance < MIN_RELEVANCE
        or state.score.safety < MIN_SAFETY
        or violates_hard_constraints(state)
    )


def should_improve(state: ThoughtState) -> bool:
    return (
        not should_reject(state)
        and state.score.overall < MIN_OVERALL_SCORE
        and has_actionable_critique(state)
    )


def select_candidate_pool(states: list[ThoughtState]) -> list[ThoughtState]:
    accepted = [s for s in states if not should_reject(s)]
    diverse = diversity_filter(accepted)
    return top_k(diverse, key=lambda s: s.score.overall)
```

## Aggregation pseudocode

```python
def aggregate_thoughts(states: list[ThoughtState], context, rubric):
    claims = extract_all_claims(states)
    claims = deduplicate_claims(claims)
    conflicts = detect_conflicts(claims)

    resolved_claims = []
    for group in conflicts:
        winner = resolve_conflict(
            group,
            priority=[
                "hard_user_constraints",
                "verifier_score",
                "evidence_strength",
                "engineering_actionability",
            ],
        )
        resolved_claims.append(winner)

    non_conflicting_claims = select_high_confidence_non_conflicting_claims(claims)
    final_claims = non_conflicting_claims + resolved_claims

    return synthesize_final_answer(final_claims, context, rubric)
```
