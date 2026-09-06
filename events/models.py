from django.db import models


class Event(models.Model):

    EVENT_TYPES = [
        ("observation", "Observation"),
        ("communication", "Communication"),
        ("action", "Action"),
        ("transaction", "Transaction"),
        ("state_change", "State Change"),
        ("system", "System"),
    ]

    world = models.ForeignKey(
        "simulation.World",
        on_delete=models.CASCADE,
        related_name="events",
    )

    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )

    tick = models.IntegerField()

    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES,
    )

    action = models.CharField(
        max_length=100,
        blank=True,
    )

    data = models.JSONField(default=dict)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.tick} - {self.event_type}"