import json

from django.urls import reverse
from django.test import TestCase, Client

from experiments.models import Simulation, SimulationAgent, ActivityEvent
from experiments.activity import EventPublisher, EventTypes
from experiments.simulation_api import _sse_event_stream


class SimulationStreamTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.sim = Simulation.objects.create(name="stream-test-sim")
        self.agent = SimulationAgent.objects.create(
            simulation=self.sim,
            name="agent-1",
        )

    def tearDown(self):
        EventPublisher._subscribers.clear()

    def _parse_sse(self, chunks):
        events = []
        for chunk in chunks:
            event = {}
            for line in chunk.split("\n"):
                line = line.strip()
                if line.startswith("event:"):
                    event["event_type"] = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    try:
                        event["data"] = json.loads(data_str)
                    except json.JSONDecodeError:
                        event["data"] = data_str
            if event:
                events.append(event)
        return events

    def test_stream_delivers_historical_events(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        gen = _sse_event_stream(self.sim.id, after_sequence=0, max_messages=100)
        chunks = []
        try:
            for chunk in gen:
                chunks.append(chunk)
                if len(chunks) >= 20:
                    break
        finally:
            gen.close()

        events = self._parse_sse(chunks)
        event_types = [e["event_type"] for e in events]
        self.assertIn("simulation.started", event_types)
        self.assertIn("world.tick", event_types)

    def test_stream_filters_by_after_sequence(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        latest = ActivityEvent.objects.filter(simulation=self.sim).order_by("-sequence").first()
        self.assertIsNotNone(latest)

        gen = _sse_event_stream(
            self.sim.id, after_sequence=latest.sequence, max_messages=100
        )
        chunks = []
        try:
            for chunk in gen:
                chunks.append(chunk)
                if len(chunks) >= 5:
                    break
        finally:
            gen.close()

        events = self._parse_sse(chunks)
        for e in events:
            self.assertGreater(
                e["data"]["sequence"], latest.sequence,
                "Event sequence must be greater than after_sequence",
            )

    def test_stream_404_for_missing_simulation(self):
        url = reverse("simulation_stream", args=[99999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_invalid_start_returns_400(self):
        sim = Simulation.objects.create(name="completed-sim", status="completed")
        url = reverse("simulation_start", args=[sim.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "invalid_transition")

    def test_invalid_pause_returns_400(self):
        sim = Simulation.objects.create(name="paused-sim", status="paused")
        url = reverse("simulation_pause", args=[sim.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "invalid_transition")

    def test_invalid_step_returns_400(self):
        sim = Simulation.objects.create(name="error-sim", status="error")
        url = reverse("simulation_step", args=[sim.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"], "invalid_transition")

    def test_live_event_delivered_via_publisher(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))

        sub_queue = EventPublisher.subscribe(self.sim.id)
        try:
            self.client.post(reverse("simulation_step", args=[self.sim.id]))
            event_data = sub_queue.get(timeout=5)
            self.assertEqual(event_data["simulation_id"], self.sim.id)
            self.assertIn("event_type", event_data)
        finally:
            EventPublisher.unsubscribe(self.sim.id, sub_queue)

    def test_snapshot_includes_latest_sequence(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        url = reverse("simulation_snapshot", args=[self.sim.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("latest_sequence", data)
        self.assertGreater(data["latest_sequence"], 0)

    def test_step_auto_resumes_paused(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_pause", args=[self.sim.id]))
        self.sim.refresh_from_db()
        self.assertEqual(self.sim.status, "paused")

        resp = self.client.post(reverse("simulation_step", args=[self.sim.id]))
        self.assertEqual(resp.status_code, 200)
        self.sim.refresh_from_db()
        self.assertEqual(self.sim.status, "running")

    def test_step_emits_state_changed_events(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        state_events = ActivityEvent.objects.filter(
            simulation=self.sim,
            event_type=EventTypes.AGENT_STATE_CHANGED,
        )
        self.assertTrue(state_events.exists())
        self.assertEqual(state_events.count(), self.sim.agents.count())

    def test_events_endpoint_replay_after_sequence(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        for _ in range(3):
            self.client.post(reverse("simulation_step", args=[self.sim.id]))

        latest = ActivityEvent.objects.filter(simulation=self.sim).order_by("-sequence").first()
        self.assertIsNotNone(latest)

        url = reverse("simulation_events", args=[self.sim.id])
        resp = self.client.get(url, {"after_sequence": latest.sequence})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["count"], 0)

    def test_sequence_strictly_increasing(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        for _ in range(5):
            self.client.post(reverse("simulation_step", args=[self.sim.id]))

        sequences = list(
            ActivityEvent.objects.filter(simulation=self.sim)
            .order_by("sequence")
            .values_list("sequence", flat=True)
        )
        self.assertEqual(sequences, sorted(set(sequences)))
        self.assertEqual(len(sequences), len(set(sequences)))

    def test_snapshot_format_matches_spec(self):
        self.client.post(reverse("simulation_start", args=[self.sim.id]))
        self.client.post(reverse("simulation_step", args=[self.sim.id]))

        url = reverse("simulation_snapshot", args=[self.sim.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("simulation", data)
        self.assertIn("latest_sequence", data)
        self.assertIn("agents", data)
        self.assertIn("world", data)

        sim = data["simulation"]
        self.assertIn("id", sim)
        self.assertIn("status", sim)
        self.assertIn("current_tick", sim)
        self.assertIn("total_ticks", sim)
