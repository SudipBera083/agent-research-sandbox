from agents.memory import MemoryManager

from .models import Message


class CommunicationManager:

    def __init__(self, world):
        self.world = world

    def send(
        self,
        sender,
        recipient,
        content,
        tick,
        message_type="direct",
        metadata=None,
    ):
        if metadata is None:
            metadata = {}

        if sender.id == recipient.id:
            raise ValueError(
                "An agent cannot send a message to itself."
            )

        message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            content=content,
            message_type=message_type,
            tick=tick,
            metadata=metadata,
        )

        MemoryManager(recipient).remember(
            "message_received",
            {
                "sender_id": sender.id,
                "sender_name": sender.name,
                "message": content,
                "message_type": message_type,
            },
            tick=tick,
            importance=3,
        )

        MemoryManager(sender).remember(
            "message_sent",
            {
                "recipient_id": recipient.id,
                "recipient_name": recipient.name,
                "message": content,
                "message_type": message_type,
            },
            tick=tick,
            importance=2,
        )

        return message

    def received(self, agent, limit=20):
        return list(
            Message.objects.filter(
                recipient=agent
            ).order_by("-tick", "-created_at")[:limit]
        )
