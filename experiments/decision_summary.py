# -*- coding: utf-8 -*-
"""Benchmark Decision Summary & Recommendation Layer (Step 30).

Provides a pure, read-only decision summary service that operates on the
structured analytical output of BenchmarkInsights.report().

Never calls ExperimentRunner, ExperimentComparisonRunner, or any live LLM API.
Produces deterministic leadership recommendations, consistency assessments,
and observational trade/social summaries without causal claims.
"""

from typing import Any, Dict, List


class BenchmarkDecisionSummary:
    """Consumes BenchmarkInsights report dictionary and generates decision-oriented summaries."""

    def __init__(self, insights: Dict[str, Any]):
        self.insights = insights or {}
        self.runtime_rankings = self.insights.get("runtime_ranking", [])
        self.scenario_rankings = self.insights.get("scenario_ranking", [])
        self.strongest_diffs = self.insights.get("strongest_differences", [])
        self.consistency_data = self.insights.get("consistency", [])
        self.llm_data = self.insights.get("llm", {})

    def overall_leader(self) -> Dict[str, Any]:
        """Determine overall leading runtime based on fixed deterministic rules.

        Criteria:
        1. Highest average total wealth
        2. Highest average action diversity
        3. Alphabetical runtime name as tie-breaker
        """
        if not self.runtime_rankings:
            return {
                "available": False,
                "reason": "No runtime ranking data available.",
            }

        leader = self.runtime_rankings[0]
        scenario_count = leader.get("scenario_count", len(self.scenario_rankings))

        scenario_wins = sum(
            1 for s in self.scenario_rankings if s.get("best_runtime") == leader["runtime"]
        )

        return {
            "available": True,
            "runtime": leader["runtime"],
            "average_total_wealth": leader.get("average_total_wealth", 0.0),
            "average_action_diversity": leader.get("average_action_diversity", 0.0),
            "scenario_wins": scenario_wins,
            "total_scenarios": scenario_count,
            "statement": (
                f"{leader['runtime']} recorded the highest average wealth "
                f"({leader.get('average_total_wealth', 0.0)}) and won in "
                f"{scenario_wins} of {scenario_count} observed scenarios."
            ),
        }

    def scenario_leaders(self) -> List[Dict[str, Any]]:
        """Extract leaders for each individual scenario."""
        leaders = []
        for s in self.scenario_rankings:
            leaders.append({
                "scenario": s.get("scenario", "unknown"),
                "winning_runtime": s.get("best_runtime", "unknown"),
                "best_wealth": s.get("best_wealth", 0.0),
                "wealth_advantage": s.get("wealth_spread", 0.0),
                "statement": (
                    f"{s.get('best_runtime')} recorded highest wealth in "
                    f"{s.get('scenario')} ({s.get('best_wealth')}, "
                    f"+{s.get('wealth_spread')} spread)."
                ),
            })
        return leaders

    def most_consistent_runtime(self) -> Dict[str, Any]:
        """Identify runtime with the smallest cross-scenario wealth spread.

        Criteria:
        1. Smallest wealth_range
        2. Highest mean_wealth
        3. Alphabetical runtime name
        """
        if not self.consistency_data:
            return {
                "available": False,
                "reason": "No consistency data available.",
            }

        sorted_consistency = sorted(
            self.consistency_data,
            key=lambda c: (
                c.get("wealth_range", float("inf")),
                -c.get("mean_wealth", 0.0),
                c.get("runtime", ""),
            ),
        )
        best = sorted_consistency[0]
        return {
            "available": True,
            "runtime": best.get("runtime", "unknown"),
            "classification": best.get("classification", "unknown"),
            "wealth_range": best.get("wealth_range", 0.0),
            "mean_wealth": best.get("mean_wealth", 0.0),
            "statement": (
                f"{best.get('runtime')} recorded the lowest cross-scenario wealth "
                f"range ({best.get('wealth_range')}), classified as {best.get('classification')}."
            ),
        }

    def strongest_observed_advantage(self) -> Dict[str, Any]:
        """Identify the single largest observed runtime delta across all metrics and scenarios."""
        if not self.strongest_diffs:
            return {
                "available": False,
                "reason": "No differences data available.",
            }

        sorted_diffs = sorted(
            self.strongest_diffs,
            key=lambda d: (
                -d.get("difference", 0.0),
                d.get("metric", ""),
                d.get("scenario", ""),
                d.get("runtime_a", ""),
                d.get("runtime_b", ""),
            ),
        )
        top = sorted_diffs[0]
        return {
            "available": True,
            "metric": top.get("metric", "unknown"),
            "runtime_a": top.get("runtime_a", "unknown"),
            "runtime_b": top.get("runtime_b", "unknown"),
            "difference": top.get("difference", 0.0),
            "scenario": top.get("scenario", "unknown"),
            "statement": (
                f"Largest observed difference was in {top.get('metric')}: "
                f"{top.get('runtime_a')} vs {top.get('runtime_b')} "
                f"(+{top.get('difference')}) in {top.get('scenario')}."
            ),
        }

    def llm_assessment(self) -> Dict[str, Any]:
        """Summarize persisted LLM runtime observations without making API calls."""
        if not self.llm_data or not self.llm_data.get("available"):
            return {
                "available": False,
                "message": "No Groq runtime data present in this suite.",
            }

        return {
            "available": True,
            "provider": self.llm_data.get("provider", "unknown"),
            "model": self.llm_data.get("model", "unknown"),
            "scenario_count": self.llm_data.get("scenario_count", 0),
            "average_latency_ms": self.llm_data.get("average_latency_ms", 0.0),
            "total_tokens": self.llm_data.get("total_tokens", 0),
            "failure_count": self.llm_data.get("failure_count", 0),
            "failure_rate": self.llm_data.get("failure_rate", 0.0),
            "statement": (
                f"Groq runtime used provider={self.llm_data.get('provider')}, "
                f"model={self.llm_data.get('model')} with "
                f"{self.llm_data.get('failure_count')} recorded failures across "
                f"{self.llm_data.get('scenario_count')} scenarios."
            ),
        }

    def trade_social_summary(self) -> Dict[str, Any]:
        """Identify highest trade and social performers across all scenarios."""
        if not self.runtime_rankings:
            return {
                "trade_leader": None,
                "communication_leader": None,
            }

        trade_leader = max(
            self.runtime_rankings,
            key=lambda r: (
                r.get("average_trade_volume", 0.0),
                -ord(r.get("runtime", "z")[0]) if r.get("runtime") else 0,
            ),
        )
        comm_leader = max(
            self.runtime_rankings,
            key=lambda r: (
                r.get("average_message_count", 0.0),
                -ord(r.get("runtime", "z")[0]) if r.get("runtime") else 0,
            ),
        )

        return {
            "trade_leader": {
                "runtime": trade_leader["runtime"],
                "average_trade_volume": trade_leader.get("average_trade_volume", 0.0),
                "statement": (
                    f"{trade_leader['runtime']} recorded the highest average trade "
                    f"volume ({trade_leader.get('average_trade_volume', 0.0)})."
                ),
            },
            "communication_leader": {
                "runtime": comm_leader["runtime"],
                "average_message_count": comm_leader.get("average_message_count", 0.0),
                "statement": (
                    f"{comm_leader['runtime']} recorded the highest average message "
                    f"count ({comm_leader.get('average_message_count', 0.0)})."
                ),
            },
        }

    def coverage_summary(self) -> Dict[str, Any]:
        """Assess scenario and runtime coverage across the benchmark suite."""
        scenarios = [s.get("scenario") for s in self.scenario_rankings if s.get("scenario")]
        runtimes = [r.get("runtime") for r in self.runtime_rankings if r.get("runtime")]
        total_observations = sum(
            s.get("runtime_count", len(runtimes)) for s in self.scenario_rankings
        )

        return {
            "scenario_count": len(scenarios),
            "runtime_count": len(runtimes),
            "scenarios": scenarios,
            "runtimes": runtimes,
            "total_observations": total_observations,
        }

    def recommendations(self) -> List[str]:
        """Generate concise, strictly observational recommendation items."""
        recs = []
        leader = self.overall_leader()
        if leader.get("available"):
            recs.append(
                f"Overall leader: {leader['runtime']} recorded the highest average wealth "
                f"({leader['average_total_wealth']})."
            )

        consistent = self.most_consistent_runtime()
        if consistent.get("available"):
            recs.append(
                f"Stability recommendation: {consistent['runtime']} demonstrated the lowest "
                f"cross-scenario wealth variation (range: {consistent['wealth_range']})."
            )

        strongest = self.strongest_observed_advantage()
        if strongest.get("available"):
            recs.append(
                f"Key differentiator: {strongest['metric']} observed largest gap "
                f"({strongest['runtime_a']} vs {strongest['runtime_b']} = +{strongest['difference']} "
                f"in {strongest['scenario']})."
            )

        llm = self.llm_assessment()
        if llm.get("available"):
            recs.append(
                f"LLM observation: {llm['provider']}/{llm['model']} recorded "
                f"avg latency of {llm['average_latency_ms']} ms with {llm['failure_count']} failures."
            )
        else:
            recs.append("LLM observation: No Groq runtime data present in this suite.")

        recs.append(
            "All recommendations are observational summaries of persisted benchmark results "
            "and do not infer causality."
        )
        return recs

    def report(self) -> Dict[str, Any]:
        """Return the complete decision summary report."""
        return {
            "overall_leader": self.overall_leader(),
            "scenario_leaders": self.scenario_leaders(),
            "most_consistent_runtime": self.most_consistent_runtime(),
            "strongest_observed_advantage": self.strongest_observed_advantage(),
            "llm_assessment": self.llm_assessment(),
            "trade_social_summary": self.trade_social_summary(),
            "coverage_summary": self.coverage_summary(),
            "recommendations": self.recommendations(),
        }
