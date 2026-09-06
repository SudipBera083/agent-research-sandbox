import json

from .models import AgentMemory


class MemoryRetriever:

    def __init__(self, agent, enabled=True, top_k=10, decay=0.95):
        self.agent = agent
        self.enabled = enabled
        self.top_k = max(0, int(top_k))
        self.decay = float(decay)

    def retrieve(
        self,
        tick,
        related_agent_ids=None,
        conversation_ids=None,
        resources=None,
    ):
        if not self.enabled or self.top_k == 0:
            return []

        related_agent_ids = set(related_agent_ids or [])
        conversation_ids = set(conversation_ids or [])
        resources = set(resources or [])
        scored = []

        for memory in AgentMemory.objects.filter(
            agent=self.agent
        ).select_related("related_agent"):
            age = max(0, tick - memory.tick)
            score = float(memory.importance)
            score += self.decay ** age
            score += 0.25

            if memory.related_agent_id in related_agent_ids:
                score += 0.5

            content_text = json.dumps(
                memory.content,
                sort_keys=True,
                default=str,
            )

            if any(resource in content_text for resource in resources):
                score += 0.25

            if any(
                conversation_id in content_text
                for conversation_id in conversation_ids
            ):
                score += 0.5

            scored.append((score, memory))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].tick,
                item[1].id,
            ),
            reverse=True,
        )

        return [
            memory
            for _, memory in scored[:self.top_k]
        ]
