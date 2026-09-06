# -*- coding: utf-8 -*-
"""Regression tests for the benchmark insights and decision analysis layer (Step 29).

Verifies that BenchmarkInsights:
- operates as a pure, read-only analytical service over persisted BenchmarkSuite data,
- produces deterministic runtime and scenario rankings,
- calculates cross-scenario consistency classifications and handles edge cases,
- extracts strongest observed differences without causal claims,
- correctly analyzes Groq/LLM metrics when present or absent,
- never invokes ExperimentRunner, ExperimentComparisonRunner, or live LLM APIs,
- never mutates database records,
- generates 100% deterministic, repeatable reports.
"""

import json
from unittest import mock

from django.test import TestCase

from experiments.models import BenchmarkSuite, ExperimentComparison
from experiments.insights import BenchmarkInsights
from experiments.reporting import BenchmarkReporter


def _create_test_suite(with_groq: bool = True):
    """Create a mock BenchmarkSuite with two scenarios and comparison metrics."""
    suite = BenchmarkSuite.objects.create(
        name="Suite 29",
        seed=42,
        scenarios={
            "Scenario A": {"seed": 101},
            "Scenario B": {"seed": 102},
        },
    )

    # Comparison 1 (Scenario A)
    comp_a_metrics = {
        "rule": {
            "economic": {"total_wealth": 200.0, "trade_volume": 5},
            "social": {"message_count": 10},
            "behavioral": {"action_diversity": 0.8, "decision_entropy": 1.2},
        },
        "random": {
            "economic": {"total_wealth": 150.0, "trade_volume": 2},
            "social": {"message_count": 4},
            "behavioral": {"action_diversity": 0.5, "decision_entropy": 0.9},
        },
    }
    if with_groq:
        comp_a_metrics["groq"] = {
            "economic": {"total_wealth": 220.0, "trade_volume": 6},
            "social": {"message_count": 8},
            "behavioral": {"action_diversity": 0.9, "decision_entropy": 1.4},
            "llm": {
                "total_tokens": 1500,
                "average_latency_ms": 120.0,
                "failures": 1,
                "average_context_chars": 600.0,
                "providers": {"groq": 1},
                "models": {"llama-3.3-70b": 1},
            },
        }

    comp_a = ExperimentComparison.objects.create(
        name="Suite 29 - Scenario A",
        seed=101,
        configuration={},
        metrics=comp_a_metrics,
        analysis={},
    )
    suite.comparisons.add(comp_a)

    # Comparison 2 (Scenario B)
    comp_b_metrics = {
        "rule": {
            "economic": {"total_wealth": 195.0, "trade_volume": 4},
            "social": {"message_count": 8},
            "behavioral": {"action_diversity": 0.75, "decision_entropy": 1.1},
        },
        "random": {
            "economic": {"total_wealth": 100.0, "trade_volume": 1},
            "social": {"message_count": 2},
            "behavioral": {"action_diversity": 0.4, "decision_entropy": 0.7},
        },
    }
    if with_groq:
        comp_b_metrics["groq"] = {
            "economic": {"total_wealth": 160.0, "trade_volume": 3},
            "social": {"message_count": 5},
            "behavioral": {"action_diversity": 0.7, "decision_entropy": 1.0},
            "llm": {
                "total_tokens": 1200,
                "average_latency_ms": 110.0,
                "failures": 0,
                "average_context_chars": 550.0,
                "providers": {"groq": 1},
                "models": {"llama-3.3-70b": 1},
            },
        }

    comp_b = ExperimentComparison.objects.create(
        name="Suite 29 - Scenario B",
        seed=102,
        configuration={},
        metrics=comp_b_metrics,
        analysis={},
    )
    suite.comparisons.add(comp_b)

    return suite


class BenchmarkInsightsTests(TestCase):

    def test_load_persisted_suite_and_report_keys(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        report = insights.report()

        expected_keys = {
            "runtime_ranking",
            "scenario_ranking",
            "strongest_differences",
            "consistency",
            "llm",
            "findings",
        }
        self.assertEqual(set(report.keys()), expected_keys)

    def test_runtime_ranking_deterministic_and_tie_breaking(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        ranking = insights.runtime_ranking()

        # Runtimes:
        # groq: avg wealth = (220 + 160) / 2 = 190.0
        # rule: avg wealth = (200 + 195) / 2 = 197.5
        # random: avg wealth = (150 + 100) / 2 = 125.0
        runtimes = [r["runtime"] for r in ranking]
        self.assertEqual(runtimes, ["rule", "groq", "random"])

        rule_entry = next(r for r in ranking if r["runtime"] == "rule")
        self.assertEqual(rule_entry["average_total_wealth"], 197.5)
        self.assertEqual(rule_entry["scenario_count"], 2)

        # Verify tie-breaking when wealth is equal: sort by action diversity then name
        suite2 = BenchmarkSuite.objects.create(name="Tie Suite", seed=1, scenarios={"S1": {}})
        comp_tie = ExperimentComparison.objects.create(
            name="Tie Suite - S1",
            seed=1,
            configuration={},
            metrics={
                "beta": {"economic": {"total_wealth": 100.0}, "behavioral": {"action_diversity": 0.5}},
                "alpha": {"economic": {"total_wealth": 100.0}, "behavioral": {"action_diversity": 0.5}},
                "gamma": {"economic": {"total_wealth": 100.0}, "behavioral": {"action_diversity": 0.8}},
            },
        )
        suite2.comparisons.add(comp_tie)
        tie_ranking = BenchmarkInsights(suite2).runtime_ranking()
        tie_names = [r["runtime"] for r in tie_ranking]
        # gamma has highest diversity (0.8), then alpha precedes beta alphabetically
        self.assertEqual(tie_names, ["gamma", "alpha", "beta"])

    def test_scenario_ranking(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        ranking = insights.scenario_ranking()

        self.assertEqual(len(ranking), 2)
        scenarios = [s["scenario"] for s in ranking]
        self.assertEqual(scenarios, ["Scenario A", "Scenario B"])

        # Scenario A winner is groq (220.0 vs rule 200.0 vs random 150.0) -> spread = 70.0
        scen_a = ranking[0]
        self.assertEqual(scen_a["best_runtime"], "groq")
        self.assertEqual(scen_a["best_wealth"], 220.0)
        self.assertEqual(scen_a["wealth_spread"], 70.0)

        # Scenario B winner is rule (195.0 vs groq 160.0 vs random 100.0) -> spread = 95.0
        scen_b = ranking[1]
        self.assertEqual(scen_b["best_runtime"], "rule")
        self.assertEqual(scen_b["best_wealth"], 195.0)
        self.assertEqual(scen_b["wealth_spread"], 95.0)

    def test_strongest_differences(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        diffs = insights.strongest_differences()

        metric_names = {d["metric"] for d in diffs}
        self.assertIn("wealth", metric_names)
        self.assertIn("trade_volume", metric_names)
        self.assertIn("communication", metric_names)

        wealth_diff = next(d for d in diffs if d["metric"] == "wealth")
        # Largest difference across scenarios: Scenario B rule (195) vs random (100) = 95.0
        self.assertEqual(wealth_diff["scenario"], "Scenario B")
        self.assertEqual(wealth_diff["runtime_a"], "rule")
        self.assertEqual(wealth_diff["runtime_b"], "random")
        self.assertEqual(wealth_diff["difference"], 95.0)

    def test_consistency_classification_and_edge_cases(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        consistency = {c["runtime"]: c for c in insights.consistency_analysis()}

        # rule: wealths 200 and 195. mean = 197.5, range = 5.0, range/mean = 5/197.5 = ~0.0253 <= 0.05 -> consistent
        self.assertEqual(consistency["rule"]["classification"], "consistent")

        # random: wealths 150 and 100. mean = 125.0, range = 50.0, range/mean = 50/125 = 0.40 > 0.15 -> volatile
        self.assertEqual(consistency["random"]["classification"], "volatile")

        # groq: wealths 220 and 160. mean = 190.0, range = 60.0, range/mean = 60/190 = ~0.315 > 0.15 -> volatile
        self.assertEqual(consistency["groq"]["classification"], "volatile")

        # Test mixed classification (between 5% and 15%)
        suite_mixed = BenchmarkSuite.objects.create(
            name="Mixed Suite", seed=1, scenarios={"S1": {}, "S2": {}}
        )
        comp_m1 = ExperimentComparison.objects.create(
            name="Mixed Suite - S1", seed=1, configuration={},
            metrics={"test_rt": {"economic": {"total_wealth": 100.0}}},
        )
        comp_m2 = ExperimentComparison.objects.create(
            name="Mixed Suite - S2", seed=2, configuration={},
            metrics={"test_rt": {"economic": {"total_wealth": 110.0}}},
        )
        suite_mixed.comparisons.add(comp_m1, comp_m2)
        # mean = 105.0, range = 10.0, ratio = 10/105 = 0.0952 (between 0.05 and 0.15) -> mixed
        mixed_res = BenchmarkInsights(suite_mixed).consistency_analysis()
        self.assertEqual(mixed_res[0]["classification"], "mixed")

        # Test zero-wealth edge cases
        suite_zero = BenchmarkSuite.objects.create(
            name="Zero Suite", seed=1, scenarios={"S1": {}, "S2": {}}
        )
        comp_z1 = ExperimentComparison.objects.create(
            name="Zero Suite - S1", seed=1, configuration={},
            metrics={"rt_zero": {"economic": {"total_wealth": 0.0}}},
        )
        comp_z2 = ExperimentComparison.objects.create(
            name="Zero Suite - S2", seed=2, configuration={},
            metrics={"rt_zero": {"economic": {"total_wealth": 0.0}}},
        )
        suite_zero.comparisons.add(comp_z1, comp_z2)
        zero_res = BenchmarkInsights(suite_zero).consistency_analysis()
        self.assertEqual(zero_res[0]["classification"], "consistent")

    def test_llm_analysis_present(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        llm = insights.llm_analysis()

        self.assertTrue(llm["available"])
        self.assertEqual(llm["provider"], "groq")
        self.assertEqual(llm["model"], "llama-3.3-70b")
        self.assertEqual(llm["scenario_count"], 2)
        self.assertEqual(llm["total_tokens"], 2700)
        self.assertEqual(llm["average_latency_ms"], 115.0)
        self.assertEqual(llm["failure_count"], 1)

    def test_llm_analysis_absent(self):
        suite = _create_test_suite(with_groq=False)
        insights = BenchmarkInsights(suite)
        llm = insights.llm_analysis()

        self.assertFalse(llm["available"])
        self.assertEqual(llm["message"], "No Groq runtime data present in this suite.")

    def test_observational_non_causal_findings(self):
        suite = _create_test_suite(with_groq=True)
        insights = BenchmarkInsights(suite)
        findings = insights.findings()

        self.assertGreater(len(findings), 0)
        for f in findings:
            # Observational check: must not contain causal phrasing
            lower = f.lower()
            self.assertNotIn("because", lower)
            self.assertNotIn("caused", lower)
            self.assertNotIn("responsible for", lower)

        # Check Groq mentions model
        groq_f = next((f for f in findings if "groq" in f.lower()), None)
        self.assertIsNotNone(groq_f)
        self.assertIn("llama-3.3-70b", groq_f)

    def test_safety_never_calls_runners_or_llms(self):
        suite = _create_test_suite(with_groq=True)
        with mock.patch("experiments.runner.ExperimentRunner") as mock_exp_runner, \
             mock.patch("experiments.comparison.ExperimentComparisonRunner") as mock_comp_runner:
            insights = BenchmarkInsights(suite)
            insights.report()
            mock_exp_runner.assert_not_called()
            mock_comp_runner.assert_not_called()

    def test_read_only_persistence_guarantee(self):
        suite = _create_test_suite(with_groq=True)
        initial_suite_updated = suite.created_at
        initial_comp_metrics = [c.metrics for c in suite.comparisons.all()]

        BenchmarkInsights(suite).report()

        suite.refresh_from_db()
        self.assertEqual(suite.created_at, initial_suite_updated)
        current_comp_metrics = [c.metrics for c in suite.comparisons.all()]
        self.assertEqual(initial_comp_metrics, current_comp_metrics)

    def test_exact_determinism(self):
        suite = _create_test_suite(with_groq=True)
        insights1 = BenchmarkInsights(suite)
        insights2 = BenchmarkInsights(suite)
        report1 = insights1.report()
        report2 = insights2.report()

        self.assertEqual(
            json.dumps(report1, sort_keys=True),
            json.dumps(report2, sort_keys=True),
        )

    def test_reporter_integration(self):
        suite = _create_test_suite(with_groq=True)
        reporter = BenchmarkReporter(suite)
        built_report = reporter.build()

        self.assertIn("insights", built_report)
        self.assertIn("runtime_ranking", built_report["insights"])
        self.assertIn("findings", built_report["insights"])
