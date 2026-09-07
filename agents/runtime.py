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

        agent_id = observation.self_state["id"]
        actions = [
            Action(
                agent_id=agent_id,
                action_type="wait",
                parameters={},
            )
        ]

        food = next(
            (
                resource
                for resource in observation.world_state["resources"]
                if resource["name"] == "food"
            ),
            None,
        )

        if (
            food
            and food["quantity"] > 0
            and observation.self_state["wallet"] >= food["price"]
        ):
            actions.append(
                Action(
                    agent_id=agent_id,
                    action_type="buy",
                    parameters={
                        "resource": "food",
                        "quantity": 1,
                    },
                )
            )

        for trade in observation.pending_trades:
            actions.append(
                Action(
                    agent_id=agent_id,
                    action_type="accept_trade",
                    parameters={
                        "trade_id": trade["trade_id"],
                    },
                )
            )

        return random.choice(actions)


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