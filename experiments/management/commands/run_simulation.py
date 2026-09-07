import logging

from django.core.management.base import BaseCommand, CommandError

from experiments.activity import SimulationController
from experiments.models import Simulation, SimulationAgent

logger = logging.getLogger(__name__)


DEFAULT_AGENTS = [
    {
        "name": "Agent 1",
        "role": "wealth",
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
    },
    {
        "name": "Agent 2",
        "role": "survival",
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
    },
    {
        "name": "Agent 3",
        "role": "cooperative",
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
    },
]


class Command(BaseCommand):
    help = "Run a real-time simulation to completion via a continuous tick loop"

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            type=str,
            default="simulation-run",
            help="Name of the simulation",
        )
        parser.add_argument(
            "--ticks",
            type=int,
            default=100,
            help="Total ticks to run",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed",
        )
        parser.add_argument(
            "--agent-runtimes",
            type=str,
            default="rule",
            help="Comma-separated runtime types (rule, random, llm)",
        )
        parser.add_argument(
            "--provider",
            type=str,
            default="deterministic",
            help="LLM provider (deterministic, groq, xai)",
        )

    def handle(self, *args, **kwargs):
        name = kwargs["name"]
        total_ticks = kwargs["ticks"]
        seed = kwargs["seed"]
        agent_runtimes = kwargs["agent_runtimes"].split(",")
        provider = kwargs["provider"]

        sim = Simulation.objects.create(
            name=name,
            status="created",
            current_tick=0,
            total_ticks=total_ticks,
            seed=seed,
            configuration={
                "agent_runtimes": agent_runtimes,
                "provider": provider,
            },
        )

        for i, runtime in enumerate(agent_runtimes):
            SimulationAgent.objects.create(
                simulation=sim,
                name=f"Agent-{i + 1}",
                role="general",
                runtime=runtime,
                provider=provider,
                model="deterministic" if provider == "deterministic" else "",
            )

        logger.info(
            "simulation_start sim_id=%s operation_id=%s total_ticks=%s",
            sim.id,
            sim.operation_id,
            total_ticks,
        )

        controller = SimulationController(sim)
        result = controller.run_to_completion()

        logger.info(
            "simulation_complete sim_id=%s operation_id=%s status=%s ticks=%s",
            sim.id,
            sim.operation_id,
            result["status"],
            result["tick"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Simulation '{name}' completed: status={result['status']}, "
                f"ticks={result['tick']}"
            )
        )
