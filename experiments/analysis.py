class ExperimentComparisonAnalyzer:

    def __init__(self, comparison):
        self.comparison = comparison
        self.metrics = comparison.metrics

    def analyze(self):
        wealth = {
            label: data.get("economic", {}).get(
                "total_wealth",
                0,
            )
            for label, data in self.metrics.items()
        }
        winner = max(wealth, key=wealth.get) if wealth else None

        return {
            "winner_by_total_wealth": winner,
            "wealth_differences": self._metric_differences(
                "economic",
                "total_wealth",
            ),
            "resource_differences": self._metric_differences(
                "economic",
                "resource_units_total",
            ),
            "communication_differences": self._metric_differences(
                "social",
                "message_count",
            ),
            "cooperation_differences": self._metric_differences(
                "social",
                "cooperation_rate",
            ),
            "action_diversity_differences": self._metric_differences(
                "behavioral",
                "action_diversity",
            ),
            "entropy_differences": self._metric_differences(
                "behavioral",
                "decision_entropy",
            ),
            "trade_differences": self._metric_differences(
                "economic",
                "trade_volume",
            ),
            "llm": self._llm_summary(),
            "pairwise_deltas": self._pairwise_deltas(),
            "findings": self._findings(wealth),
        }

    def _metric_differences(self, section, key):
        if key == "resource_units_total":
            return {
                label: sum(
                    data.get(section, {})
                    .get("resource_units", {})
                    .values()
                )
                for label, data in self.metrics.items()
            }

        return {
            label: data.get(section, {}).get(key, 0)
            for label, data in self.metrics.items()
        }

    def _pairwise_deltas(self):
        pairs = (
            ("groq", "rule"),
            ("groq", "random"),
            ("rule", "random"),
        )
        sections = ("economic", "social", "behavioral")
        result = {}

        for left, right in pairs:
            if left not in self.metrics or right not in self.metrics:
                continue

            pair = {}
            for section in sections:
                left_data = self.metrics[left].get(section, {})
                right_data = self.metrics[right].get(section, {})
                pair[section] = {
                    key: value - right_data[key]
                    for key, value in left_data.items()
                    if isinstance(value, (int, float))
                    and isinstance(right_data.get(key), (int, float))
                }
            result[f"{left}_minus_{right}"] = pair

        return result

    def _llm_summary(self):
        return {
            label: data.get("llm", {})
            for label, data in self.metrics.items()
            if data.get("llm", {}).get("trace_count", 0)
        }

    @staticmethod
    def _findings(wealth):
        if not wealth:
            return []

        winner = max(wealth, key=wealth.get)
        return [
            f"{winner} had the highest total wealth at {wealth[winner]}.",
            "Metrics are observational and do not alter simulation state.",
        ]