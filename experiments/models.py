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
