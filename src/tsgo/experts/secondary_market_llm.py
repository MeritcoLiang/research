"""SecondaryMarketAnalyst Stage flow with LLM-implemented Operators.

This keeps the documented expert handoff, context, rubric, and six-subtask
problem decomposition, then uses LLM Operators for generation, normalization,
scoring, improvement, aggregation, and validation.
"""

from __future__ import annotations

from ..llm_operators import (
    LLMAggregatorOperator,
    LLMCandidateGeneratorOperator,
    LLMFinalValidatorOperator,
    LLMImproverOperator,
    LLMThoughtNormalizerOperator,
    LLMVerifierScorerOperator,
)
from ..model_client import ModelClient
from ..operators import Operator
from ..prompter import DefaultPipelinePrompter, Prompter
from .secondary_market import (
    SecondaryMarketContextBuilderOperator,
    SecondaryMarketProblemDecomposerOperator,
    SecondaryMarketRubricBuilderOperator,
    SecondaryMarketTaskIntakeOperator,
)


def build_secondary_market_llm_operators(
    model_client: ModelClient,
    prompter: Prompter | None = None,
) -> dict[str, Operator]:
    """Return SecondaryMarketAnalyst Operators with real LLM implementations.

    The first four Operators are deterministic so the UI gets immediate expert
    handoff and subtask graph updates. LLM calls begin at Candidate Generator.
    """

    active_prompter = prompter or DefaultPipelinePrompter()
    return {
        "task_intake": SecondaryMarketTaskIntakeOperator(),
        "context_builder": SecondaryMarketContextBuilderOperator(),
        "rubric_builder": SecondaryMarketRubricBuilderOperator(),
        "problem_decomposer": SecondaryMarketProblemDecomposerOperator(),
        "candidate_generator": LLMCandidateGeneratorOperator(model_client, active_prompter),
        "thought_normalizer": LLMThoughtNormalizerOperator(model_client),
        "verifier_scorer": LLMVerifierScorerOperator(model_client, active_prompter),
        "improver": LLMImproverOperator(model_client, active_prompter),
        "aggregator": LLMAggregatorOperator(model_client, active_prompter),
        "final_validator": LLMFinalValidatorOperator(model_client, active_prompter),
    }
