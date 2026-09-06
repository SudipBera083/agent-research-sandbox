from events.models import Event
from .actions import Action, ActionTypes


class SimulationEngine:

    def __init__(self, world):
        self.world = world

    def log_event(
        self,
        agent,
        event_type,
        action="",
        data=None,
    ):
        return Event.objects.create(
            world=self.world,
            agent=agent,
            tick=self.world.current_tick,
            event_type=event_type,
            action=action,
            data=data or {},
        )

    def execute(self, action: Action):

        agent = self.world.agents.get(
            id=action.agent_id
        )

        if action.action_type == ActionTypes.OBSERVE:
            return self.observe(agent)

        if action.action_type == ActionTypes.BUY:
            return self.buy(
                agent,
                action.parameters
            )

        if action.action_type == ActionTypes.SELL:
            return self.sell(
                agent,
                action.parameters
            )

        if action.action_type == ActionTypes.WAIT:
            return self.wait(agent)

        raise ValueError(
            f"Unknown action: {action.action_type}"
        )

    def observe(self, agent):

        resources = list(
            self.world.resources.values(
                "name",
                "price",
                "quantity",
            )
        )

        data = {
            "resources": resources,
            "wallet": agent.wallet,
            "inventory": agent.inventory,
        }

        self.log_event(
            agent,
            "observation",
            "observe",
            data,
        )

        return data

    def buy(self, agent, parameters):

        resource_name = parameters["resource"]
        quantity = parameters["quantity"]

        resource = self.world.resources.get(
        name=resource_name
        )

        total_cost = resource.price * quantity

        if resource.quantity < quantity:
            return {
            "success": False,
            "reason": "insufficient_market_supply",
        }

        if agent.wallet < total_cost:
            return {
            "success": False,
            "reason": "insufficient_funds",
        }

        resource.quantity -= quantity
        resource.save()

        agent.wallet -= total_cost

        inventory = agent.inventory.copy()

        inventory[resource_name] = (
        inventory.get(resource_name, 0)
        + quantity
    )

        agent.inventory = inventory
        agent.save()

        self.log_event(
        agent,
        "transaction",
        "buy",
        {
            "resource": resource_name,
            "quantity": quantity,
            "price": total_cost,
        },
    )

        return {
        "success": True,
        "resource": resource_name,
        "quantity": quantity,
        "cost": total_cost,
    }
    def sell(self, agent, parameters):

        resource_name = parameters["resource"]
        quantity = parameters["quantity"]

        inventory = agent.inventory.copy()

        current_quantity = inventory.get(
            resource_name,
            0,
        )

        if current_quantity < quantity:
            return {
                "success": False,
                "reason": "insufficient_inventory",
            }

        resource = self.world.resources.get(
            name=resource_name
        )

        revenue = resource.price * quantity

        inventory[resource_name] -= quantity

        agent.inventory = inventory
        agent.wallet += revenue

        resource.quantity += quantity

        agent.save()

        self.log_event(
            agent,
            "transaction",
            "sell",
            {
                "resource": resource_name,
                "quantity": quantity,
                "revenue": revenue,
            },
        )

        return {
            "success": True,
            "resource": resource_name,
            "quantity": quantity,
            "revenue": revenue,
        }

    def wait(self, agent):

        self.log_event(
            agent,
            "action",
            "wait",
        )

        return {
            "success": True,
            "action": "wait",
        }

    def tick(self):

        self.world.current_tick += 1
        self.world.save()

    def run(self, actions):

        results = []

        for action in actions:
            result = self.execute(action)
            results.append(result)

        self.tick()

        return results