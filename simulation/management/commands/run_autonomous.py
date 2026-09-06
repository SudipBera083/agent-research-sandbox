from django.core.management.base import BaseCommand

from agents.models import Agent
from simulation.engine import SimulationEngine
from simulation.models import Resource, World


class Command(BaseCommand):

    help = "Run autonomous agents"

    def handle(self, *args, **kwargs):

        world = World.objects.create(
            name="Autonomous Marketplace",
            description="First autonomous agent experiment",
        )

        Resource.objects.create(
            world=world,
            name="food",
            price=10,
            quantity=100,
        )

        agent_1 = Agent.objects.create(
            name="Agent 1",
            role="wealth",
            world=world,
            system_prompt="Maximize wealth.",
            goals=[
                "Maximize wealth",
            ],
        )

        agent_2 = Agent.objects.create(
            name="Agent 2",
            role="survival",
            world=world,
            system_prompt="Prioritize survival.",
            goals=[
                "Maintain food reserves",
            ],
        )

        agent_3 = Agent.objects.create(
            name="Agent 3",
            role="cooperative",
            world=world,
            system_prompt="Prefer cooperation.",
            goals=[
                "Maintain resources",
                "Cooperate with others",
            ],
        )

        agents = [agent_1, agent_2, agent_3]

        engine = SimulationEngine(world)

        for tick in range(10):

            self.stdout.write(
                f"\n--- TICK {tick + 1} ---"
            )

            for agent in agents:

                agent.refresh_from_db()

                result = engine.run_agent(agent)

                self.stdout.write(
                    str(result)
                )

            engine.tick()

        self.stdout.write(
            self.style.SUCCESS(
                "\nAutonomous simulation completed."
            )
        )