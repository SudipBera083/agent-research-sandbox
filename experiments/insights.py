# -*- coding: utf-8 -*-
"""Benchmark Insights & Decision Analysis layer (Step 29).

Provides a pure, read-only analytics service that inspects already-persisted
BenchmarkSuite, ExperimentComparison, and metric data.

Never calls ExperimentRunner, ExperimentComparisonRunner, or any live LLM API.
Produces deterministic rankings, cross-scenario consistency classifications,
strongest observed metric differences, and observational, non-causal findings.
"""

from typing import Any, Dict, List


class BenchmarkInsights:
    """Read-only analysis service operating on persisted BenchmarkSuite data."""

    def __init__(self, suite):
        self.suite = suite
        self.comparisons = list(suite.comparisons.order_by("id"))
        self.scenario_names = sorted(suite.scenarios.keys())

        # Map scenario names to comparisons
        comp_by_scenario = {}
        for comp in self.comparisons:
            prefix = f"{self.suite.name} - "
            if comp.name.startswith(prefix) and comp.name[len(prefix):] in self.scenario_names:
                comp_by_scenario[comp.name[len(prefix):]] = comp

        if comp_by_scenario:
            self.scenario_comp_pairs = [
                (s, comp_by_scenario[s])
                for s in self.scenario_names
                if s in comp_by_scenario
            ]
        else:
            self.scenario_comp_pairs = list(zip(self.scenario_names, self.comparisons))

        # Parse flattened scenario-runtime metrics for deterministic analysis
        self._records = self._collect_records()

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _collect_records(self) -> List[Dict[str, Any]]:
        """Flatten scenario comparisons into normalized observational records."""
        records = []
        for scenario, comparison in self.scenario_comp_pairs:
            metrics_dict = comparison.metrics or {}
            for runtime in sorted(metrics_dict.keys()):
                m = metrics_dict[runtime]
                if not isinstance(m, dict):
                    continue

                economic = m.get("economic", {})
                social = m.get("social", {})
                behavioral = m.get("behavioral", {})
                llm = m.get("llm", {})

                # Extract provider and model if present
                provider = m.get("provider")
                model = m.get("model")
                if not provider and isinstance(llm, dict):
                    if "providers" in llm and llm["providers"]:
                        provider = list(llm["providers"].keys())[0]
                    elif "provider" in llm:
                        provider = llm["provider"]
                if not model and isinstance(llm, dict):
                    if "models" in llm and llm["models"]:
                        model = list(llm["models"].keys())[0]
                    elif "model" in llm:
                        model = llm["model"]

                records.append({
                    "scenario": scenario,
                    "runtime": runtime,
                    "total_wealth": float(economic.get("total_wealth", m.get("total_wealth", 0))),
                    "trade_volume": int(economic.get("trade_volume", m.get("trade_volume", 0))),
                    "messages": int(social.get("message_count", m.get("messages", m.get("message_count", 0)))),
                    "action_diversity": float(behavioral.get("action_diversity", m.get("action_diversity", 0))),
                    "decision_entropy": float(behavioral.get("decision_entropy", m.get("decision_entropy", 0))),
                    "llm_tokens": int(llm.get("total_tokens", m.get("total_tokens", 0))),
                    "llm_latency": float(llm.get("average_latency_ms", m.get("average_latency_ms", 0))),
                    "llm_failures": int(llm.get("failures", m.get("failures", 0))),
                    "average_context_chars": float(llm.get("average_context_chars", m.get("average_context_chars", 0))),
                    "has_llm_data": bool(
                        runtime == "groq"
                        or "llm" in m
                        or "provider" in m
                        or m.get("total_tokens", 0) > 0
                        or m.get("average_latency_ms", 0) > 0
                    ),
                    "provider": provider or "unknown",
                    "model": model or "unknown",
                })

        records.sort(key=lambda r: (r["scenario"], r["runtime"]))
        return records

    @staticmethod
    def _avg(values) -> float:
        v = list(values)
        return sum(v) / len(v) if v else 0.0

    # ------------------------------------------------------------------
    # Core insight methods
    # ------------------------------------------------------------------

    def runtime_ranking(self) -> List[Dict[str, Any]]:
        """Rank runtimes deterministically across all scenarios.

        Ranking criteria:
        1. Highest average total wealth
        2. Highest average action diversity
        3. Alphabetical runtime name as tie-breaker
        """
        runtimes = sorted({r["runtime"] for r in self._records})
        rankings = []

        for rt in runtimes:
            rt_records = [r for r in self._records if r["runtime"] == rt]
            if not rt_records:
                continue

            entry = {
                "runtime": rt,
                "scenario_count": len(rt_records),
                "average_total_wealth": round(self._avg(r["total_wealth"] for r in rt_records), 2),
                "average_trade_volume": round(self._avg(r["trade_volume"] for r in rt_records), 2),
                "average_message_count": round(self._avg(r["messages"] for r in rt_records), 2),
                "average_action_diversity": round(self._avg(r["action_diversity"] for r in rt_records), 4),
                "average_decision_entropy": round(self._avg(r["decision_entropy"] for r in rt_records), 4),
            }

            has_llm = any(r["has_llm_data"] for r in rt_records)
            if has_llm:
                entry["average_latency_ms"] = round(self._avg(r["llm_latency"] for r in rt_records), 2)
                entry["total_tokens"] = sum(r["llm_tokens"] for r in rt_records)
                entry["llm_failures"] = sum(r["llm_failures"] for r in rt_records)
                entry["average_context_chars"] = round(self._avg(r["average_context_chars"] for r in rt_records), 2)

            rankings.append(entry)

        # Deterministic sort: (-wealth, -diversity, runtime)
        rankings.sort(
            key=lambda x: (
                -x["average_total_wealth"],
                -x["average_action_diversity"],
                x["runtime"],
            )
        )
        return rankings

    def scenario_ranking(self) -> List[Dict[str, Any]]:
        """Evaluate each scenario's performance and determine leaders.

        Sorted alphabetically by scenario name.
        """
        scenarios = sorted({r["scenario"] for r in self._records})
        results = []

        for s in scenarios:
            s_records = [r for r in self._records if r["scenario"] == s]
            if not s_records:
                continue

            # Deterministic best runtime: highest wealth, then alphabetical
            best_record = max(
                s_records,
                key=lambda r: (r["total_wealth"], -ord(r["runtime"][0]) if r["runtime"] else 0),
            )
            wealths = [r["total_wealth"] for r in s_records]
            best_wealth = max(wealths)
            min_wealth = min(wealths)

            results.append({
                "scenario": s,
                "runtime_count": len(s_records),
                "best_runtime": best_record["runtime"],
                "best_wealth": round(best_wealth, 2),
                "wealth_spread": round(best_wealth - min_wealth, 2),
                "trade_volume": sum(r["trade_volume"] for r in s_records),
                "message_count": sum(r["messages"] for r in s_records),
            })

        results.sort(key=lambda x: x["scenario"])
        return results

    def strongest_differences(self) -> List[Dict[str, Any]]:
        """Identify the largest observed runtime differences for key metrics.

        Metrics analyzed:
        - wealth
        - trade_volume
        - communication
        - action_diversity
        - decision_entropy
        - llm_latency
        - llm_tokens
        """
        metric_keys = [
            ("wealth", "total_wealth"),
            ("trade_volume", "trade_volume"),
            ("communication", "messages"),
            ("action_diversity", "action_diversity"),
            ("decision_entropy", "decision_entropy"),
            ("llm_latency", "llm_latency"),
            ("llm_tokens", "llm_tokens"),
        ]

        scenarios = sorted({r["scenario"] for r in self._records})
        differences = []

        for label, key in metric_keys:
            max_diff = -1.0
            best_pair = None

            for s in scenarios:
                s_records = [r for r in self._records if r["scenario"] == s]
                # Compare all distinct pairs
                for i in range(len(s_records)):
                    for j in range(i + 1, len(s_records)):
                        r1 = s_records[i]
                        r2 = s_records[j]

                        # Skip LLM comparisons if neither has LLM data
                        if label.startswith("llm_") and not (r1["has_llm_data"] or r2["has_llm_data"]):
                            continue

                        v1 = r1[key]
                        v2 = r2[key]
                        diff = abs(v1 - v2)

                        # Determine leader
                        if v1 >= v2:
                            leader, follower = r1["runtime"], r2["runtime"]
                        else:
                            leader, follower = r2["runtime"], r1["runtime"]

                        if diff > max_diff:
                            max_diff = diff
                            best_pair = {
                                "metric": label,
                                "runtime_a": leader,
                                "runtime_b": follower,
                                "difference": round(diff, 4),
                                "scenario": s,
                            }

            if best_pair is not None and (max_diff > 0 or not label.startswith("llm_")):
                differences.append(best_pair)

        # Sort differences deterministically by metric name
        differences.sort(key=lambda d: d["metric"])
        return differences

    def consistency_analysis(self) -> List[Dict[str, Any]]:
        """Determine whether runtime behavior is consistent across scenarios.

        Classification rule:
        - scenario_count <= 1 -> "consistent" (no variation observed)
        - mean_wealth == 0:
            - wealth_range == 0 -> "consistent"
            - wealth_range > 0 -> "volatile"
        - range <= 5% of mean_wealth (range / mean <= 0.05) -> "consistent"
        - range <= 15% of mean_wealth (range / mean <= 0.15) -> "mixed"
        - otherwise -> "volatile"
        """
        runtimes = sorted({r["runtime"] for r in self._records})
        results = []

        for rt in runtimes:
            rt_records = [r for r in self._records if r["runtime"] == rt]
            if not rt_records:
                continue

            wealths = [r["total_wealth"] for r in rt_records]
            mean_wealth = self._avg(wealths)
            min_wealth = min(wealths)
            max_wealth = max(wealths)
            wealth_range = max_wealth - min_wealth

            if len(wealths) <= 1:
                classification = "consistent"
            elif mean_wealth == 0:
                classification = "consistent" if wealth_range == 0 else "volatile"
            else:
                ratio = wealth_range / abs(mean_wealth)
                if ratio <= 0.05:
                    classification = "consistent"
                elif ratio <= 0.15:
                    classification = "mixed"
                else:
                    classification = "volatile"

            results.append({
                "runtime": rt,
                "mean_wealth": round(mean_wealth, 2),
                "min_wealth": round(min_wealth, 2),
                "max_wealth": round(max_wealth, 2),
                "wealth_range": round(wealth_range, 2),
                "scenario_count": len(rt_records),
                "classification": classification,
            })

        results.sort(key=lambda x: x["runtime"])
        return results

    def llm_analysis(self) -> Dict[str, Any]:
        """Analyze only persisted Groq/LLM metrics without live provider calls."""
        llm_records = [r for r in self._records if r["has_llm_data"]]
        if not llm_records:
            return {
                "available": False,
                "message": "No Groq runtime data present in this suite.",
            }

        total_tokens = sum(r["llm_tokens"] for r in llm_records)
        avg_latency = self._avg(r["llm_latency"] for r in llm_records)
        avg_context = self._avg(r["average_context_chars"] for r in llm_records)
        failures = sum(r["llm_failures"] for r in llm_records)

        # Identify primary provider and model from persisted records
        provider = next((r["provider"] for r in llm_records if r["provider"] != "unknown"), "groq")
        model = next((r["model"] for r in llm_records if r["model"] != "unknown"), "unknown")

        scenario_count = len({r["scenario"] for r in llm_records})
        failure_rate = round(failures / max(1, scenario_count), 4)

        return {
            "available": True,
            "provider": provider,
            "model": model,
            "scenario_count": scenario_count,
            "total_tokens": total_tokens,
            "average_latency_ms": round(avg_latency, 2),
            "average_context_chars": round(avg_context, 2),
            "failure_count": failures,
            "failure_rate": failure_rate,
        }

    def findings(self) -> List[str]:
        """Generate human-readable, non-causal observational findings."""
        if not self._records:
            return ["No benchmark records available to analyze."]

        rankings = self.runtime_ranking()
        differences = self.strongest_differences()
        consistency = self.consistency_analysis()
        llm = self.llm_analysis()

        findings_list = []

        # 1. Wealth leader
        if rankings:
            leader = rankings[0]
            findings_list.append(
                f"Highest observed average wealth: {leader['runtime']} "
                f"({leader['average_total_wealth']})."
            )

        # 2. Largest observed wealth difference
        wealth_diff = next((d for d in differences if d["metric"] == "wealth"), None)
        if wealth_diff:
            findings_list.append(
                f"Largest observed wealth difference: {wealth_diff['runtime_a']} vs "
                f"{wealth_diff['runtime_b']} in {wealth_diff['scenario']} "
                f"({wealth_diff['difference']})."
            )

        # 3. Consistency
        consistent_rts = [c["runtime"] for c in consistency if c["classification"] == "consistent"]
        if consistent_rts:
            findings_list.append(
                f"Most consistent runtime by wealth: {', '.join(consistent_rts)}."
            )
        elif consistency:
            findings_list.append(
                f"Runtime wealth consistency: {consistency[0]['runtime']} "
                f"classified as {consistency[0]['classification']}."
            )

        # 4. Communication activity
        if rankings:
            comm_leader = max(rankings, key=lambda x: x["average_message_count"])
            findings_list.append(
                f"Highest communication activity: {comm_leader['runtime']} "
                f"({comm_leader['average_message_count']} avg messages)."
            )

        # 5. LLM / Groq finding
        if llm.get("available"):
            findings_list.append(
                f"Groq runtime used provider={llm['provider']}, model={llm['model']} "
                f"with {llm['failure_count']} recorded failures."
            )
        else:
            findings_list.append("No Groq runtime data present in this suite.")

        # 6. Observational disclaimer
        findings_list.append(
            "All findings summarise persisted benchmark results and do not infer causality."
        )

        return findings_list

    def report(self) -> Dict[str, Any]:
        """Generate the complete deterministic insights report."""
        return {
            "runtime_ranking": self.runtime_ranking(),
            "scenario_ranking": self.scenario_ranking(),
            "strongest_differences": self.strongest_differences(),
            "consistency": self.consistency_analysis(),
            "llm": self.llm_analysis(),
            "findings": self.findings(),
        }
