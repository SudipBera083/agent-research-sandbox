from django.db import models

class Agent(models.Model):
    name = models.CharField(max_length=100)

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