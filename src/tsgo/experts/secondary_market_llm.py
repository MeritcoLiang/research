"""SecondaryMarketAnalyst Stage flow with LLM-implemented Operators.

The LLM path starts with an instruction-driven ExpertRouter handoff. The router
invokes a target-specific handoff tool that transfers control to
SecondaryMarketAnalyst; the specialist then runs the documented context, rubric,
problem decomposition, and downstream LLM Operators.
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
from .handoff_router import SecondaryMarketLLMExpertRouterOperator
from .secondary_market import (
    SecondaryMarketContextBuilderOperator,
    SecondaryMarketProblemDecomposerOperator,
    SecondaryMarketRubricBuilderOperator,
)


def build_secondary_market_llm_operators(
    model_client: ModelClient,
    prompter: Prompter | None = None,
) -> dict[str, Operator]:
    """Return SecondaryMarketAnalyst Operators with real LLM implementations.

    The first Operator is an LLM-backed ExpertRouter. It is intentionally not a
    direct hard-coded assignment: it receives routing instructions and emits a
    durable handoff tool invocation before SecondaryMarketAnalyst takes over.
    """

    active_prompter = prompter or DefaultPipelinePrompter()
    return {
        "task_intake": SecondaryMarketLLMExpertRouterOperator(model_client),
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
