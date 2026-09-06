from abc import ABC, abstractmethod

from .actions import Action, ActionTypes

class DecisionEngine(ABC):

    @abstractmethod
    def decide(self, agent, observation) -> Action:
        pass

class RuleBasedDecisionEngine(DecisionEngine):

    def decide(self, agent, observation) -> Action:

        resources = observation.world_state["resources"]

        food = next(
            (
                resource
                for resource in resources
                if resource["name"] == "food"
            ),
            None,
        )

        current_food = observation.self_state["inventory"].get(
            "food",
            0,
        )

        if food and current_food < 5:

            affordable_quantity = int(
                observation.self_state["wallet"] // food["price"]
            )

            quantity = min(
                2,
                affordable_quantity,
                food["quantity"],
            )

            if quantity > 0:

                return Action(
                    agent_id=observation.self_state["id"],
                    action_type=ActionTypes.BUY,
                    parameters={
                        "resource": "food",
                        "quantity": quantity,
                    },
                )

        return Action(
            agent_id=observation.self_state["id"],
            action_type=ActionTypes.WAIT,
            parameters={},
        )

class WealthDecisionEngine(DecisionEngine):

    def decide(self, agent, observation) -> Action:

        resources = observation.world_state["resources"]

        food = next(
            (
                resource
                for resource in resources
                if resource["name"] == "food"
            ),
            None,
        )

        if food is None:
            return Action(
                agent_id=observation.self_state["id"],
                action_type=ActionTypes.WAIT,
                parameters={},
            )

        # Wealth agent only buys if price is attractive.
        if (
            food["price"] <= 10
            and observation.self_state["wallet"] >= food["price"]
        ):

            return Action(
                agent_id=observation.self_state["id"],
                action_type=ActionTypes.BUY,
                parameters={
                    "resource": "food",
                    "quantity": 1,
                },
            )

        return Action(
            agent_id=observation.self_state["id"],
            action_type=ActionTypes.WAIT,
            parameters={},
        )

class SurvivalDecisionEngine(DecisionEngine):

    def decide(self, agent, observation) -> Action:

        food = observation.self_state["inventory"].get(
            "food",
            0,
        )

        if food < 8:

            resources = observation.world_state["resources"]

            food_resource = next(
                (
                    resource
                    for resource in resources
                    if resource["name"] == "food"
                ),
                None,
            )

            if food_resource:

                affordable = int(
                    observation.self_state["wallet"]
                    // food_resource["price"]
                )

                quantity = min(
                    3,
                    affordable,
                    food_resource["quantity"],
                )

                if quantity > 0:

                    return Action(
                        agent_id=observation.self_state["id"],
                        action_type=ActionTypes.BUY,
                        parameters={
                            "resource": "food",
                            "quantity": quantity,
                        },
                    )

        return Action(
            agent_id=observation.self_state["id"],
            action_type=ActionTypes.WAIT,
            parameters={},
        )

class CooperativeDecisionEngine(DecisionEngine):

    def decide(self, agent, observation) -> Action:

        other_agents = observation.other_agents

        if other_agents:

            target = other_agents[0]

            return Action(
                agent_id=observation.self_state["id"],
                action_type=ActionTypes.COMMUNICATE,
                parameters={
                    "recipient_id": target["id"],
                    "content": (
                        "Hello. I am willing to cooperate "
                        "if we can help each other."
                    ),
                },
            )

        return Action(
            agent_id=observation.self_state["id"],
            action_type=ActionTypes.WAIT,
            parameters={},
        )


def get_decision_engine(agent):

    if agent.role == "wealth":
        return WealthDecisionEngine()

    if agent.role == "survival":
        return SurvivalDecisionEngine()

    if agent.role == "cooperative":
        return CooperativeDecisionEngine()

    return RuleBasedDecisionEngine()


