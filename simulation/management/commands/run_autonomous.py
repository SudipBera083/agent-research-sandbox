from django.core.management.base import BaseCommand

from simulation.models import World, Resource
from simulation.engine import SimulationEngine
from simulation.decision import RuleBasedDecisionEngine
from agents.models import Agent


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

        agents = []

        for i in range(3):

            agent = Agent.objects.create(
                name=f"Agent {i + 1}",
                world=world,
                system_prompt=(
                    "Maintain sufficient food "
                    "while preserving money."
                ),
                goals=[
                    "Maintain at least 5 food"
                ],
            )

            agents.append(agent)

        decision_engine = RuleBasedDecisionEngine()

        engine = SimulationEngine(
            world,
            decision_engine,
        )

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