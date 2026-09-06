import json

from .base import LLMProvider, LLMResponse


class DeterministicLLMProvider(LLMProvider):

    provider_name = "deterministic"
    model_name = "deterministic-v1"

    def generate(self, messages):
        observation = json.loads(messages[-1]["content"])
        self_state = observation["self"]

        if observation["pending_trades"]:
            action = {
                "action": "accept_trade",
                "parameters": {
                    "trade_id": observation["pending_trades"][0]["trade_id"],
                },
            }
            return LLMResponse(content=json.dumps(action))

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
                    action = {
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
                    }
                    return LLMResponse(content=json.dumps(action))

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
            action = {
                "action": "buy",
                "parameters": {
                    "resource": "food",
                    "quantity": 1,
                },
            }
            return LLMResponse(content=json.dumps(action))

        return LLMResponse(
            content=json.dumps({
                "action": "wait",
                "parameters": {},
            })
        )
