from django.core.management.base import BaseCommand

from experiments.comparison import ExperimentComparisonRunner
from experiments.models import ExperimentComparison


class Command(BaseCommand):

    help = "Run a controlled rule, random, and Groq comparison"

    def handle(self, *args, **options):
        comparison = ExperimentComparison.objects.create(
            name="Runtime Comparison 001",
            seed=42,
            configuration={
                "world": {
                    "name": "Controlled Research World",
                    "resources": [
                        {
                            "name": "food",
                            "price": 10,
                            "quantity": 100,
                        }
                    ],
                },
                "memory": {
                    "enabled": True,
                    "top_k": 10,
                    "decay": 0.95,
                },
                "simulation": {
                    "ticks": 10,
                },
                "agents": [
                    {
                        "name": "Agent 1",
                        "role": "wealth",
                        "wallet": 100,
                        "goals": ["Maximize wealth"],
                    },
                    {
                        "name": "Agent 2",
                        "role": "survival",
                        "wallet": 100,
                        "goals": ["Maintain food reserves"],
                    },
                    {
                        "name": "Agent 3",
                        "role": "cooperative",
                        "wallet": 100,
                        "inventory": {"food": 2},
                        "goals": ["Cooperate with other agents"],
                    },
                ],
            },
        )

        metrics = ExperimentComparisonRunner(comparison).run()

        self.stdout.write(
            self.style.SUCCESS(
                f"Comparison completed: {comparison.name}"
            )
        )
        self.stdout.write(f"Comparison ID: {comparison.id}")
        self.stdout.write(f"Metrics: {metrics}")