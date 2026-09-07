from copy import deepcopy

from .analysis import ExperimentComparisonAnalyzer
from .comparison import ExperimentComparisonRunner
from .models import BenchmarkSuite, ExperimentComparison


class BenchmarkRunner:

    def __init__(self, suite, runtimes=None):
        self.suite = suite
        self.runtimes = runtimes

    def run(self):
        results = {}

        for scenario_name, scenario in self.suite.scenarios.items():
            comparison = ExperimentComparison.objects.create(
                name=f"{self.suite.name} - {scenario_name}",
                seed=scenario["seed"],
                configuration=deepcopy(scenario["configuration"]),
            )
            runner = ExperimentComparisonRunner(comparison)
            if self.runtimes is not None:
                original = runner.RUNTIMES
                runner.RUNTIMES = tuple(
                    item for item in original
                    if item[0] in self.runtimes
                )

            metrics = runner.run()
            self.suite.comparisons.add(comparison)
            results[scenario_name] = {
                "metrics": metrics,
                "analysis": comparison.analysis,
            }

        self.suite.analysis = results
        self.suite.save(update_fields=["analysis"])
        return results
