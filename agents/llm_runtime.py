import hashlib
import json
import time

from simulation.actions import Action

from .providers.base import LLMResponse
from .runtime import AgentRuntime


class LLMAgentRuntime(AgentRuntime):

    runtime_type = "llm"

    def __init__(self, provider):
        self.provider = provider
        self._metadata = {}

    def decide(self, agent, observation):
        observation_data = observation.to_llm_dict()
        observation_json = json.dumps(
            observation_data,
            sort_keys=True,
            separators=(",", ":"),
        )
        messages = [
            {
                "role": "user",
                "content": observation_json,
            }
        ]
        started_at = time.perf_counter()

        try:
            response = self.provider.generate(messages)
            response = self._normalize_response(response)
            parsed_action = self._parse_output(response.content)
            action = self._validate_action(
                parsed_action,
                observation_data,
            )
            self._metadata = self._metadata_for(
                observation_json=observation_json,
                response=response,
                parsed_action=parsed_action,
                started_at=started_at,
                validation_result="accepted",
            )
            return action
        except Exception as error:
            self._metadata = self._metadata_for(
                observation_json=observation_json,
                response=(
                    response
                    if "response" in locals()
                    else LLMResponse(content="")
                ),
                parsed_action=None,
                started_at=started_at,
                validation_result="rejected",
                error=str(error),
            )
            return Action(
                agent_id=observation_data["self"]["id"],
                action_type="wait",
                parameters={},
            )

    def trace_metadata(self):
        return self._metadata

    def _normalize_response(self, response):
        if isinstance(response, LLMResponse):
            return response

        if isinstance(response, str):
            return LLMResponse(content=response)

        raise TypeError("Provider response must contain structured content.")

    def _metadata_for(
        self,
        observation_json,
        response,
        parsed_action,
        started_at,
        validation_result,
        error=None,
    ):
        bounded_observation = json.loads(observation_json)
        metadata = {
            "provider": self.provider.provider_name,
            "model": self.provider.model_name,
            "prompt_version": self.provider.prompt_version,
            "observation_hash": hashlib.sha256(
                observation_json.encode("utf-8")
            ).hexdigest(),
            "raw_response": response.raw_response or response.content,
            "parsed_action": parsed_action,
            "validation_result": validation_result,
            "latency_ms": round(
                (time.perf_counter() - started_at) * 1000,
                3,
            ),
            "token_usage": response.usage,
            "context_stats": {
                "messages": len(bounded_observation["messages"]),
                "memories": len(bounded_observation["memories"]),
                "trade_history": len(
                    bounded_observation["trade_history"]
                ),
                "pending_trades": len(
                    bounded_observation["pending_trades"]
                ),
                "other_agents": len(bounded_observation["other_agents"]),
                "estimated_chars": len(observation_json),
            },
        }

        if error is not None:
            metadata["error"] = error

        prompt_tokens = metadata["token_usage"].get(
            "prompt_tokens",
            0,
        )
        completion_tokens = metadata["token_usage"].get(
            "completion_tokens",
            0,
        )
        metadata["estimated_cost_usd"] = (
            prompt_tokens * self.provider.input_cost_per_million
            + completion_tokens * self.provider.output_cost_per_million
        ) / 1_000_000

        return metadata

    def _parse_output(self, raw_output):
        if isinstance(raw_output, str):
            raw_output = json.loads(raw_output)

        if not isinstance(raw_output, dict):
            raise TypeError("LLM output must be a JSON object.")

        action_type = raw_output.get("action")
        parameters = raw_output.get("parameters", {})

        if not isinstance(action_type, str):
            raise TypeError("LLM output must include an action.")

        if not isinstance(parameters, dict):
            raise TypeError("Action parameters must be an object.")

        return {
            "action": action_type,
            "parameters": parameters,
        }

    def _validate_action(self, parsed_action, observation):
        action_type = parsed_action["action"]
        parameters = parsed_action["parameters"]
        available_actions = observation["available_actions"]

        if action_type not in available_actions:
            raise ValueError("Action is not available in this observation.")

        if action_type == "wait":
            return Action(
                agent_id=observation["self"]["id"],
                action_type=action_type,
                parameters={},
            )

        if action_type == "buy":
            resource = parameters.get("resource")
            quantity = parameters.get("quantity")
            resources = observation["world"]["resources"]
            resource_state = next(
                (
                    item
                    for item in resources
                    if item["name"] == resource
                ),
                None,
            )

            if (
                not isinstance(resource, str)
                or not isinstance(quantity, int)
                or quantity <= 0
                or resource_state is None
                or quantity > resource_state["quantity"]
                or quantity * resource_state["price"]
                > observation["self"]["wallet"]
            ):
                raise ValueError("Invalid buy parameters.")

        if action_type == "sell":
            resource = parameters.get("resource")
            quantity = parameters.get("quantity")
            inventory = observation["self"].get("inventory", {})

            if (
                not isinstance(resource, str)
                or not isinstance(quantity, int)
                or quantity <= 0
                or inventory.get(resource, 0) < quantity
            ):
                raise ValueError("Invalid sell parameters.")

        if action_type == "communicate":
            if not self._has_recipient(parameters, observation):
                raise ValueError("Invalid communication recipient.")
            if not isinstance(parameters.get("content"), str):
                raise ValueError("Communication content is required.")

        if action_type == "propose_trade":
            if not self._has_recipient(parameters, observation):
                raise ValueError("Invalid trade recipient.")
            if not isinstance(parameters.get("conversation_id"), str):
                raise ValueError("Trade conversation is required.")
            self._validate_offer(parameters.get("offer"))

        if action_type in ("accept_trade", "reject_trade"):
            trade_ids = {
                trade["trade_id"]
                for trade in observation["pending_trades"]
            }
            if parameters.get("trade_id") not in trade_ids:
                raise ValueError("Trade is not pending for this agent.")

        return Action(
            agent_id=observation["self"]["id"],
            action_type=action_type,
            parameters=parameters,
        )

    def _has_recipient(self, parameters, observation):
        recipient_id = parameters.get("recipient_id")
        return any(
            other["id"] == recipient_id
            for other in observation["other_agents"]
        )

    def _validate_offer(self, offer):
        if not isinstance(offer, dict):
            raise TypeError("Trade offer must be an object.")

        for side in ("give", "receive"):
            details = offer.get(side, {})
            if (
                not isinstance(details.get("resource"), str)
                or not isinstance(details.get("quantity"), int)
                or details["quantity"] <= 0
            ):
                raise ValueError("Trade offer is invalid.")
