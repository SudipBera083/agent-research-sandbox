from typing import ClassVar

from django.db import models


class World(models.Model):
    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    current_tick = models.IntegerField(default=0)

    is_running = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Resource(models.Model):
    world = models.ForeignKey(
        World,
        on_delete=models.CASCADE,
        related_name="resources",
    )

    name = models.CharField(max_length=100)

    price = models.FloatField(default=10.0)

    quantity = models.IntegerField(default=0)

    def __str__(self):
        return self.name


class Message(models.Model):
    MESSAGE_TYPES: ClassVar = [
        ("direct", "Direct"),
        ("broadcast", "Broadcast"),
        ("system", "System"),
    ]

    sender = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )

    recipient = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="received_messages",
        null=True,
        blank=True,
    )

    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPES,
        default="direct",
    )

    content = models.TextField()

    tick = models.IntegerField()

    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        if self.recipient:
            return (
                f"{self.sender.name} -> "
                f"{self.recipient.name}: "
                f"{self.content[:40]}"
            )

        return (
            f"{self.sender.name} -> broadcast: "
            f"{self.content[:40]}"
        )