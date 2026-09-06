from dataclasses import dataclass
from typing import Any

from agents.memory import MemoryManager
from django.db.models import Q

from simulation.models import Message, Trade


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
			"available_actions": self.available_actions,
		}


class ObservationBuilder:

	def __init__(self, world):
		self.world = world

	def build(self, agent) -> AgentObservation:

		memories = MemoryManager(agent).recent(10)

		memory_data = [
			{
				"type": memory.memory_type,
				"content": memory.content,
				"importance": memory.importance,
				"tick": memory.tick,
			}
			for memory in memories
		]

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
		)[:10]

		message_data = [
			{
				"sender": message.sender.name,
				"content": message.content,
				"tick": message.tick,
				"conversation_id": message.conversation_id,
				"intent": message.intent,
			}
			for message in recent_messages
		]

		recent_trades = Trade.objects.filter(
			Q(proposer=agent) | Q(recipient=agent)
		).order_by(
			"-created_at"
		)[:10]

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

		pending_trades = [
			trade
			for trade in trade_data
			if (
				trade["status"] == "proposed"
				and trade["recipient_id"] == agent.id
			)
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
