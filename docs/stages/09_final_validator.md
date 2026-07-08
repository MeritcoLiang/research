# 09 Final Validator

## Purpose

Decide whether the aggregated answer is safe and good enough to send. This is a release gate, not another general scoring pass.

## Inputs

```text
Aggregated ThoughtState
user_query
ContextPacket
Rubric
validation policy
```

## Outputs

Validated final `ThoughtState` or a rejected/repair-required state:

```text
status="validated" or "rejected"
metadata.validation.pass
metadata.validation.blocking_issues
metadata.validation.required_edits
metadata.validation.confidence
```

## Pseudocode

```python
def validate_final_answer(state: ThoughtState, user_query: str, context: ContextPacket, rubric: Rubric):
    checks = [
        answers_user_query(state, user_query),
        satisfies_hard_constraints(state, context.hard_constraints),
        has_no_unresolved_conflicts(state),
        has_no_unsupported_high_risk_claims(state),
        is_uncertainty_calibrated(state),
        is_clear_and_actionable(state, rubric),
        passes_safety_policy(state),
    ]

    blocking = [check.message for check in checks if not check.pass_ and check.blocking]
    required_edits = [check.repair for check in checks if not check.pass_ and check.repair]

    if blocking:
        return ValidationResult(
            pass_=False,
            blocking_issues=blocking,
            required_edits=required_edits,
            confidence=estimate_confidence(checks),
        )

    return ValidationResult(
        pass_=True,
        blocking_issues=[],
        required_edits=[],
        confidence=estimate_confidence(checks),
    )
```

## Validation questions

```text
Does the final answer answer this user query?
Does it satisfy all hard constraints?
Are conflicts resolved or explicitly disclosed?
Are high-risk claims supported?
Is uncertainty calibrated?
Is the answer usable by the user?
Is there any safety or compliance issue?
```

## Failure modes

- Treats validation as another rewrite opportunity.
- Lets unsupported confident claims pass.
- Ignores user hard constraints.
- Fails to block unsafe recommendations.

## Acceptance criteria

- Pass/fail is explicit.
- Blocking issues are separated from non-blocking issues.
- Required edits are actionable.
- If validation fails, the answer is repaired once or returned as not ready.
