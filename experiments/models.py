import uuid

from django.db import models


class Experiment(models.Model):

	STATUS_CHOICES = [
		("created", "Created"),
		("running", "Running"),
		("completed", "Completed"),
		("failed", "Failed"),
	]

	name = models.CharField(max_length=200)

	experiment_id = models.UUIDField(
		default=uuid.uuid4,
		unique=True,
		editable=False,
	)

	description = models.TextField(
		blank=True,
		default="",
	)

	configuration = models.JSONField(
		default=dict,
	)

	seed = models.IntegerField(
		null=True,
		blank=True,
	)

	status = models.CharField(
		max_length=20,
		choices=STATUS_CHOICES,
		default="created",
	)

	current_tick = models.IntegerField(
		default=0,
	)

	total_ticks = models.IntegerField(
		default=10,
	)

	started_at = models.DateTimeField(
		null=True,
		blank=True,
	)

	completed_at = models.DateTimeField(
		null=True,
		blank=True,
	)

	created_at = models.DateTimeField(
		auto_now_add=True,
	)

	def __str__(self):
		return self.name


class ExperimentComparison(models.Model):

	name = models.CharField(max_length=200)

	seed = models.IntegerField()

	configuration = models.JSONField(default=dict)

	experiments = models.ManyToManyField(
		Experiment,
		related_name="comparisons",
	)

	metrics = models.JSONField(default=dict)

	analysis = models.JSONField(default=dict)

	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class BenchmarkSuite(models.Model):

	name = models.CharField(max_length=200)

	seed = models.IntegerField()

	scenarios = models.JSONField(default=dict)

	comparisons = models.ManyToManyField(
		ExperimentComparison,
		related_name="benchmark_suites",
	)

	analysis = models.JSONField(default=dict)

	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class ExperimentResult(models.Model):

	experiment = models.OneToOneField(
		Experiment,
		on_delete=models.CASCADE,
		related_name="result",
	)

	final_world_state = models.JSONField(
		default=dict,
	)

	final_agent_states = models.JSONField(
		default=list,
	)

	metrics = models.JSONField(
		default=dict,
	)

	created_at = models.DateTimeField(
		auto_now_add=True,
	)

	def __str__(self):
		return f"Result: {self.experiment.name}"


class DecisionTrace(models.Model):

	experiment = models.ForeignKey(
		Experiment,
		on_delete=models.CASCADE,
		related_name="decision_traces",
	)

	tick = models.IntegerField()

	agent = models.ForeignKey(
		"agents.Agent",
		on_delete=models.CASCADE,
		related_name="decision_traces",
	)

	observation = models.JSONField(default=dict)

	decision = models.JSONField(default=dict)

	action = models.JSONField(default=dict)

	result = models.JSONField(default=dict)

	created_at = models.DateTimeField(
		auto_now_add=True,
	)


import uuid

from django.db import models


class Simulation(models.Model):
	STATUS_CHOICES = [
		("created", "Created"),
		("running", "Running"),
		("paused", "Paused"),
		("completed", "Completed"),
		("error", "Error"),
	]

	# Public UUID for API references (idempotency key)
	operation_id = models.UUIDField(
		default=uuid.uuid4,
		editable=False,
		unique=True,
	)

	name = models.CharField(max_length=200)
	status = models.CharField(
		max_length=20,
		choices=STATUS_CHOICES,
		default="created",
	)
	current_tick = models.IntegerField(default=0)
	total_ticks = models.IntegerField(default=100)
	seed = models.IntegerField(default=42)
	configuration = models.JSONField(default=dict)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.name} ({self.status})"


class SimulationAgent(models.Model):
	simulation = models.ForeignKey(
		Simulation,
		on_delete=models.CASCADE,
		related_name="agents",
	)
	name = models.CharField(max_length=100)
	role = models.CharField(max_length=100, default="trader")
	runtime = models.CharField(max_length=50, default="rule")
	provider = models.CharField(max_length=50, default="deterministic")
	model = models.CharField(max_length=100, default="rule")
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.name} [{self.simulation.name}]"


class ActivityEvent(models.Model):
	simulation = models.ForeignKey(
		Simulation,
		on_delete=models.CASCADE,
		related_name="events",
	)
	agent = models.ForeignKey(
		SimulationAgent,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="events",
	)
	tick = models.IntegerField(db_index=True)
	event_type = models.CharField(max_length=64, db_index=True)
	sequence = models.BigIntegerField(db_index=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	data = models.JSONField(default=dict)

	class Meta:
		ordering = ["sequence"]
		constraints = [
			models.UniqueConstraint(
				fields=["simulation", "sequence"],
				name="unique_simulation_event_sequence",
			)
		]

	def __str__(self):
		return f"Sim {self.simulation_id} #{self.sequence}: {self.event_type} (tick {self.tick})"


class AgentState(models.Model):
	simulation = models.ForeignKey(
		Simulation,
		on_delete=models.CASCADE,
		related_name="agent_states",
	)
	agent = models.OneToOneField(
		SimulationAgent,
		on_delete=models.CASCADE,
		related_name="state",
	)
	wealth = models.FloatField(default=0.0)
	resources = models.JSONField(default=dict)
	health = models.FloatField(default=100.0)
	status = models.CharField(max_length=50, default="active")
	current_action = models.CharField(max_length=100, blank=True, default="")
	last_action = models.CharField(max_length=100, blank=True, default="")
	last_decision = models.JSONField(default=dict)
	last_observation_tick = models.IntegerField(default=0)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=["simulation", "agent"],
				name="unique_simulation_agent_state",
			)
		]

	def __str__(self):
		return f"State: {self.agent.name} (wealth: {self.wealth})"
