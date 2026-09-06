# -*- coding: utf-8 -*-
"""Automated regression tests for the benchmark reporting layer (Step 28).

These tests verify that the reporter:
* loads a persisted BenchmarkSuite without side‑effects,
* produces deterministic output (scenario & runtime ordering),
* generates matching CSV and JSON rows,
* creates the five expected chart PNG files,
* correctly handles Groq‑present and Groq‑absent data,
* never instantiates any experiment runner or LLM provider.

All tests are pure unit‑tests – they use Django's TestCase and a temporary directory
for file exports. No network calls are performed.
"""

import shutil
import tempfile
from pathlib import Path
from unittest import mock
import json

from django.test import TestCase

from experiments.models import BenchmarkSuite, ExperimentComparison
from experiments.reporting import BenchmarkReporter


def _create_suite(with_groq: bool = True):
    """Create a BenchmarkSuite with two scenarios and a single comparison.

    Parameters
    ----------
    with_groq: bool
        Include a ``groq`` runtime entry in the persisted metrics when True.
    """
    suite = BenchmarkSuite.objects.create(
        name="test suite",
        seed=42,
        scenarios={"Scenario 1": {}, "Scenario 2": {}},
    )

    metrics = {
        "rule": {
            "total_tokens": 100,
            "average_latency_ms": 50,
            "failures": 0,
            "average_context_chars": 200,
        },
        "random": {
            "total_tokens": 80,
            "average_latency_ms": 60,
            "failures": 1,
            "average_context_chars": 150,
        },
    }
    if with_groq:
        metrics["groq"] = {
            "total_tokens": 120,
            "average_latency_ms": 40,
            "failures": 0,
            "average_context_chars": 250,
            "provider": "groq",
            "model": "mixtral-8x7b",
        }
    comparison = ExperimentComparison.objects.create(
        name="comparison",
        seed=42,
        configuration={},
        metrics=metrics,
        analysis={},
    )
    suite.comparisons.add(comparison)
    return suite


class BenchmarkReporterTests(TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_load_persisted_suite(self):
        suite = _create_suite()
        reporter = BenchmarkReporter(suite)
        rows = reporter.rows()
        self.assertTrue(len(rows) > 0)

    def test_deterministic_ordering(self):
        suite = _create_suite()
        reporter = BenchmarkReporter(suite)
        rows = reporter.rows()
        scenario_order = [r["scenario"] for r in rows]
        self.assertEqual(scenario_order, sorted(scenario_order))
        for scenario in suite.scenarios.keys():
            runtimes = [r["runtime"] for r in rows if r["scenario"] == scenario]
            self.assertEqual(runtimes, sorted(runtimes))

    def test_csv_matches_json_rows(self):
        suite = _create_suite()
        reporter = BenchmarkReporter(suite)
        json_path = self.tmp_dir / "report.json"
        csv_path = self.tmp_dir / "report.csv"
        reporter.export_json(json_path)
        reporter.export_csv(csv_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        json_rows = data["rows"]
        with open(csv_path, "r", encoding="utf-8") as f:
            header = f.readline().strip().split(",")
            csv_rows = [dict(zip(header, line.strip().split(","))) for line in f]
        for jr, cr in zip(json_rows, csv_rows):
            for key, val in jr.items():
                self.assertIn(key, cr)
                self.assertEqual(str(val), cr[key])

    def test_chart_generation(self):
        suite = _create_suite()
        reporter = BenchmarkReporter(suite)
        reporter.export_charts(self.tmp_dir)
        expected = [
            "wealth.png",
            "trade_volume.png",
            "communication.png",
            "llm_latency.png",
            "llm_tokens.png",
        ]
        for fname in expected:
            self.assertTrue((self.tmp_dir / fname).exists(), f"{fname} not generated")

    def test_groq_absent_behavior(self):
        suite = _create_suite(with_groq=False)
        reporter = BenchmarkReporter(suite)
        rows = reporter.rows()
        findings = reporter.findings(rows)
        messages = [f["text"] for f in findings if f["kind"] == "measured"]
        self.assertIn("No Groq runtime data present in this suite.", messages)

    def test_groq_present_behavior(self):
        suite = _create_suite(with_groq=True)
        reporter = BenchmarkReporter(suite)
        rows = reporter.rows()
        findings = reporter.findings(rows)
        groq_finding = None
        for f in findings:
            if f["kind"] == "measured" and "groq" in f["text"].lower():
                groq_finding = f
                break
        self.assertIsNotNone(groq_finding)
        self.assertIn("mixtral-8x7b", groq_finding["text"].lower())

    def test_reporter_never_calls_runners(self):
        with mock.patch("experiments.runner.ExperimentRunner") as mock_runner, \
             mock.patch("experiments.comparison.ExperimentComparisonRunner") as mock_comp_runner:
            suite = _create_suite()
            BenchmarkReporter(suite)
            mock_runner.assert_not_called()
            mock_comp_runner.assert_not_called()
            reporter = BenchmarkReporter(suite)
            rows = reporter.rows()
            reporter.export_json(self.tmp_dir / "dummy.json")
            reporter.export_csv(self.tmp_dir / "dummy.csv")
            reporter.export_charts(self.tmp_dir)
            mock_runner.assert_not_called()
            mock_comp_runner.assert_not_called()
