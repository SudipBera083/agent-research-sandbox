import random

from django.conf import settings
from simulation.actions import Action

from simulation.decision import get_decision_engine


class AgentRuntime:

    runtime_type = "base"

    def decide(self, agent, observation):
        raise NotImplementedError

    def trace_metadata(self):
        return {}


class RuleAgentRuntime(AgentRuntime):

    runtime_type = "rule"

    def __init__(self, decision_engine):
        self.decision_engine = decision_engine

    def decide(self, agent, observation):
        return self.decision_engine.decide(
            agent,
            observation,
        )


class RandomAgentRuntime(AgentRuntime):

    runtime_type = "random"

    def decide(self, agent, observation):

        actions = observation.available_actions

        if not actions:
            return Action(
                agent_id=agent.id,
                action_type="wait",
                parameters={},
            )

        action_type = random.choice(actions)

        return Action(
            agent_id=agent.id,
            action_type=action_type,
            parameters={},
        )


def get_agent_runtime(agent):

    if agent.runtime_type == "llm":
        from .llm_runtime import LLMAgentRuntime
        from .providers.deterministic import DeterministicLLMProvider

        provider_name = (
            agent.provider or settings.LLM_PROVIDER
        ).lower()

        if provider_name == "groq":
            from .providers.groq_provider import GroqProvider

            provider = GroqProvider(model=agent.model or None)
        elif provider_name == "xai":
            from .providers.openai_provider import XAIProvider

            provider = XAIProvider(model=agent.model or None)
        elif provider_name == "deterministic":
            provider = DeterministicLLMProvider()
        else:
            raise ValueError(
                f"Unknown LLM provider: {settings.LLM_PROVIDER}"
            )

        return LLMAgentRuntime(
            provider
        )

    if agent.runtime_type == "random":
        return RandomAgentRuntime()

    return RuleAgentRuntime(
        get_decision_engine(agent)
    )