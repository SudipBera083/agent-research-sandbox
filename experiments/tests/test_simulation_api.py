import json
from django.urls import reverse
from django.test import TestCase, Client
from ..models import Simulation, SimulationAgent, ActivityEvent

class SimulationAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.sim = Simulation.objects.create(name='test-sim')
        self.agent = SimulationAgent.objects.create(simulation=self.sim, name='agent-1')

    def test_snapshot_endpoint(self):
        url = reverse('simulation_snapshot', args=[self.sim.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('agents', data)
        self.assertEqual(data['simulation']['id'], self.sim.id)

    def test_start_endpoint_creates_event(self):
        url = reverse('simulation_start', args=[self.sim.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        # Verify a `simulation.started` event exists
        self.assertTrue(ActivityEvent.objects.filter(simulation=self.sim, event_type='simulation.started').exists())

    def test_step_advances_tick_and_creates_events(self):
        # Start first
        self.client.post(reverse('simulation_start', args=[self.sim.id]))
        url = reverse('simulation_step', args=[self.sim.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        # Check a world.tick event
        self.assertTrue(ActivityEvent.objects.filter(simulation=self.sim, event_type='world.tick').exists())

    def test_events_endpoint_pagination(self):
        # Generate a few events via start/step
        self.client.post(reverse('simulation_start', args=[self.sim.id]))
        for _ in range(3):
            self.client.post(reverse('simulation_step', args=[self.sim.id]))
        url = reverse('simulation_events', args=[self.sim.id]) + '?limit=2'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertLessEqual(len(payload['events']), 2)
        self.assertIn('latest_sequence', payload)
