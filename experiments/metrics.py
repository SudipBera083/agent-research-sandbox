import math
from collections import Counter, defaultdict


class ExperimentMetrics:

    def __init__(self, experiment, world, agents):
        self.experiment = experiment
        self.world = world
        self.agents = list(agents)
        self.traces = list(
            experiment.decision_traces.select_related("agent").order_by(
                "tick",
                "id",
            )
        )
        self.messages = list(
            message
            for agent in self.agents
            for message in agent.sent_messages.all()
            if message.sender_id in {item.id for item in self.agents}
        )
        self.trades = list(
            trade
            for agent in self.agents
            for trade in agent.proposed_trades.all()
            if trade.proposer_id in {item.id for item in self.agents}
        )
        self.conversations = {
            message.conversation_id
            for message in self.messages
            if message.conversation_id
        }

    def calculate(self):
        return {
            "economic": self.economic(),
            "social": self.social(),
            "behavioral": self.behavioral(),
            "llm": self.llm(),
            "interaction_graph": self.interaction_graph(),
        }

    def economic(self):
        final_agents = [
            self._refresh_agent(agent)
            for agent in self.agents
        ]
        wealth = {
            agent.name: agent.wallet
            for agent in final_agents
        }
        for agent in final_agents:
            wealth[agent.name] = agent.wallet + sum(
                quantity * self._resource_price(resource_name)
                for resource_name, quantity in agent.inventory.items()
            )

        values = list(wealth.values())
        total = sum(values)
        mean = total / len(values) if values else 0.0
        variance = (
            sum((value - mean) ** 2 for value in values) / len(values)
            if values
            else 0.0
        )

        completed_trades = [
            trade for trade in self.trades if trade.status == "completed"
        ]
        failed_trades = [
            trade for trade in self.trades if trade.status == "failed"
        ]

        return {
            "agent_count": len(final_agents),
            "total_wealth": total,
            "wealth_by_agent": wealth,
            "wealth_inequality_stddev": math.sqrt(variance),
            "resource_distribution": {
                agent.name: agent.inventory
                for agent in final_agents
            },
            "trade_volume": len(completed_trades),
            "trade_value": sum(
                self._money_quantity(trade.offer.get("receive", {}))
                for trade in completed_trades
            ),
            "failed_trades": len(failed_trades),
        }

    def social(self):
        accepted = sum(
            1 for trade in self.trades if trade.status == "completed"
        )
        rejected = sum(
            1 for trade in self.trades if trade.status == "rejected"
        )
        interactions = Counter(
            (message.sender.name, message.recipient.name)
            for message in self.messages
            if message.recipient_id is not None
        )

        return {
            "message_count": len(self.messages),
            "conversation_count": len(self.conversations),
            "cooperation_rate": (
                accepted / len(self.trades)
                if self.trades
                else 0.0
            ),
            "rejection_rate": (
                rejected / len(self.trades)
                if self.trades
                else 0.0
            ),
            "interaction_count": sum(interactions.values()),
        }

    def behavioral(self):
        actions_by_agent = defaultdict(list)
        runtimes = defaultdict(set)

        for trace in self.traces:
            action_type = trace.action.get("type", "unknown")
            actions_by_agent[trace.agent.name].append(action_type)
            runtimes[trace.agent.name].add(
                trace.decision.get("runtime", "unknown")
            )

        action_counts = Counter(
            action
            for actions in actions_by_agent.values()
            for action in actions
        )
        total_actions = sum(action_counts.values())
        entropy = 0.0
        if total_actions:
            entropy = -sum(
                (count / total_actions)
                * math.log2(count / total_actions)
                for count in action_counts.values()
            )

        repeated = {
            agent: sum(
                current == previous
                for previous, current in zip(actions, actions[1:])
            )
            for agent, actions in actions_by_agent.items()
        }

        return {
            "action_diversity": len(action_counts),
            "action_counts": dict(action_counts),
            "repeated_actions": repeated,
            "runtime_changes": {
                agent: len(types) - 1
                for agent, types in runtimes.items()
            },
            "decision_entropy": entropy,
        }

    def llm(self):
        llm_traces = [
            trace
            for trace in self.traces
            if trace.decision.get("runtime") == "llm"
        ]
        providers = Counter(
            trace.decision.get("provider", "unknown")
            for trace in llm_traces
        )
        models = Counter(
            trace.decision.get("model", "unknown")
            for trace in llm_traces
        )
        failures = sum(
            trace.decision.get("validation_result") != "accepted"
            for trace in llm_traces
        )
        usage = [
            trace.decision.get("token_usage", {})
            for trace in llm_traces
        ]

        return {
            "trace_count": len(llm_traces),
            "providers": dict(providers),
            "models": dict(models),
            "failures": failures,
            "average_latency_ms": self._average(
                trace.decision.get("latency_ms", 0)
                for trace in llm_traces
            ),
            "total_tokens": sum(
                item.get("total_tokens", 0)
                for item in usage
            ),
            "average_context_chars": self._average(
                trace.decision.get("context_stats", {}).get(
                    "estimated_chars",
                    0,
                )
                for trace in llm_traces
            ),
        }

    def interaction_graph(self):
        edges = Counter(
            f"{message.sender.name}->{message.recipient.name}"
            for message in self.messages
            if message.recipient_id is not None
        )

        return {
            "nodes": [agent.name for agent in self.agents],
            "edges": dict(edges),
        }

    def _resource_price(self, resource_name):
        resource = self.world.resources.filter(
            name=resource_name
        ).first()
        return resource.price if resource else 0.0

    @staticmethod
    def _money_quantity(details):
        return (
            details.get("quantity", 0)
            if details.get("resource") == "money"
            else 0
        )

    @staticmethod
    def _average(values):
        values = list(values)
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _refresh_agent(agent):
        agent.refresh_from_db()
        return agent
