from django.core.management.base import BaseCommand

from experiments.benchmarks import BenchmarkRunner
from experiments.models import BenchmarkSuite
from experiments.scenarios import scenario_definitions


class Command(BaseCommand):

    help = "Run the reproducible scenario benchmark matrix"

    def add_arguments(self, parser):
        parser.add_argument(
            "--runtimes",
            default="rule,random,groq",
            help="Comma-separated runtimes to run",
        )

    def handle(self, *args, **options):
        runtime_names = {
            name.strip()
            for name in options["runtimes"].split(",")
            if name.strip()
        }
        scenarios = scenario_definitions()
        suite = BenchmarkSuite.objects.create(
            name="Runtime Benchmark Suite 001",
            seed=0,
            scenarios=scenarios,
        )
        results = BenchmarkRunner(
            suite,
            runtimes=runtime_names,
        ).run()

        self.stdout.write(
            self.style.SUCCESS(
                f"Benchmark suite completed: {suite.name}"
            )
        )
        self.stdout.write(f"Suite ID: {suite.id}")
        self.stdout.write(
            f"Scenarios: {list(results.keys())}"
        )
        self.stdout.write(
            f"Comparisons: {suite.comparisons.count()}"
        )
