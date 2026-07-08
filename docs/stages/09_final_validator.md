# 09 Final Validator

## 目的

判断聚合后的答案是否安全、可靠，是否足以发送给用户。这是发布门禁，不是又一轮普通评分。

## 输入

```text
Aggregated ThoughtState
user_query
ContextPacket
Rubric
validation policy
```

## 输出

验证通过的最终 `ThoughtState`，或被拒绝 / 需要修复的状态：

```text
status="validated" or "rejected"
metadata.validation.pass
metadata.validation.blocking_issues
metadata.validation.required_edits
metadata.validation.confidence
```

## 伪代码

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

## 验证问题

```text
最终答案是否回答了这个用户请求？
是否满足所有硬约束？
冲突是否被解决或显式披露？
高风险 claims 是否有支撑？
不确定性是否被校准？
答案对用户是否可用？
是否存在安全或合规问题？
```

## 失败模式

- 把 validation 当成又一次重写机会。
- 放行无依据的高置信 claims。
- 忽略用户硬约束。
- 没有拦截不安全建议。

## 验收标准

- pass/fail 是显式的。
- blocking issues 和 non-blocking issues 分开。
- required edits 是可执行的。
- 如果验证失败，答案只修复一次，或者返回 not ready。
