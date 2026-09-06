import json

from simulation.actions import Action

from .runtime import AgentRuntime


class LLMProvider:

    provider_name = "base"
    model_name = "base"

    def generate(self, messages):
        raise NotImplementedError


class DeterministicLLMProvider(LLMProvider):

    provider_name = "deterministic"
    model_name = "deterministic-v1"

    def generate(self, messages):
        observation = json.loads(messages[-1]["content"])
        self_state = observation["self"]

        if observation["pending_trades"]:
            return json.dumps({
                "action": "accept_trade",
                "parameters": {
                    "trade_id": observation["pending_trades"][0]["trade_id"],
                },
            })

        if observation["messages"]:
            message = observation["messages"][0]

            if message["sender"] != self_state["name"]:
                sender = next(
                    (
                        other
                        for other in observation["other_agents"]
                        if other["name"] == message["sender"]
                    ),
                    None,
                )

                if sender:
                    return json.dumps({
                        "action": "communicate",
                        "parameters": {
                            "recipient_id": sender["id"],
                            "content": (
                                "I received your message. "
                                "What do you propose?"
                            ),
                            "conversation_id": message["conversation_id"],
                            "intent": "question",
                        },
                    })

        food = next(
            (
                resource
                for resource in observation["world"]["resources"]
                if resource["name"] == "food"
            ),
            None,
        )

        if (
            food
            and food["price"] <= 10
            and self_state["wallet"] >= food["price"]
        ):
            return json.dumps({
                "action": "buy",
                "parameters": {
                    "resource": "food",
                    "quantity": 1,
                },
            })

        return json.dumps({
            "action": "wait",
            "parameters": {},
        })


class LLMAgentRuntime(AgentRuntime):

    runtime_type = "llm"

    def __init__(self, provider):
        self.provider = provider
        self._metadata = {}

    def decide(self, agent, observation):
        observation_data = observation.to_dict()
        messages = [
            {
                "role": "user",
                "content": json.dumps(observation_data),
            }
        ]

        try:
            raw_output = self.provider.generate(messages)
            parsed_action = self._parse_output(raw_output)
            action = self._validate_action(
                parsed_action,
                observation_data,
            )
            self._metadata = {
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
                "parsed_action": parsed_action,
            }
            return action
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            self._metadata = {
                "provider": self.provider.provider_name,
                "model": self.provider.model_name,
                "parsed_action": None,
                "validation_error": str(error),
            }
            return Action(
                agent_id=observation_data["self"]["id"],
                action_type="wait",
                parameters={},
            )

    def trace_metadata(self):
        return self._metadata

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