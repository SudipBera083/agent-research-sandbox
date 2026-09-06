from .models import AgentMemory


class MemoryManager:

    def __init__(self, agent):
        self.agent = agent

    def remember(
        self,
        memory_type,
        content,
        tick,
        importance=1.0,
        experiment=None,
        source="simulation",
        related_agent=None,
    ):
        return AgentMemory.objects.create(
            agent=self.agent,
            experiment=experiment,
            related_agent=related_agent,
            source=source,
            memory_type=memory_type,
            content=content,
            importance=importance,
            tick=tick,
        )

    def recent(self, limit=10):

        return list(
            self.agent.memories.all()[:limit]
        )

    def important(self, limit=10):

        return list(
            self.agent.memories
            .filter(importance__gte=5)
            [:limit]
        )

    def clear(self):

        self.agent.memories.all().delete()