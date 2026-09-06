import json
from dataclasses import dataclass
from typing import Any

from agents.retrieval import MemoryRetriever
from django.db.models import Q

from simulation.models import Message, Trade


MAX_MESSAGES = 10
MAX_MEMORIES = 10
MAX_TRADE_HISTORY = 10
MAX_OTHER_AGENTS = 10
MAX_MEMORY_CONTENT_CHARS = 500


@dataclass
class AgentObservation:
	tick: int
	self_state: dict[str, Any]
	world_state: dict[str, Any]
	other_agents: list[dict[str, Any]]
	memories: list[dict[str, Any]]
	messages: list[dict[str, Any]]
	pending_trades: list[dict[str, Any]]
	trade_history: list[dict[str, Any]]
	memory_ids: list[int]
	available_actions: list[str]

	def to_dict(self):
		return {
			"tick": self.tick,
			"self": self.self_state,
			"world": self.world_state,
			"other_agents": self.other_agents,
			"memories": self.memories,
			"messages": self.messages,
			"pending_trades": self.pending_trades,
			"trade_history": self.trade_history,
			"memory_ids": self.memory_ids,
			"available_actions": self.available_actions,
		}

	def to_llm_dict(self):
		return {
			"tick": self.tick,
			"self": self.self_state,
			"world": self.world_state,
			"other_agents": self.other_agents[:MAX_OTHER_AGENTS],
			"memories": [
				self._compact_memory(memory)
				for memory in self.memories[:MAX_MEMORIES]
			],
			"messages": self.messages[:MAX_MESSAGES],
			"pending_trades": self.pending_trades,
			"trade_history": self.trade_history[:MAX_TRADE_HISTORY],
			"memory_ids": self.memory_ids[:MAX_MEMORIES],
			"available_actions": self.available_actions,
		}

	@staticmethod
	def _compact_memory(memory):
		content = memory.get("content", {})

		if memory.get("type") == "observation" and isinstance(
			content,
			dict,
		):
			content = {
				"tick": content.get("tick"),
				"self": content.get("self", {}),
				"world": content.get("world", {}),
				"message_count": len(content.get("messages", [])),
				"pending_trade_count": len(
					content.get("pending_trades", [])
				),
			}

		serialized_content = json.dumps(
			content,
			sort_keys=True,
			separators=(",", ":"),
		)

		if len(serialized_content) > MAX_MEMORY_CONTENT_CHARS:
			content = {
				"summary": serialized_content[
					:MAX_MEMORY_CONTENT_CHARS
				]
			}

		return {
			"type": memory.get("type"),
			"content": content,
			"importance": memory.get("importance"),
			"tick": memory.get("tick"),
		}


class ObservationBuilder:

	def __init__(self, world, memory_policy=None):
		self.world = world
		self.memory_policy = {
			"memory_enabled": True,
			"memory_top_k": MAX_MEMORIES,
			"memory_decay": 0.95,
		}
		self.memory_policy.update(memory_policy or {})

	def build(self, agent) -> AgentObservation:

		other_agents = [
			{
				"id": other.id,
				"name": other.name,
				"role": other.role,
				"wallet": other.wallet,
				"inventory": other.inventory,
			}
			for other in self.world.agents.exclude(id=agent.id)
		]

		resources = [
			{
				"name": resource.name,
				"price": resource.price,
				"quantity": resource.quantity,
			}
			for resource in self.world.resources.all()
		]

		recent_messages = Message.objects.filter(
			Q(sender=agent) | Q(recipient=agent)
		).order_by(
			"-created_at"
		)[:MAX_MESSAGES]

		message_data = [
			{
				"sender_id": message.sender_id,
				"sender": message.sender.name,
				"content": message.content,
				"tick": message.tick,
				"conversation_id": message.conversation_id,
				"intent": message.intent,
			}
			for message in recent_messages
		]

		pending_trade_rows = Trade.objects.filter(
			recipient=agent,
			status="proposed",
		).order_by(
			"-created_at"
		)

		pending_trades = [
			{
				"trade_id": trade.id,
				"conversation_id": trade.conversation.conversation_id,
				"proposer_id": trade.proposer_id,
				"proposer": trade.proposer.name,
				"recipient_id": trade.recipient_id,
				"recipient": trade.recipient.name,
				"offer": trade.offer,
				"status": trade.status,
			}
			for trade in pending_trade_rows
		]

		recent_trades = Trade.objects.filter(
			Q(proposer=agent) | Q(recipient=agent)
		).order_by(
			"-created_at"
		)[:MAX_TRADE_HISTORY]

		trade_data = [
			{
				"trade_id": trade.id,
				"conversation_id": trade.conversation.conversation_id,
				"proposer_id": trade.proposer_id,
				"proposer": trade.proposer.name,
				"recipient_id": trade.recipient_id,
				"recipient": trade.recipient.name,
				"offer": trade.offer,
				"status": trade.status,
			}
			for trade in recent_trades
		]

		memory_ids_context = [
			message["sender_id"]
			for message in message_data
		]
		conversation_ids = [
			message["conversation_id"]
			for message in message_data
			if message["conversation_id"]
		]
		resource_names = [
			resource["name"]
			for resource in resources
		]
		memories = MemoryRetriever(
			agent,
			enabled=self.memory_policy["memory_enabled"],
			top_k=self.memory_policy["memory_top_k"],
			decay=self.memory_policy["memory_decay"],
		).retrieve(
			tick=self.world.current_tick,
			related_agent_ids=memory_ids_context,
			conversation_ids=conversation_ids,
			resources=resource_names,
		)

		memory_data = [
			{
				"id": memory.id,
				"type": memory.memory_type,
				"content": memory.content,
				"importance": memory.importance,
				"tick": memory.tick,
				"related_agent": (
					memory.related_agent.name
					if memory.related_agent
					else None
				),
			}
			for memory in memories
		]

		return AgentObservation(
			tick=self.world.current_tick,
			self_state={
				"id": agent.id,
				"name": agent.name,
				"role": agent.role,
				"wallet": agent.wallet,
				"inventory": agent.inventory,
				"goals": agent.goals,
				"personality": agent.personality,
			},
			world_state={
				"name": self.world.name,
				"tick": self.world.current_tick,
				"resources": resources,
			},
			other_agents=other_agents,
			memories=memory_data,
			messages=message_data,
			pending_trades=pending_trades,
			trade_history=trade_data,
			memory_ids=[memory.id for memory in memories],
			available_actions=[
				"buy",
				"sell",
				"communicate",
				"propose_trade",
				"accept_trade",
				"reject_trade",
				"wait",
			],
		)
