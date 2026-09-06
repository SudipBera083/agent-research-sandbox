from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from experiments.models import BenchmarkSuite
from experiments.reporting import BenchmarkReporter


class Command(BaseCommand):

    help = (
        "Export a read-only report from a persisted benchmark suite.\n"
        "Generates report.json, report.csv, and five PNG chart files.\n"
        "Never re-runs experiments or calls any LLM provider."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--suite-id",
            type=int,
            help="ID of the BenchmarkSuite to report on (default: latest).",
        )
        parser.add_argument(
            "--output-dir",
            default="reports",
            help="Directory to write all report files (default: reports/).",
        )

    def handle(self, *args, **options):
        suite_id = options.get("suite_id")
        queryset = BenchmarkSuite.objects.order_by("-id")

        if suite_id is not None:
            queryset = queryset.filter(id=suite_id)

        suite = queryset.first()
        if suite is None:
            raise CommandError("No persisted benchmark suite was found.")

        reporter = BenchmarkReporter(suite)
        output_dir = Path(options["output_dir"])

        # --- exports ---
        json_path = reporter.export_json(output_dir / "report.json")
        csv_path = reporter.export_csv(output_dir / "report.csv")
        chart_paths = reporter.export_charts(output_dir)

        # --- build report for console summary ---
        report = reporter.build()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nBenchmark report for: {suite.name} (id={suite.id})"
            )
        )
        self.stdout.write(f"  JSON  : {json_path}")
        self.stdout.write(f"  CSV   : {csv_path}")

        if chart_paths:
            self.stdout.write("  Charts:")
            for name, path in chart_paths.items():
                self.stdout.write(f"    {name:<16} {path}")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  Charts: skipped (matplotlib not installed)"
                )
            )

        # --- runtime comparison table ---
        self.stdout.write("\nRuntime comparison (averages across scenarios):")
        header = (
            f"  {'Runtime':<10} {'Wealth':>10} {'Trades':>8} "
            f"{'Messages':>10} {'Tokens':>8} {'Latency(ms)':>12}"
        )
        self.stdout.write(header)
        self.stdout.write("  " + "-" * (len(header) - 2))
        for runtime, stats in sorted(report["runtime_comparison"].items()):
            self.stdout.write(
                f"  {runtime:<10} "
                f"{stats['average_total_wealth']:>10.1f} "
                f"{stats['average_trade_volume']:>8.1f} "
                f"{stats['average_messages']:>10.1f} "
                f"{stats['total_llm_tokens']:>8} "
                f"{stats['average_llm_latency']:>12.1f}"
            )

        # --- findings ---
        self.stdout.write("\nFindings:")
        for finding in report["findings"]:
            tag = "[measured]      " if finding["kind"] == "measured" \
                else "[interpretation]"
            self.stdout.write(f"  {tag} {finding['text']}")

        # --- insights ---
        insights = report.get("insights", {})
        if insights:
            self.stdout.write("\nInsights")
            self.stdout.write("--------")

            self.stdout.write("\nRuntime ranking:")
            for i, r in enumerate(insights.get("runtime_ranking", []), 1):
                self.stdout.write(f"  {i}. {r['runtime']}")

            self.stdout.write("\nScenario leaders:")
            for s in insights.get("scenario_ranking", []):
                self.stdout.write(f"  {s['scenario']:<22} {s['best_runtime']}")

            self.stdout.write("\nStrongest observed differences:")
            for d in insights.get("strongest_differences", []):
                self.stdout.write(
                    f"  {d['metric']}: {d['runtime_a']} vs {d['runtime_b']} = +{d['difference']}"
                )

            self.stdout.write("\nConsistency:")
            for c in insights.get("consistency", []):
                self.stdout.write(f"  {c['runtime']:<8} {c['classification']}")

            self.stdout.write("\nLLM:")
            llm_info = insights.get("llm", {})
            if llm_info.get("available"):
                self.stdout.write(f"  provider:        {llm_info.get('provider')}")
                self.stdout.write(f"  model:           {llm_info.get('model')}")
                self.stdout.write(f"  average latency: {llm_info.get('average_latency_ms')} ms")
                self.stdout.write(f"  total tokens:    {llm_info.get('total_tokens')}")
                self.stdout.write(f"  failures:        {llm_info.get('failure_count')}")
            else:
                self.stdout.write(f"  {llm_info.get('message', 'No Groq runtime data present in this suite.')}")

        # --- decision summary ---
        dec_summary = report.get("decision_summary", {})
        if dec_summary:
            self.stdout.write("\nDecision Summary")
            self.stdout.write("----------------")

            self.stdout.write("\nOverall leader:")
            leader = dec_summary.get("overall_leader", {})
            if leader.get("available"):
                self.stdout.write(f"  {leader.get('runtime')}")
            else:
                self.stdout.write("  unavailable")

            self.stdout.write("\nScenario leadership:")
            for item in dec_summary.get("scenario_leaders", []):
                self.stdout.write(f"  {item.get('scenario'):<22} {item.get('winning_runtime')}")

            self.stdout.write("\nMost consistent:")
            consistent = dec_summary.get("most_consistent_runtime", {})
            if consistent.get("available"):
                self.stdout.write(f"  {consistent.get('runtime')} - {consistent.get('classification')}")
            else:
                self.stdout.write("  unavailable")

            self.stdout.write("\nStrongest observed difference:")
            adv = dec_summary.get("strongest_observed_advantage", {})
            if adv.get("available"):
                self.stdout.write(
                    f"  {adv.get('metric')}: {adv.get('runtime_a')} vs {adv.get('runtime_b')} = +{adv.get('difference')}"
                )
            else:
                self.stdout.write("  unavailable")

            self.stdout.write("\nLLM:")
            llm_summary = dec_summary.get("llm_assessment", {})
            if llm_summary.get("available"):
                self.stdout.write(f"  provider:        {llm_summary.get('provider')}")
                self.stdout.write(f"  model:           {llm_summary.get('model')}")
                self.stdout.write(f"  average latency: {llm_summary.get('average_latency_ms')} ms")
                self.stdout.write(f"  total tokens:    {llm_summary.get('total_tokens')}")
                self.stdout.write(f"  failures:        {llm_summary.get('failure_count')}")
            else:
                self.stdout.write("  unavailable")

        self.stdout.write(
            f"\nRows: {len(report['rows'])}  "
            f"Scenarios: {len(report['scenario_comparison'])}  "
            f"Findings: {len(report['findings'])}"
        )
