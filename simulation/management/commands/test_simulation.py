from django.core.management.base import BaseCommand

from simulation.models import World, Resource
from simulation.engine import SimulationEngine
from simulation.actions import Action, ActionTypes

from agents.models import Agent


class Command(BaseCommand):

    help = "Run a simple agent simulation"

    def handle(self, *args, **kwargs):

        world = World.objects.create(
            name="Test Marketplace",
            description="First agent experiment",
        )

        food = Resource.objects.create(
            world=world,
            name="food",
            price=10,
            quantity=100,
        )

        agent_a = Agent.objects.create(
            name="Agent A",
            world=world,
            system_prompt="You are a resource-seeking agent.",
            goals=[
                "Acquire food"
            ],
        )

        agent_b = Agent.objects.create(
            name="Agent B",
            world=world,
            system_prompt="You are a trading agent.",
            goals=[
                "Accumulate wealth"
            ],
        )

        agent_c = Agent.objects.create(
            name="Agent C",
            world=world,
            system_prompt="You are a conservative agent.",
            goals=[
                "Preserve resources"
            ],
        )

        engine = SimulationEngine(world)

        actions = [
            Action(
                agent_id=agent_a.id,
                action_type=ActionTypes.BUY,
                parameters={
                    "resource": "food",
                    "quantity": 3,
                },
            ),
            Action(
                agent_id=agent_b.id,
                action_type=ActionTypes.BUY,
                parameters={
                    "resource": "food",
                    "quantity": 5,
                },
            ),
            Action(
                agent_id=agent_c.id,
                action_type=ActionTypes.OBSERVE,
                parameters={},
            ),
        ]

        results = engine.run(actions)

        self.stdout.write(
            self.style.SUCCESS(
                f"Simulation completed: {results}"
            )
        )