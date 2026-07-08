# Pipeline v0.1

Pipeline v0.1 是 Thought-State Graph Orchestration Engine 的第一个可执行形态。它是一条线性流水线，但在部分阶段内部允许多分支。

## 阶段顺序

```text
00 Task Intake
01 Context Builder
02 Rubric Builder
03 Problem Decomposer
04 Candidate Generator
05 Thought Normalizer
06 Verifier / Scorer
07 Improver
08 Aggregator
09 Final Validator
10 Trace Logger
```

## 为什么先做线性 pipeline？

完整图引擎需要先稳定回答几个问题：

- 什么是 thought state？
- thought 如何评分？
- state 如何记录父子关系？
- 原始生成结果如何规范化？
- 冲突状态如何合并？
- 什么样的最终答案可以发布？

Pipeline v0.1 先回答这些问题，再增加图调度能力。

## 高层流程

```text
user_query
  -> task_info
  -> context_packet
  -> rubric
  -> subtasks
  -> candidate_states
  -> normalized_states
  -> scored_states
  -> improved_states
  -> aggregated_state
  -> validated_state
  -> trace
```

## 分支点

允许分支的阶段包括：

- Candidate Generator：生成多种策略条件下的草稿
- Verifier / Scorer：使用多种评分视角
- Improver：对有潜力但有缺陷的状态进行多次修复尝试
- Aggregator：从 top states 做 claim 级综合

## 质量门禁

当状态满足以下情况时，可以被拒绝：

- relevance 过低
- safety score 低于阈值
- 违反用户硬约束
- 包含关键且无支撑的 claim
- 在配置的改进预算内无法修复

## 默认阈值

```python
MIN_OVERALL_SCORE = 0.78
MIN_RELEVANCE = 0.85
MIN_CORRECTNESS = 0.75
MIN_CLARITY = 0.75
MIN_GROUNDEDNESS = 0.60
MIN_SAFETY = 0.95
```

这些阈值在 v0.1 中是静态的。之后可以升级为 policy-controlled 或 learned。

## 完成标准

Pipeline v0.1 完成时应满足：

1. 每个阶段都有明确文档契约；
2. 每个中间状态都是 `ThoughtState`；
3. 每个候选都可以被规范化为 claims 和 assumptions；
4. 评分是多维度的；
5. 聚合是 claim 级、冲突感知的；
6. 最终验证可以拦截不安全或低质量回复；
7. 整个运行过程被记录为可回放 trace。
