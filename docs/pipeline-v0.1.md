# Pipeline v0.1

Pipeline v0.1 is the first executable shape of the Thought-State Graph Orchestration Engine. It is a linear pipeline with branching inside selected stages.

## Stage order

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

## Why linear first?

A full graph engine requires stable answers to several questions:

- What is a thought state?
- How is a thought scored?
- How does a state record parentage?
- How do we normalize raw generations?
- How do we merge conflicting states?
- What makes a final answer releasable?

Pipeline v0.1 answers those questions before adding graph scheduling.

## High-level flow

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

## Branching points

Branching is allowed inside:

- Candidate Generator: multiple strategy-conditioned drafts
- Verifier / Scorer: multiple scoring lenses
- Improver: multiple repair attempts for promising flawed states
- Aggregator: claim-level synthesis from top states

## Quality gates

A state can be rejected when:

- relevance is too low
- safety score is below threshold
- it violates a hard user constraint
- it contains a critical unsupported claim
- it cannot be repaired within the configured improvement budget

## Default thresholds

```python
MIN_OVERALL_SCORE = 0.78
MIN_RELEVANCE = 0.85
MIN_CORRECTNESS = 0.75
MIN_CLARITY = 0.75
MIN_GROUNDEDNESS = 0.60
MIN_SAFETY = 0.95
```

These thresholds are static in v0.1. They can later become policy-controlled or learned.

## Completion criteria

Pipeline v0.1 is complete when:

1. every stage has a documented contract;
2. every intermediate state is a `ThoughtState`;
3. every candidate can be normalized into claims and assumptions;
4. scoring is multi-dimensional;
5. aggregation is claim-level and conflict-aware;
6. final validation can block unsafe or low-quality responses;
7. the entire run is logged as a replayable trace.
