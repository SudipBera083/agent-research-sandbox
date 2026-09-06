from abc import ABC, abstractmethod

from .actions import Action, ActionTypes
from agents.memory import MemoryManager

class DecisionEngine(ABC):

    @abstractmethod
    def decide(self, agent, observation) -> Action:
        pass

class RuleBasedDecisionEngine(DecisionEngine):

    def decide(self, agent, observation) -> Action:

        memory = MemoryManager(agent)

        memory.remember(
            "observation",
            {
                "resources": observation["resources"],
                "wallet": agent.wallet,
                "inventory": agent.inventory,
            },
            tick=agent.world.current_tick,
        )

        resources = observation["resources"]

        food = next(
            (
                resource
                for resource in resources
                if resource["name"] == "food"
            ),
            None,
        )

        current_food = agent.inventory.get(
            "food",
            0,
        )

        if food and current_food < 5:

            affordable_quantity = int(
                agent.wallet // food["price"]
            )

            quantity = min(
                2,
                affordable_quantity,
                food["quantity"],
            )

            if quantity > 0:

                return Action(
                    agent_id=agent.id,
                    action_type=ActionTypes.BUY,
                    parameters={
                        "resource": "food",
                        "quantity": quantity,
                    },
                )

        return Action(
            agent_id=agent.id,
            action_type=ActionTypes.WAIT,
            parameters={},
        )