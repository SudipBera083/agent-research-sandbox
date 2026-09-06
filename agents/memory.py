from .models import AgentMemory


class MemoryManager:

    def __init__(self, agent):
        self.agent = agent

    def remember(
        self,
        memory_type,
        content,
        tick,
        importance=1,
    ):
        return AgentMemory.objects.create(
            agent=self.agent,
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