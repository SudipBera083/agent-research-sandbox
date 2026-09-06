from agents.memory import MemoryManager

from .models import Conversation, Message


class CommunicationManager:

    def __init__(self, world, experiment=None, memory_enabled=True):
        self.world = world
        self.experiment = experiment
        self.memory_enabled = memory_enabled

    def get_or_create_conversation(
        self,
        sender,
        recipient,
        conversation_id,
        topic="general",
    ):
        conversation, created = Conversation.objects.get_or_create(
            conversation_id=conversation_id,
            defaults={
                "topic": topic,
            },
        )

        conversation.participants.add(
            sender,
            recipient,
        )

        return conversation

    def send(
        self,
        sender,
        recipient,
        content,
        tick,
        message_type="direct",
        conversation_id="",
        intent="information",
        metadata=None,
    ):
        if metadata is None:
            metadata = {}

        if sender.id == recipient.id:
            raise ValueError(
                "An agent cannot send a message to itself."
            )

        self.get_or_create_conversation(
            sender=sender,
            recipient=recipient,
            conversation_id=conversation_id,
        )

        message = Message.objects.create(
            sender=sender,
            recipient=recipient,
            content=content,
            message_type=message_type,
            conversation_id=conversation_id,
            intent=intent,
            tick=tick,
            metadata=metadata,
        )

        if self.memory_enabled:
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
                experiment=self.experiment,
                source="communication",
                related_agent=sender,
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
                experiment=self.experiment,
                source="communication",
                related_agent=recipient,
            )

        return message

    def conversation(self, conversation_id):
        return list(
            Message.objects.filter(
                conversation_id=conversation_id
            ).order_by(
                "tick",
                "created_at",
            )
        )

    def received(self, agent, limit=20):
        return list(
            Message.objects.filter(
                recipient=agent
            ).order_by("-tick", "-created_at")[:limit]
        )
