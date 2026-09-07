import logging
from django.core.management.base import BaseCommand
from experiments.activity import SimulationController
from experiments.models import Simulation, SimulationAgent

logger = logging.getLogger(__name__)

DEFAULT_AGENTS = [
    {
        "name": "Alpha-Trader",
        "role": "wealth",
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
    },
    {
        "name": "Beta-Survivor",
        "role": "survival",
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
    },
    {
        "name": "Gamma-Cooperator",
        "role": "cooperative",
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
    },
]


class Command(BaseCommand):
    help = "Seed initial demo simulation with agents and baseline event history (idempotent)"

    def handle(self, *args, **options):
        if Simulation.objects.filter(id=1).exists():
            self.stdout.write(
                self.style.NOTICE("Simulation with id=1 already exists. Skipping seed.")
            )
            return

        self.stdout.write("Seeding demo simulation...")

        sim = Simulation.objects.create(
            name="Demo Research Simulation",
            status="created",
            current_tick=0,
            total_ticks=100,
            seed=42,
            configuration={
                "agent_runtimes": ["rule", "rule", "rule"],
                "provider": "deterministic",
            },
        )

        for spec in DEFAULT_AGENTS:
            SimulationAgent.objects.create(
                simulation=sim,
                name=spec["name"],
                role=spec["role"],
                runtime=spec["runtime"],
                provider=spec["provider"],
                model=spec["model"],
            )

        controller = SimulationController(sim)
        controller.start()
        for _ in range(3):
            controller.step()
        controller.pause(reason="demo_initialized")

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded demo Simulation id={sim.id} (status={sim.status}, tick={sim.current_tick})"
            )
        )
