# -*- coding: utf-8 -*-
"""Regression tests for the benchmark decision summary & recommendation layer (Step 30).

Verifies that BenchmarkDecisionSummary:
- operates purely on the in-memory insights dictionary without querying the DB,
- selects overall leaders and breaks ties deterministically,
- accurately extracts scenario winners and spreads,
- classifies consistency by smallest wealth range,
- identifies the strongest observed differences,
- handles LLM present/absent states safely,
- gracefully tolerates empty/partial inputs,
- strictly employs observational, non-causal phrasing,
- generates 100% deterministic repeatable output,
- preserves read-only database invariant,
- never invokes experiment runners or LLMs,
- integrates into BenchmarkReporter.build().
"""

import json
from unittest import mock

from django.test import TestCase

from experiments.decision_summary import BenchmarkDecisionSummary
from experiments.insights import BenchmarkInsights
from experiments.models import BenchmarkSuite, ExperimentComparison
from experiments.reporting import BenchmarkReporter


def _sample_insights_data(with_groq: bool = True):
    """Generate synthetic insights dictionary matching BenchmarkInsights.report() output."""
    runtime_ranking = [
        {
            "runtime": "rule",
            "scenario_count": 3,
            "average_total_wealth": 250.0,
            "average_trade_volume": 5.0,
            "average_message_count": 10.0,
            "average_action_diversity": 0.85,
            "average_decision_entropy": 1.3,
        },
        {
            "runtime": "random",
            "scenario_count": 3,
            "average_total_wealth": 150.0,
            "average_trade_volume": 2.0,
            "average_message_count": 4.0,
            "average_action_diversity": 0.5,
            "average_decision_entropy": 0.9,
        },
    ]
    if with_groq:
        runtime_ranking.insert(
            1,
            {
                "runtime": "groq",
                "scenario_count": 3,
                "average_total_wealth": 240.0,
                "average_trade_volume": 6.0,
                "average_message_count": 8.0,
                "average_action_diversity": 0.9,
                "average_decision_entropy": 1.4,
                "average_latency_ms": 115.0,
                "total_tokens": 3000,
                "llm_failures": 1,
                "average_context_chars": 500.0,
            },
        )

    scenario_ranking = [
        {
            "scenario": "Scenario 1",
            "runtime_count": 3 if with_groq else 2,
            "best_runtime": "rule",
            "best_wealth": 260.0,
            "wealth_spread": 100.0,
            "trade_volume": 12,
            "message_count": 20,
        },
        {
            "scenario": "Scenario 2",
            "runtime_count": 3 if with_groq else 2,
            "best_runtime": "groq" if with_groq else "rule",
            "best_wealth": 255.0,
            "wealth_spread": 90.0,
            "trade_volume": 10,
            "message_count": 18,
        },
    ]

    consistency = [
        {
            "runtime": "rule",
            "mean_wealth": 250.0,
            "min_wealth": 245.0,
            "max_wealth": 255.0,
            "wealth_range": 10.0,
            "scenario_count": 3,
            "classification": "consistent",
        },
        {
            "runtime": "random",
            "mean_wealth": 150.0,
            "min_wealth": 120.0,
            "max_wealth": 180.0,
            "wealth_range": 60.0,
            "scenario_count": 3,
            "classification": "volatile",
        },
    ]
    if with_groq:
        consistency.append({
            "runtime": "groq",
            "mean_wealth": 240.0,
            "min_wealth": 220.0,
            "max_wealth": 255.0,
            "wealth_range": 35.0,
            "scenario_count": 3,
            "classification": "mixed",
        })

    strongest_differences = [
        {
            "metric": "wealth",
            "runtime_a": "rule",
            "runtime_b": "random",
            "difference": 100.0,
            "scenario": "Scenario 1",
        },
        {
            "metric": "trade_volume",
            "runtime_a": "groq" if with_groq else "rule",
            "runtime_b": "random",
            "difference": 4.0,
            "scenario": "Scenario 2",
        },
        {
            "metric": "action_diversity",
            "runtime_a": "groq" if with_groq else "rule",
            "runtime_b": "random",
            "difference": 0.4,
            "scenario": "Scenario 1",
        },
    ]

    llm = {
        "available": True,
        "provider": "groq",
        "model": "llama-3.3-70b",
        "scenario_count": 3,
        "total_tokens": 3000,
        "average_latency_ms": 115.0,
        "average_context_chars": 500.0,
        "failure_count": 1,
        "failure_rate": 0.3333,
    } if with_groq else {
        "available": False,
        "message": "No Groq runtime data present in this suite.",
    }

    return {
        "runtime_ranking": runtime_ranking,
        "scenario_ranking": scenario_ranking,
        "strongest_differences": strongest_differences,
        "consistency": consistency,
        "llm": llm,
        "findings": ["Observational findings placeholder."],
    }


def _create_persisted_suite():
    """Create a minimal real BenchmarkSuite in the database for integration testing."""
    suite = BenchmarkSuite.objects.create(
        name="Step 30 Suite",
        seed=1,
        scenarios={"Scen1": {}},
    )
    comp = ExperimentComparison.objects.create(
        name="Step 30 Suite - Scen1",
        seed=1,
        configuration={},
        metrics={
            "rule": {
                "economic": {"total_wealth": 100.0, "trade_volume": 2},
                "social": {"message_count": 4},
                "behavioral": {"action_diversity": 0.6, "decision_entropy": 1.0},
            },
            "random": {
                "economic": {"total_wealth": 80.0, "trade_volume": 1},
                "social": {"message_count": 2},
                "behavioral": {"action_diversity": 0.3, "decision_entropy": 0.8},
            },
        },
        analysis={},
    )
    suite.comparisons.add(comp)
    return suite


class BenchmarkDecisionSummaryTests(TestCase):

    def test_overall_leader_selection(self):
        data = _sample_insights_data(with_groq=True)
        summary = BenchmarkDecisionSummary(data)
        leader = summary.overall_leader()

        self.assertTrue(leader["available"])
        self.assertEqual(leader["runtime"], "rule")
        self.assertEqual(leader["average_total_wealth"], 250.0)
        self.assertIn("rule", leader["statement"])

    def test_deterministic_tie_breaking(self):
        # Tie in wealth: tie broken by action diversity, then alphabetical
        data = {
            "runtime_ranking": [
                {"runtime": "beta", "average_total_wealth": 200.0, "average_action_diversity": 0.9},
                {"runtime": "alpha", "average_total_wealth": 200.0, "average_action_diversity": 0.7},
            ],
            "scenario_ranking": [],
            "strongest_differences": [],
            "consistency": [],
            "llm": {"available": False},
        }
        summary = BenchmarkDecisionSummary(data)
        self.assertEqual(summary.overall_leader()["runtime"], "beta")

    def test_scenario_leaders(self):
        data = _sample_insights_data(with_groq=True)
        summary = BenchmarkDecisionSummary(data)
        leaders = summary.scenario_leaders()

        self.assertEqual(len(leaders), 2)
        self.assertEqual(leaders[0]["scenario"], "Scenario 1")
        self.assertEqual(leaders[0]["winning_runtime"], "rule")
        self.assertEqual(leaders[0]["best_wealth"], 260.0)
        self.assertEqual(leaders[0]["wealth_advantage"], 100.0)

    def test_most_consistent_selection(self):
        data = _sample_insights_data(with_groq=True)
        summary = BenchmarkDecisionSummary(data)
        consistent = summary.most_consistent_runtime()

        self.assertTrue(consistent["available"])
        self.assertEqual(consistent["runtime"], "rule")
        self.assertEqual(consistent["wealth_range"], 10.0)
        self.assertEqual(consistent["classification"], "consistent")

    def test_strongest_difference_selection(self):
        data = _sample_insights_data(with_groq=True)
        summary = BenchmarkDecisionSummary(data)
        diff = summary.strongest_observed_advantage()

        self.assertTrue(diff["available"])
        self.assertEqual(diff["metric"], "wealth")
        self.assertEqual(diff["difference"], 100.0)
        self.assertEqual(diff["runtime_a"], "rule")
        self.assertEqual(diff["runtime_b"], "random")

    def test_llm_assessment_present(self):
        data = _sample_insights_data(with_groq=True)
        summary = BenchmarkDecisionSummary(data)
        llm = summary.llm_assessment()

        self.assertTrue(llm["available"])
        self.assertEqual(llm["provider"], "groq")
        self.assertEqual(llm["model"], "llama-3.3-70b")
        self.assertEqual(llm["failure_count"], 1)

    def test_llm_assessment_absent(self):
        data = _sample_insights_data(with_groq=False)
        summary = BenchmarkDecisionSummary(data)
        llm = summary.llm_assessment()

        self.assertFalse(llm["available"])
        self.assertIn("No Groq runtime data", llm["message"])

    def test_empty_partial_benchmark_handling(self):
        empty_summary = BenchmarkDecisionSummary({})
        report = empty_summary.report()

        self.assertFalse(report["overall_leader"]["available"])
        self.assertEqual(report["scenario_leaders"], [])
        self.assertFalse(report["most_consistent_runtime"]["available"])
        self.assertFalse(report["strongest_observed_advantage"]["available"])
        self.assertFalse(report["llm_assessment"]["available"])
        self.assertIsNone(report["trade_social_summary"]["trade_leader"])
        self.assertEqual(report["coverage_summary"]["total_observations"], 0)

    def test_non_causal_wording(self):
        data = _sample_insights_data(with_groq=True)
        summary = BenchmarkDecisionSummary(data)
        report = summary.report()

        # Collect all text statements and recommendation strings
        text_samples = list(report["recommendations"])
        if report["overall_leader"].get("statement"):
            text_samples.append(report["overall_leader"]["statement"])
        if report["most_consistent_runtime"].get("statement"):
            text_samples.append(report["most_consistent_runtime"]["statement"])
        if report["strongest_observed_advantage"].get("statement"):
            text_samples.append(report["strongest_observed_advantage"]["statement"])
        if report["llm_assessment"].get("statement"):
            text_samples.append(report["llm_assessment"]["statement"])

        for text in text_samples:
            lower = text.lower()
            self.assertNotIn("caused", lower)
            self.assertNotIn("because", lower)
            self.assertNotIn("responsible for", lower)

    def test_deterministic_repeated_output(self):
        data = _sample_insights_data(with_groq=True)
        summary1 = BenchmarkDecisionSummary(data)
        summary2 = BenchmarkDecisionSummary(data)
        rep1 = summary1.report()
        rep2 = summary2.report()

        self.assertEqual(
            json.dumps(rep1, sort_keys=True),
            json.dumps(rep2, sort_keys=True),
        )

    def test_read_only_persistence_behavior(self):
        suite = _create_persisted_suite()
        initial_timestamp = suite.created_at
        initial_metrics = [c.metrics for c in suite.comparisons.all()]

        insights = BenchmarkInsights(suite).report()
        BenchmarkDecisionSummary(insights).report()

        suite.refresh_from_db()
        self.assertEqual(suite.created_at, initial_timestamp)
        current_metrics = [c.metrics for c in suite.comparisons.all()]
        self.assertEqual(initial_metrics, current_metrics)

    def test_no_runner_or_llm_invocation(self):
        with mock.patch("experiments.runner.ExperimentRunner") as mock_exp_runner, \
             mock.patch("experiments.comparison.ExperimentComparisonRunner") as mock_comp_runner:
            data = _sample_insights_data(with_groq=True)
            BenchmarkDecisionSummary(data).report()
            mock_exp_runner.assert_not_called()
            mock_comp_runner.assert_not_called()

    def test_reporter_integration(self):
        suite = _create_persisted_suite()
        reporter = BenchmarkReporter(suite)
        report = reporter.build()

        self.assertIn("decision_summary", report)
        dec = report["decision_summary"]
        expected_keys = {
            "overall_leader",
            "scenario_leaders",
            "most_consistent_runtime",
            "strongest_observed_advantage",
            "llm_assessment",
            "trade_social_summary",
            "coverage_summary",
            "recommendations",
        }
        self.assertEqual(set(dec.keys()), expected_keys)
