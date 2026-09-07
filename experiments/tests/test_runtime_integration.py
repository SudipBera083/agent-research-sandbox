from unittest.mock import patch, MagicMock

from django.urls import reverse
from django.test import TestCase, Client

from experiments.models import Simulation, SimulationAgent, ActivityEvent
from experiments.activity import EventPublisher, EventTypes, SimulationController, AgentAdapter
from simulation.actions import Action, ActionTypes
from agents.providers.base import LLMResponse


class RuntimeIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.sim = Simulation.objects.create(name="runtime-test-sim")
        self.agent = SimulationAgent.objects.create(
            simulation=self.sim,
            name="rule-agent",
            role="wealth",
            runtime="rule",
            provider="deterministic",
            model="rule",
        )

    def tearDown(self):
        EventPublisher._subscribers.clear()

    def test_rule_agent_produces_decision_with_runtime_metadata(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[self.sim.id]))
        self.assertEqual(resp.status_code, 200)

        decision = ActivityEvent.objects.filter(
            simulation=self.sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIsNotNone(decision)
        self.assertEqual(decision.data["runtime"], "rule")
        self.assertEqual(decision.data["action"], "buy")

    def test_random_agent_produces_valid_action(self):
        sim = Simulation.objects.create(name="random-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="random-agent",
            runtime="random",
            provider="deterministic",
            model="random",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[sim.id]))
        self.assertEqual(resp.status_code, 200)

        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIsNotNone(decision)
        self.assertEqual(decision.data["runtime"], "random")
        action = decision.data["action"]
        self.assertIn(
            action,
            [ActionTypes.WAIT, ActionTypes.BUY, ActionTypes.ACCEPT_TRADE],
        )

    def test_llm_deterministic_agent_produces_decision(self):
        sim = Simulation.objects.create(name="llm-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="llm-agent",
            runtime="llm",
            provider="deterministic",
            model="deterministic-v1",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[sim.id]))
        self.assertEqual(resp.status_code, 200)

        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIsNotNone(decision)
        self.assertEqual(decision.data["runtime"], "llm")
        self.assertEqual(decision.data["provider"], "deterministic")
        self.assertEqual(decision.data["model"], "deterministic-v1")
        self.assertIn(
            decision.data["action"],
            [ActionTypes.WAIT, ActionTypes.BUY, ActionTypes.COMMUNICATE],
        )

    def test_provider_failure_captured_safely(self):
        sim = Simulation.objects.create(name="fail-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="fail-agent",
            runtime="llm",
            provider="deterministic",
            model="deterministic-v1",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))

        # Patch the runtime's decide to raise an exception
        from agents.llm_runtime import LLMAgentRuntime

        original_decide = LLMAgentRuntime.decide

        def failing_decide(self, agent, observation):
            raise ConnectionError("Simulated provider connection failure")

        with patch.object(LLMAgentRuntime, "decide", failing_decide):
            resp = self.client.post(reverse("simulation_step", args=[sim.id]))
            self.assertEqual(resp.status_code, 200)

        # On failure, the controller should record an error trace and fall back to wait
        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIsNotNone(decision)
        self.assertEqual(decision.data["action"], "wait")
        self.assertEqual(decision.data["trace"]["validation_result"], "error")
        self.assertIn("connection failure", decision.data["trace"]["error"])

        LLMAgentRuntime.decide = original_decide

    def test_buy_action_updates_agent_state(self):
        sim = Simulation.objects.create(name="buy-test-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="buyer",
            role="wealth",
            runtime="rule",
            provider="deterministic",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        self.client.post(reverse("simulation_step", args=[sim.id]))

        state_events = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_STATE_CHANGED,
        )
        state = state_events.first()
        self.assertIsNotNone(state)
        self.assertIn("wealth", state.data)

    def test_rule_agent_wealth_decision_buys_food(self):
        sim = Simulation.objects.create(name="wealth-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="wealthy-agent",
            role="wealth",
            runtime="rule",
            provider="deterministic",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[sim.id]))
        self.assertEqual(resp.status_code, 200)

        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertEqual(decision.data["action"], "buy")
        self.assertEqual(decision.data["parameters"]["resource"], "food")

    def test_multiple_agents_processed_deterministically_by_id(self):
        sim = Simulation.objects.create(name="multi-sim")
        SimulationAgent.objects.create(
            simulation=sim, name="agent-b", runtime="rule", provider="deterministic"
        )
        SimulationAgent.objects.create(
            simulation=sim, name="agent-a", runtime="rule", provider="deterministic"
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[sim.id]))
        self.assertEqual(resp.status_code, 200)

        decisions = list(
            ActivityEvent.objects.filter(
                simulation=sim, event_type=EventTypes.AGENT_DECISION
            ).order_by("sequence")
        )
        self.assertEqual(len(decisions), 2)

        # Agent with lower id should be processed first
        first_agent_id = decisions[0].agent_id
        second_agent_id = decisions[1].agent_id
        self.assertLess(first_agent_id, second_agent_id)

    def test_llm_agent_records_provider_and_model(self):
        sim = Simulation.objects.create(name="llm-meta-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="llm-agent",
            runtime="llm",
            provider="deterministic",
            model="deterministic-v1",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        self.client.post(reverse("simulation_step", args=[sim.id]))

        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertEqual(decision.data["provider"], "deterministic")
        self.assertEqual(decision.data["model"], "deterministic-v1")
        self.assertIn("trace", decision.data)

    def test_deterministic_agent_marked_simulation_generated(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        for event_type in [
            EventTypes.AGENT_OBSERVATION,
            EventTypes.AGENT_DECISION,
            EventTypes.AGENT_ACTION,
        ]:
            event = ActivityEvent.objects.filter(
                simulation=self.sim, event_type=event_type
            ).first()
            self.assertIsNotNone(event)
            self.assertEqual(event.data.get("source"), "simulation_generated")

    def test_no_api_keys_in_activity_events(self):
        sim = Simulation.objects.create(name="secret-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="secret-agent",
            runtime="llm",
            provider="deterministic",
            model="deterministic-v1",
        )
        sim.configuration = {"api_key": "sk-secret-123"}
        sim.save()

        self.client.post(reverse("simulation_start", args=[sim.id]))
        self.client.post(reverse("simulation_step", args=[sim.id]))

        events = ActivityEvent.objects.filter(simulation=sim)
        for event in events:
            event_data_str = str(event.data)
            self.assertNotIn("sk-secret-123", event_data_str)
            self.assertNotIn("api_key", event.data)

    def test_cooperative_runtime_produces_communicate_or_wait(self):
        sim = Simulation.objects.create(name="coop-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="coop-agent",
            role="cooperative",
            runtime="rule",
            provider="deterministic",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[sim.id]))
        self.assertEqual(resp.status_code, 200)

        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIn(
            decision.data["action"],
            [ActionTypes.COMMUNICATE, ActionTypes.WAIT],
        )

    def test_survival_runtime_produces_buy_or_wait(self):
        sim = Simulation.objects.create(name="survival-sim")
        SimulationAgent.objects.create(
            simulation=sim,
            name="survival-agent",
            role="survival",
            runtime="rule",
            provider="deterministic",
        )
        self.client.post(reverse("simulation_start", args=[sim.id]))
        resp = self.client.post(reverse("simulation_step", args=[sim.id]))
        self.assertEqual(resp.status_code, 200)

        decision = ActivityEvent.objects.filter(
            simulation=sim,
            event_type=EventTypes.AGENT_DECISION,
        ).first()
        self.assertIn(
            decision.data["action"],
            [ActionTypes.BUY, ActionTypes.WAIT],
        )

    def test_step_emits_full_event_chain(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        events = list(
            ActivityEvent.objects.filter(simulation=self.sim)
            .exclude(event_type=EventTypes.SIMULATION_STARTED)
            .order_by("sequence")
        )
        event_types = [e.event_type for e in events]

        # Verify the deterministic tick pattern
        self.assertIn(EventTypes.WORLD_TICK, event_types)
        self.assertIn(EventTypes.AGENT_OBSERVATION, event_types)
        self.assertIn(EventTypes.AGENT_DECISION, event_types)
        self.assertIn(EventTypes.AGENT_ACTION, event_types)
        self.assertIn(EventTypes.AGENT_STATE_CHANGED, event_types)

        # world.tick should come before agent events
        world_tick_idx = event_types.index(EventTypes.WORLD_TICK)
        obs_idx = event_types.index(EventTypes.AGENT_OBSERVATION)
        self.assertLess(world_tick_idx, obs_idx)

    def test_agent_adapter_maps_fields_correctly(self):
        adapter = AgentAdapter(self.agent)
        self.assertEqual(adapter.id, self.agent.id)
        self.assertEqual(adapter.name, self.agent.name)
        self.assertEqual(adapter.role, self.agent.role)
        self.assertEqual(adapter.runtime_type, self.agent.runtime)
        self.assertEqual(adapter.provider, self.agent.provider)
        self.assertEqual(adapter.model, self.agent.model)
