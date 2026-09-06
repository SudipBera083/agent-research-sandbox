from django.db import models

class Agent(models.Model):
    name = models.CharField(max_length=100)

    role = models.CharField(
        max_length=50,
        default="general",
    )

    system_prompt = models.TextField()

    goals = models.JSONField(default=list)

    personality = models.JSONField(default=dict)

    inventory = models.JSONField(default=dict)

    wallet = models.FloatField(default=100.0)

    energy = models.FloatField(default=100.0)

    is_active = models.BooleanField(default=True)

    world = models.ForeignKey(
        "simulation.World",
        on_delete=models.CASCADE,
        related_name="agents",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AgentMemory(models.Model):
    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="memories",
    )

    memory_type = models.CharField(
        max_length=50,
        default="observation",
    )

    content = models.JSONField(default=dict)

    importance = models.IntegerField(default=1)

    tick = models.IntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-tick", "-created_at"]

    def __str__(self):
        return f"{self.agent.name} - {self.memory_type}"