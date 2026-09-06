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