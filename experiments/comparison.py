from copy import deepcopy

from .models import Experiment, ExperimentComparison
from .analysis import ExperimentComparisonAnalyzer
from .runner import ExperimentRunner


class ExperimentComparisonRunner:

    RUNTIMES = (
        ("rule", "rule"),
        ("random", "random"),
        ("groq", "llm"),
    )

    def __init__(self, comparison):
        self.comparison = comparison

    def run(self):
        metric_results = {}

        for label, runtime_type in self.RUNTIMES:
            configuration = deepcopy(self.comparison.configuration)
            agents = configuration.get("agents", [])

            if agents:
                agents[0]["runtime_type"] = runtime_type
                agents[0]["provider"] = (
                    "groq" if label == "groq" else ""
                )
                agents[0]["model"] = (
                    configuration.get("model", "")
                    if label == "groq"
                    else ""
                )

            experiment = Experiment.objects.create(
                name=f"{self.comparison.name} - {label}",
                description=f"Controlled {label} runtime comparison.",
                seed=self.comparison.seed,
                total_ticks=configuration.get(
                    "simulation",
                    {},
                ).get("ticks", 10),
                configuration=configuration,
            )

            result = ExperimentRunner(experiment).run()
            self.comparison.experiments.add(experiment)
            metric_results[label] = result.metrics

        self.comparison.metrics = metric_results
        self.comparison.analysis = ExperimentComparisonAnalyzer(
            self.comparison
        ).analyze()
        self.comparison.save(update_fields=["metrics", "analysis"])
        return metric_results