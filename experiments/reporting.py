import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .insights import BenchmarkInsights


class BenchmarkReporter:
    """
    Read-only reporter that consumes a persisted BenchmarkSuite and its
    linked ExperimentComparison objects.

    Never calls ExperimentRunner, ExperimentComparisonRunner, or any
    LLMProvider.  All data is read from comparison.metrics as saved by
    the BenchmarkRunner.
    """

    def __init__(self, suite):
        self.suite = suite
        self.comparisons = list(
            suite.comparisons.order_by("id")
        )
        self.scenario_names = sorted(suite.scenarios.keys())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self):
        rows = self.rows()
        return {
            "suite": {
                "id": self.suite.id,
                "name": self.suite.name,
                "seed": self.suite.seed,
            },
            "rows": rows,
            "runtime_comparison": self.runtime_comparison(rows),
            "scenario_comparison": self.scenario_comparison(rows),
            "findings": self.findings(rows),
            "charts": self.charts(rows),
            "insights": BenchmarkInsights(self.suite).report(),
        }

    # ------------------------------------------------------------------
    # Row normalisation
    # ------------------------------------------------------------------

    def rows(self):
        """
        Flatten every scenario x runtime into a single list of report rows.

        Row shape:
            {
                "scenario":        str,
                "runtime":         str,   # "rule" | "random" | "groq"
                "total_wealth":    float,
                "trade_volume":    int,
                "messages":        int,
                "action_diversity":int,
                "llm_tokens":      int,
                "llm_latency":     float,
                "llm_failures":    int,
            }
        """
        rows = []

        comp_by_scenario = {}
        for comp in self.comparisons:
            prefix = f"{self.suite.name} - "
            if comp.name.startswith(prefix) and comp.name[len(prefix):] in self.scenario_names:
                comp_by_scenario[comp.name[len(prefix):]] = comp

        if comp_by_scenario:
            scenario_comp_pairs = [
                (s, comp_by_scenario[s])
                for s in self.scenario_names
                if s in comp_by_scenario
            ]
        else:
            scenario_comp_pairs = list(zip(self.scenario_names, self.comparisons))

        for scenario, comparison in scenario_comp_pairs:
            for runtime in sorted(comparison.metrics.keys()):
                metrics = comparison.metrics[runtime]
                economic = metrics.get("economic", {})
                social = metrics.get("social", {})
                behavioral = metrics.get("behavioral", {})
                llm = metrics.get("llm", {})
                rows.append({
                    "scenario": scenario,
                    "runtime": runtime,
                    "total_wealth": economic.get("total_wealth", metrics.get("total_wealth", 0)),
                    "trade_volume": economic.get("trade_volume", metrics.get("trade_volume", 0)),
                    "messages": social.get("message_count", metrics.get("messages", metrics.get("message_count", 0))),
                    "action_diversity": behavioral.get(
                        "action_diversity", metrics.get("action_diversity", 0)
                    ),
                    "llm_tokens": llm.get("total_tokens", metrics.get("total_tokens", 0)),
                    "llm_latency": llm.get("average_latency_ms", metrics.get("average_latency_ms", 0)),
                    "llm_failures": llm.get("failures", metrics.get("failures", 0)),
                })

        # Deterministic ordering of rows: first by scenario, then by runtime alphabetically
        rows.sort(key=lambda r: (r["scenario"], r["runtime"]))
        return rows

    # ------------------------------------------------------------------
    # Comparisons
    # ------------------------------------------------------------------

    def runtime_comparison(self, rows):
        """Aggregate metrics per runtime, averaged across all scenarios."""
        result = {}
        for runtime in sorted({row["runtime"] for row in rows}):
            runtime_rows = [
                row for row in rows if row["runtime"] == runtime
            ]
            result[runtime] = {
                "average_total_wealth": self._average(
                    row["total_wealth"] for row in runtime_rows
                ),
                "average_trade_volume": self._average(
                    row["trade_volume"] for row in runtime_rows
                ),
                "average_messages": self._average(
                    row["messages"] for row in runtime_rows
                ),
                "average_action_diversity": self._average(
                    row["action_diversity"] for row in runtime_rows
                ),
                "total_llm_tokens": sum(
                    row["llm_tokens"] for row in runtime_rows
                ),
                "average_llm_latency": self._average(
                    row["llm_latency"] for row in runtime_rows
                ),
                "total_llm_failures": sum(
                    row["llm_failures"] for row in runtime_rows
                ),
            }
        return result

    def scenario_comparison(self, rows):
        """
        For each scenario show every runtime side-by-side.

        Example:
            {
              "baseline": {
                "groq":   {"total_wealth": ..., "trade_volume": ..., ...},
                "random": {...},
                "rule":   {...},
              },
              ...
            }
        """
        result = {}
        for scenario in self.scenario_names:
            result[scenario] = {
                row["runtime"]: {
                    "total_wealth": row["total_wealth"],
                    "trade_volume": row["trade_volume"],
                    "messages": row["messages"],
                    "action_diversity": row["action_diversity"],
                }
                for row in rows
                if row["scenario"] == scenario
            }
        return result

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def findings(self, rows):
        """
        Return a list of finding dicts:
            {"kind": "measured" | "interpretation", "text": str}

        Every "measured" finding is a direct observation from persisted
        data.  "interpretation" findings are explicitly labelled so
        consumers can distinguish them.
        """
        if not rows:
            return []

        groq_rows = [row for row in rows if row["runtime"] == "groq"]
        has_groq = bool(groq_rows)
        provider = None
        model = None

        for comp in self.comparisons:
            if not comp.metrics:
                continue
            groq_metric = comp.metrics.get("groq")
            if groq_metric and isinstance(groq_metric, dict):
                has_groq = True
                if "provider" in groq_metric:
                    provider = groq_metric["provider"]
                if "model" in groq_metric:
                    model = groq_metric["model"]
                llm_data = groq_metric.get("llm", {})
                if isinstance(llm_data, dict):
                    if "providers" in llm_data and llm_data["providers"]:
                        provider = list(llm_data["providers"].keys())[0]
                    if "models" in llm_data and llm_data["models"]:
                        model = list(llm_data["models"].keys())[0]
                    if "provider" in llm_data:
                        provider = llm_data["provider"]
                    if "model" in llm_data:
                        model = llm_data["model"]
                break

        findings = []

        if has_groq:
            provider_str = provider if provider else "unknown"
            model_str = model if model else "unknown"
            findings.append({
                "kind": "measured",
                "type": "measured",
                "text": f"Groq runtime used provider={provider_str}, model={model_str}.",
            })
        else:
            findings.append({
                "kind": "measured",
                "type": "measured",
                "text": "No Groq runtime data present in this suite.",
            })

        wealth_winner = max(rows, key=lambda row: row["total_wealth"])
        wealth_loser = min(rows, key=lambda row: row["total_wealth"])
        active_winner = max(
            rows,
            key=lambda row: row["messages"] + row["trade_volume"],
        )
        active_loser = min(
            rows,
            key=lambda row: row["messages"] + row["trade_volume"],
        )
        trade_winner = max(rows, key=lambda row: row["trade_volume"])
        msg_winner = max(rows, key=lambda row: row["messages"])

        findings.extend([
            {
                "kind": "measured",
                "type": "measured",
                "text": (
                    f"Highest measured wealth: "
                    f"{wealth_winner['runtime']} in "
                    f"{wealth_winner['scenario']} "
                    f"({wealth_winner['total_wealth']})."
                ),
            },
            {
                "kind": "measured",
                "type": "measured",
                "text": (
                    f"Lowest measured wealth: "
                    f"{wealth_loser['runtime']} in "
                    f"{wealth_loser['scenario']} "
                    f"({wealth_loser['total_wealth']})."
                ),
            },
            {
                "kind": "measured",
                "type": "measured",
                "text": (
                    f"Most active runtime/scenario (messages + trades): "
                    f"{active_winner['runtime']} in "
                    f"{active_winner['scenario']} "
                    f"({active_winner['messages']} messages, "
                    f"{active_winner['trade_volume']} trades)."
                ),
            },
            {
                "kind": "measured",
                "type": "measured",
                "text": (
                    f"Least active runtime/scenario: "
                    f"{active_loser['runtime']} in "
                    f"{active_loser['scenario']} "
                    f"({active_loser['messages']} messages, "
                    f"{active_loser['trade_volume']} trades)."
                ),
            },
            {
                "kind": "measured",
                "type": "measured",
                "text": (
                    f"Highest single-run trade volume: "
                    f"{trade_winner['runtime']} in "
                    f"{trade_winner['scenario']} "
                    f"({trade_winner['trade_volume']} completed trades)."
                ),
            },
            {
                "kind": "measured",
                "type": "measured",
                "text": (
                    f"Highest single-run communication: "
                    f"{msg_winner['runtime']} in "
                    f"{msg_winner['scenario']} "
                    f"({msg_winner['messages']} messages)."
                ),
            },
        ])

        if groq_rows:
            total_failures = sum(
                row["llm_failures"] for row in groq_rows
            )
            total_tokens = sum(
                row["llm_tokens"] for row in groq_rows
            )
            avg_latency = self._average(
                row["llm_latency"] for row in groq_rows
            )
            findings += [
                {
                    "kind": "measured",
                    "type": "measured",
                    "text": (
                        f"Groq recorded {total_failures} validation/"
                        f"provider failures across the suite."
                    ),
                },
                {
                    "kind": "measured",
                    "type": "measured",
                    "text": (
                        f"Groq consumed {total_tokens} total LLM tokens "
                        f"with an average latency of "
                        f"{avg_latency:.1f} ms per decision."
                    ),
                },
            ]

        findings.append({
            "kind": "interpretation",
            "type": "interpretation",
            "text": (
                "These findings summarise persisted results; "
                "they do not explain causality."
            ),
        })
        return findings

    # ------------------------------------------------------------------
    # Charts (inline data for JSON)
    # ------------------------------------------------------------------

    def charts(self, rows):
        """
        Return chart data as plain lists of dicts (embedded in the JSON
        report).  For actual PNG image files use export_charts().
        """
        return {
            "wealth": self._chart(rows, "total_wealth"),
            "trade_volume": self._chart(rows, "trade_volume"),
            "communication": self._chart(rows, "messages"),
            "llm_latency": self._chart(rows, "llm_latency"),
            "llm_tokens": self._chart(rows, "llm_tokens"),
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_json(self, path):
        """Write the full report to a JSON file.  Returns the Path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.build(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def export_csv(self, path):
        """Write the flattened row data to a CSV file.  Returns the Path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.rows()
        fieldnames = [
            "scenario",
            "runtime",
            "total_wealth",
            "trade_volume",
            "messages",
            "action_diversity",
            "llm_tokens",
            "llm_latency",
            "llm_failures",
        ] if rows else []
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            if fieldnames:
                writer.writeheader()
                writer.writerows(rows)
        return path

    def export_charts(self, output_dir):
        """
        Generate PNG chart files using matplotlib and write them to
        output_dir.  Returns a dict of {chart_name: absolute_path_str}.
        Returns an empty dict if matplotlib is not installed.

        Charts produced:
            wealth.png       - total wealth grouped by runtime / scenario
            trade_volume.png - completed trades grouped by runtime / scenario
            communication.png- messages sent grouped by runtime / scenario
            llm_latency.png  - avg LLM latency grouped by runtime / scenario
            llm_tokens.png   - total LLM tokens grouped by runtime / scenario

        This method never modifies any model or calls any runner.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")       # non-interactive backend
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            return {}

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        rows = self.rows()
        scenarios = list(dict.fromkeys(row["scenario"] for row in rows))
        runtimes = sorted({row["runtime"] for row in rows})
        chart_paths = {}

        palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        runtime_colours = {
            rt: palette[i % len(palette)]
            for i, rt in enumerate(runtimes)
        }

        def _values_for(metric):
            return {
                runtime: [
                    next(
                        (
                            row[metric]
                            for row in rows
                            if row["scenario"] == s
                            and row["runtime"] == runtime
                        ),
                        0,
                    )
                    for s in scenarios
                ]
                for runtime in runtimes
            }

        def _grouped_bar(metric, title, ylabel, filename):
            values = _values_for(metric)
            x = np.arange(len(scenarios))
            n = len(runtimes)
            width = 0.7 / n

            fig, ax = plt.subplots(
                figsize=(max(8, len(scenarios) * 1.6), 5)
            )
            for i, runtime in enumerate(runtimes):
                offset = (i - n / 2 + 0.5) * width
                ax.bar(
                    x + offset,
                    values[runtime],
                    width,
                    label=runtime,
                    color=runtime_colours[runtime],
                )

            ax.set_title(title, fontsize=13, fontweight="bold")
            ax.set_ylabel(ylabel)
            ax.set_xticks(x)
            ax.set_xticklabels(scenarios, rotation=20, ha="right")
            ax.legend(title="Runtime")
            ax.grid(axis="y", linestyle="--", alpha=0.4)
            fig.tight_layout()

            path = output_dir / filename
            fig.savefig(path, dpi=120)
            plt.close(fig)
            return path

        chart_paths["wealth"] = _grouped_bar(
            "total_wealth",
            "Total Wealth by Runtime / Scenario",
            "Total Wealth",
            "wealth.png",
        )
        chart_paths["trade_volume"] = _grouped_bar(
            "trade_volume",
            "Trade Volume by Runtime / Scenario",
            "Completed Trades",
            "trade_volume.png",
        )
        chart_paths["communication"] = _grouped_bar(
            "messages",
            "Communication by Runtime / Scenario",
            "Messages Sent",
            "communication.png",
        )
        chart_paths["llm_latency"] = _grouped_bar(
            "llm_latency",
            "LLM Average Latency by Runtime / Scenario (ms)",
            "Latency (ms)",
            "llm_latency.png",
        )
        chart_paths["llm_tokens"] = _grouped_bar(
            "llm_tokens",
            "LLM Total Tokens by Runtime / Scenario",
            "Tokens",
            "llm_tokens.png",
        )

        expected = [
            "wealth.png",
            "trade_volume.png",
            "communication.png",
            "llm_latency.png",
            "llm_tokens.png",
        ]

        missing = [
            name
            for name in expected
            if not (output_dir / name).exists()
        ]

        if missing:
            raise RuntimeError(
                f"Benchmark chart generation failed; missing: {', '.join(missing)}"
            )

        return {name: str(path) for name, path in chart_paths.items()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _average(values):
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _chart(rows, metric):
        return [
            {
                "scenario": row["scenario"],
                "runtime": row["runtime"],
                "value": row[metric],
            }
            for row in rows
        ]
