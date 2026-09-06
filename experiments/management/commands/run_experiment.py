from django.core.management.base import BaseCommand

from experiments.models import Experiment
from experiments.runner import ExperimentRunner


class Command(BaseCommand):

    help = "Run a research experiment"

    def handle(self, *args, **kwargs):

        experiment = Experiment.objects.create(
            name="Heterogeneous Agents 001",
            description=(
                "Baseline experiment with "
                "three agents using different strategies."
            ),
            seed=42,
            total_ticks=10,
            configuration={
                "world_name": "Research World 001",
                "resources": [
                    {
                        "name": "food",
                        "price": 10,
                        "quantity": 100,
                    }
                ],
                "agents": [
                    {
                        "name": "Agent 1",
                        "role": "wealth",
                        "wallet": 100,
                        "goals": [
                            "Maximize wealth"
                        ],
                    },
                    {
                        "name": "Agent 2",
                        "role": "survival",
                        "wallet": 100,
                        "goals": [
                            "Maintain food reserves"
                        ],
                    },
                    {
                        "name": "Agent 3",
                        "role": "cooperative",
                        "wallet": 100,
                        "inventory": {
                            "food": 2,
                        },
                        "goals": [
                            "Cooperate with other agents"
                        ],
                    },
                ],
            },
        )

        runner = ExperimentRunner(experiment)
        result = runner.run()

        self.stdout.write(
            self.style.SUCCESS(
                "\nExperiment completed."
            )
        )
        self.stdout.write(
            f"Experiment: {experiment.name}"
        )
        self.stdout.write(
            f"Status: {experiment.status}"
        )
        self.stdout.write(
            f"Ticks: {experiment.current_tick}"
        )
        self.stdout.write(
            f"Metrics: {result.metrics}"
        )
