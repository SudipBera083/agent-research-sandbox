from agents.memory import MemoryManager
from events.models import Event
from experiments.models import DecisionTrace
from .actions import Action, ActionTypes
from .communication import CommunicationManager
from .models import Conversation, Trade
from .observation import ObservationBuilder
from .trading import TradeEngine
from agents.runtime import get_agent_runtime

class SimulationEngine:

    def __init__(self, world, experiment=None):
        self.world = world
        self.experiment = experiment

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

        if action.action_type == ActionTypes.COMMUNICATE:
            recipient = self.world.agents.get(
                id=action.parameters["recipient_id"]
            )

            message = CommunicationManager(
                self.world
            ).send(
                sender=agent,
                recipient=recipient,
                content=action.parameters["content"],
                tick=self.world.current_tick,
                conversation_id=action.parameters.get(
                    "conversation_id",
                    "",
                ),
                intent=action.parameters.get(
                    "intent",
                    "information",
                ),
            )

            return {
                "success": True,
                "action": "communicate",
                "message_id": message.id,
                "recipient": recipient.name,
            }

        if action.action_type == ActionTypes.PROPOSE_TRADE:
            recipient = self.world.agents.get(
                id=action.parameters["recipient_id"]
            )
            conversation = Conversation.objects.get(
                conversation_id=action.parameters["conversation_id"]
            )

            trade = TradeEngine.propose(
                conversation=conversation,
                proposer=agent,
                recipient=recipient,
                offer=action.parameters["offer"],
            )

            return {
                "success": True,
                "action": "propose_trade",
                "trade_id": trade.id,
                "status": trade.status,
                "recipient": recipient.name,
            }

        if action.action_type == ActionTypes.ACCEPT_TRADE:
            trade = Trade.objects.get(
                id=action.parameters["trade_id"]
            )

            return TradeEngine.accept(
                trade=trade,
                agent=agent,
            )

        if action.action_type == ActionTypes.REJECT_TRADE:
            trade = Trade.objects.get(
                id=action.parameters["trade_id"]
            )

            if trade.recipient_id != agent.id:
                return {
                    "success": False,
                    "error": "Only the recipient can reject this trade.",
                }

            if trade.status != "proposed":
                return {
                    "success": False,
                    "error": "Trade is no longer available.",
                }

            trade.status = "rejected"
            trade.save(update_fields=["status", "updated_at"])

            return {
                "success": True,
                "action": "reject_trade",
                "trade_id": trade.id,
                "status": trade.status,
            }

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
    def run_agent(self, agent):

        observation = ObservationBuilder(
            self.world
        ).build(agent)

        memory = MemoryManager(agent)

        memory.remember(
            "observation",
            observation.to_dict(),
            tick=self.world.current_tick,
        )

        runtime = get_agent_runtime(agent)

        action = runtime.decide(
            agent,
            observation,
        )

        result = self.execute(action)

        memory.remember(
        "action_result",
        {
            "action": action.action_type,
            "parameters": action.parameters,
            "result": result,
        },
        tick=self.world.current_tick,
    )

        if self.experiment is not None:
            decision_data = {
                "runtime": runtime.runtime_type,
                "backend": runtime.__class__.__name__,
                "action_type": action.action_type,
            }
            decision_data.update(runtime.trace_metadata())

            DecisionTrace.objects.create(
                experiment=self.experiment,
                tick=self.world.current_tick,
                agent=agent,
                observation=observation.to_dict(),
                decision=decision_data,
                action={
                    "type": action.action_type,
                    "parameters": action.parameters,
                },
                result=result,
            )

        return {
        "agent": agent.name,
        "action": action.action_type,
        "parameters": action.parameters,
        "result": result,
    }