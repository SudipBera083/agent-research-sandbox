# -*- coding: utf-8 -*-
"""Real-Time Agent Activity Tracking & Simulation Controller (Step 31A / Step 32).

Provides:
- Standardized ActivityEvent vocabulary.
- ActivityTracker: Authoritative database ledger for all agent observations,
  decisions, actions, communications, and state transitions with per-simulation
  monotonic sequence numbering.
- EventPublisher: Real-time broadcast and subscription broker.
- AgentAdapter: Bridges SimulationAgent to the agent runtime interface.
- SimulationController: State machine and tick stepping engine with real
  agent runtimes (rule, random, groq, xai).
"""

import logging

from collections import defaultdict
import copy
import queue
import threading
from typing import Any, Dict, List, Optional

from django.db import models, transaction

from simulation.actions import Action
from simulation.observation import AgentObservation
from agents.runtime import get_agent_runtime

from .models import ActivityEvent, AgentState, Simulation, SimulationAgent


logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Agent Adapter (bridges SimulationAgent to agent runtime interface)
# ----------------------------------------------------------------------

class AgentAdapter:
    """Adapts SimulationAgent to the interface expected by agent runtimes.

    The runtimes in agents/runtime.py expect objects with runtime_type,
    provider, model, role, name, and id attributes. SimulationAgent stores
    these as 'runtime', 'provider', 'model', 'role', 'name', and 'id'.
    """

    def __init__(self, simulation_agent: SimulationAgent):
        self.simulation_agent = simulation_agent

    @property
    def id(self):
        return self.simulation_agent.id

    @property
    def name(self):
        return self.simulation_agent.name

    @property
    def role(self):
        return self.simulation_agent.role

    @property
    def runtime_type(self):
        return self.simulation_agent.runtime

    @property
    def provider(self):
        return self.simulation_agent.provider

    @property
    def model(self):
        return self.simulation_agent.model


# ----------------------------------------------------------------------
# Standard Event Vocabulary
# ----------------------------------------------------------------------

class EventTypes:
    SIMULATION_CREATED = "simulation.created"
    SIMULATION_STARTED = "simulation.started"
    SIMULATION_PAUSED = "simulation.paused"
    SIMULATION_RESUMED = "simulation.resumed"
    SIMULATION_COMPLETED = "simulation.completed"
    SIMULATION_ERROR = "simulation.error"

    WORLD_TICK = "world.tick"

    AGENT_SPAWNED = "agent.spawned"
    AGENT_OBSERVATION = "agent.observation"
    AGENT_DECISION = "agent.decision"
    AGENT_ACTION = "agent.action"
    AGENT_STATE_CHANGED = "agent.state_changed"
    AGENT_RESOURCE_CHANGED = "agent.resource_changed"

    MESSAGE_CREATED = "message.created"

    TRADE_PROPOSED = "trade.proposed"
    TRADE_ACCEPTED = "trade.accepted"
    TRADE_REJECTED = "trade.rejected"
    TRADE_COMPLETED = "trade.completed"

    RESOURCE_CHANGED = "resource.changed"

    AGENT_DIED = "agent.died"
    AGENT_RECOVERED = "agent.recovered"


# ----------------------------------------------------------------------
# Event Publisher (Pub/Sub for streaming)
# ----------------------------------------------------------------------

class EventPublisher:
    """In-memory broadcast broker for real-time subscribers (SSE / WebSockets).

    Authoritative data always lives in the ActivityEvent table. This broker
    serves as a delivery optimization for active connections.
    """

    _subscribers: Dict[int, List[queue.Queue]] = defaultdict(list)
    _lock = threading.Lock()

    @classmethod
    def subscribe(cls, simulation_id: int) -> queue.Queue:
        q = queue.Queue(maxsize=500)
        with cls._lock:
            cls._subscribers[simulation_id].append(q)
        return q

    @classmethod
    def unsubscribe(cls, simulation_id: int, q: queue.Queue):
        with cls._lock:
            if simulation_id in cls._subscribers and q in cls._subscribers[simulation_id]:
                cls._subscribers[simulation_id].remove(q)
                if not cls._subscribers[simulation_id]:
                    del cls._subscribers[simulation_id]

    @classmethod
    def publish(cls, event_data: Dict[str, Any]):
        sim_id = event_data.get("simulation_id")
        if not sim_id:
            return
        with cls._lock:
            subscribers = list(cls._subscribers.get(sim_id, []))

        for q in subscribers:
            try:
                q.put_nowait(event_data)
            except queue.Full:
                pass


# ----------------------------------------------------------------------
# Activity Tracker (Authoritative Ledger)
# ----------------------------------------------------------------------

class ActivityTracker:
    """Records simulation activity events into the database with sequence numbers

    and automatically synchronizes live AgentState records.
    """

    SENSITIVE_KEYS = {
        "api_key",
        "groq_api_key",
        "openai_api_key",
        "xai_api_key",
        "authorization",
        "token",
        "secret",
        "password",
    }

    def __init__(self, simulation: Simulation):
        self.simulation = simulation

    @classmethod
    def sanitize_data(cls, data: Any) -> Any:
        """Strip credentials, API keys, and authorization headers from event data."""
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if k.lower() in cls.SENSITIVE_KEYS:
                    continue
                clean[k] = cls.sanitize_data(v)
            return clean
        elif isinstance(data, list):
            return [cls.sanitize_data(item) for item in data]
        return data

    def record(
        self,
        tick: int,
        event_type: str,
        agent: Optional[SimulationAgent] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> ActivityEvent:
        """Record an immutable ActivityEvent with monotonic sequence number.

        Synchronizes live AgentState for stateful agent events.
        """
        clean_data = self.sanitize_data(data or {})

        with transaction.atomic():
            # Get next monotonic sequence for this simulation
            last_seq = (
                ActivityEvent.objects.filter(simulation=self.simulation)
                .select_for_update()
                .aggregate(m=models.Max("sequence"))["m"]
                or 0
            )
            next_seq = last_seq + 1

            event = ActivityEvent.objects.create(
                simulation=self.simulation,
                agent=agent,
                tick=tick,
                event_type=event_type,
                sequence=next_seq,
                data=clean_data,
            )

            # Update live AgentState if an agent is attached
            if agent:
                self._update_agent_state(agent, tick, event_type, clean_data)

        # Broadcast event to active real-time subscribers
        event_payload = {
            "id": event.id,
            "simulation_id": self.simulation.id,
            "tick": event.tick,
            "sequence": event.sequence,
            "event_type": event.event_type,
            "agent_id": agent.id if agent else None,
            "timestamp": event.timestamp.isoformat(),
            "data": clean_data,
        }
        EventPublisher.publish(event_payload)

        return event

    def _update_agent_state(
        self,
        agent: SimulationAgent,
        tick: int,
        event_type: str,
        data: Dict[str, Any],
    ):
        """Update or create the cached AgentState snapshot based on event."""
        state, _ = AgentState.objects.get_or_create(
            simulation=self.simulation,
            agent=agent,
            defaults={"wealth": 0.0, "resources": {}, "health": 100.0, "status": "active"},
        )

        if event_type == EventTypes.AGENT_OBSERVATION:
            state.last_observation_tick = tick
            if "wealth" in data:
                state.wealth = float(data["wealth"])
            if "resources" in data and isinstance(data["resources"], dict):
                state.resources = data["resources"]

        elif event_type == EventTypes.AGENT_DECISION:
            state.last_decision = data
            if "action" in data:
                state.current_action = str(data["action"])

        elif event_type == EventTypes.AGENT_ACTION:
            if "action" in data:
                state.last_action = str(data["action"])

        elif event_type == EventTypes.AGENT_STATE_CHANGED:
            if "status" in data:
                state.status = str(data["status"])
            if "health" in data:
                state.health = float(data["health"])
            if "wealth" in data:
                state.wealth = float(data["wealth"])

        elif event_type in (EventTypes.RESOURCE_CHANGED, EventTypes.AGENT_RESOURCE_CHANGED):
            res_name = data.get("resource")
            curr_val = data.get("current")
            if res_name and curr_val is not None:
                current_res = dict(state.resources or {})
                current_res[res_name] = curr_val
                state.resources = current_res

        elif event_type == EventTypes.TRADE_COMPLETED:
            if "wealth" in data:
                state.wealth = float(data["wealth"])

        state.save()


# ----------------------------------------------------------------------
# Simulation Controller
# ----------------------------------------------------------------------

class SimulationController:
    """Manages the simulation lifecycle state machine and executes ticks."""

    def __init__(self, simulation: Simulation):
        self.simulation = simulation
        self.tracker = ActivityTracker(simulation)

    def start(self) -> Dict[str, Any]:
        """Start or resume the simulation."""
        if self.simulation.status in ("completed", "error"):
            return {
                "error": "invalid_transition",
                "message": f"Cannot start a simulation in '{self.simulation.status}' status",
                "simulation": self.snapshot(),
            }

        if self.simulation.status == "running":
            return {"status": "already_running", "simulation": self.snapshot()}

        is_resume = self.simulation.status == "paused"
        self.simulation.status = "running"
        self.simulation.save(update_fields=["status", "updated_at"])

        event_type = EventTypes.SIMULATION_RESUMED if is_resume else EventTypes.SIMULATION_STARTED
        self.tracker.record(
            tick=self.simulation.current_tick,
            event_type=event_type,
            data={"tick": self.simulation.current_tick},
        )

        return {"status": "started", "simulation": self.snapshot()}

    def pause(self, reason: str = "user_request") -> Dict[str, Any]:
        """Pause a running simulation."""
        if self.simulation.status != "running":
            return {
                "error": "invalid_transition",
                "message": f"Cannot pause a simulation in '{self.simulation.status}' status",
                "simulation": self.snapshot(),
            }

        self.simulation.status = "paused"
        self.simulation.save(update_fields=["status", "updated_at"])

        self.tracker.record(
            tick=self.simulation.current_tick,
            event_type=EventTypes.SIMULATION_PAUSED,
            data={"reason": reason, "tick": self.simulation.current_tick},
        )

        return {"status": "paused", "simulation": self.snapshot()}

    def _build_observation(self, agent: SimulationAgent, state: AgentState, tick: int, all_agents: List[SimulationAgent]) -> AgentObservation:
        """Build an AgentObservation from simulation state for the given agent."""
        other_agents_data = []
        for other in all_agents:
            if other.id == agent.id:
                continue
            other_state = AgentState.objects.filter(
                simulation=self.simulation, agent=other
            ).first()
            other_agents_data.append({
                "id": other.id,
                "name": other.name,
                "role": other.role,
                "wallet": other_state.wealth if other_state else 0.0,
                "inventory": other_state.resources if other_state else {},
            })

        world_resources = [
            {"name": "food", "price": 10, "quantity": 100},
        ]

        return AgentObservation(
            tick=tick,
            self_state={
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "wallet": state.wealth,
                "inventory": state.resources,
                "goals": [],
                "personality": {},
            },
            world_state={
                "name": self.simulation.name,
                "tick": tick,
                "resources": world_resources,
            },
            other_agents=other_agents_data,
            memories=[],
            messages=[],
            pending_trades=[],
            trade_history=[],
            memory_ids=[],
            available_actions=[
                "buy", "sell", "communicate",
                "propose_trade", "accept_trade", "reject_trade",
                "wait",
            ],
        )

    def _execute_action(
        self,
        agent: SimulationAgent,
        state: AgentState,
        action: Action,
        tick: int,
    ) -> Dict[str, Any]:
        """Execute the agent's decided action and update AgentState.

        Returns a dict describing the action result for event recording.
        Failures produce success=False without raising (provider failures
        are captured at the decision layer, not here).
        """
        action_type = action.action_type
        parameters = action.parameters
        result: Dict[str, Any] = {"success": True, "action": action_type}

        if action_type == "wait":
            pass

        elif action_type == "buy":
            resource_name = parameters.get("resource", "food")
            quantity = parameters.get("quantity", 1)
            unit_price = 10

            resources = dict(state.resources or {})
            resources[resource_name] = resources.get(resource_name, 0) + quantity
            state.resources = resources
            state.wealth -= quantity * unit_price
            state.save()

            result.update({
                "resource": resource_name,
                "quantity": quantity,
                "cost": quantity * unit_price,
            })

        elif action_type == "sell":
            resource_name = parameters.get("resource", "food")
            quantity = parameters.get("quantity", 1)
            unit_price = 10

            resources = dict(state.resources or {})
            current = resources.get(resource_name, 0)
            if current >= quantity:
                resources[resource_name] = current - quantity
                state.resources = resources
                state.wealth += quantity * unit_price
                state.save()
                result.update({
                    "resource": resource_name,
                    "quantity": quantity,
                    "revenue": quantity * unit_price,
                })
            else:
                result["success"] = False
                result["reason"] = "insufficient_inventory"

        elif action_type == "communicate":
            result.update({
                "message_id": None,
                "recipient_id": parameters.get("recipient_id"),
                "content": parameters.get("content", ""),
                "conversation_id": parameters.get("conversation_id", ""),
                "intent": parameters.get("intent", "information"),
            })

        elif action_type == "propose_trade":
            result.update({
                "trade_id": None,
                "status": "proposed",
                "recipient_id": parameters.get("recipient_id"),
                "offer": parameters.get("offer", {}),
                "conversation_id": parameters.get("conversation_id", ""),
            })

        elif action_type == "accept_trade":
            result.update({
                "trade_id": parameters.get("trade_id"),
                "status": "accepted",
            })

        elif action_type == "reject_trade":
            result.update({
                "trade_id": parameters.get("trade_id"),
                "status": "rejected",
            })

        return result

    def step(self) -> Dict[str, Any]:
        """Execute exactly one simulation tick across all agents.

        The deterministic tick pattern is:

            world.tick -> agent.observation -> agent.decision -> agent.action
                        -> agent.state_changed
                        -> optional message/trade/resource events

        Each agent is processed deterministically by id.
        Real agent runtimes (rule, random, groq, xai) are invoked for decisions.
        """
        if self.simulation.status in ("completed", "error"):
            return {
                "error": "invalid_transition",
                "message": f"Cannot step a simulation in '{self.simulation.status}' status",
                "simulation": self.snapshot(),
                "events": [],
            }

        is_resume = self.simulation.status == "paused"
        next_tick = self.simulation.current_tick + 1
        self.simulation.current_tick = next_tick

        if self.simulation.status == "created":
            self.simulation.status = "running"
            self.tracker.record(
                tick=0,
                event_type=EventTypes.SIMULATION_STARTED,
                data={"tick": 0},
            )
        elif is_resume:
            self.simulation.status = "running"
            self.tracker.record(
                tick=next_tick,
                event_type=EventTypes.SIMULATION_RESUMED,
                data={"tick": next_tick},
            )

        self.simulation.save(update_fields=["current_tick", "status", "updated_at"])

        tick_events = []

        # 1. World Tick Event
        e_world = self.tracker.record(
            tick=next_tick,
            event_type=EventTypes.WORLD_TICK,
            data={"tick": next_tick, "agent_count": self.simulation.agents.count()},
        )
        tick_events.append(e_world)

        # 2. Iterate each agent through the observation -> decision -> action lifecycle
        agents = list(self.simulation.agents.all().order_by("id"))
        for agent in agents:
            state, _ = AgentState.objects.get_or_create(
                simulation=self.simulation,
                agent=agent,
                defaults={"wealth": 100.0, "resources": {"food": 10, "wood": 5}, "status": "active"},
            )

            # Build observation
            observation = self._build_observation(agent, state, next_tick, agents)

            # Record observation event
            e_obs = self.tracker.record(
                tick=next_tick,
                event_type=EventTypes.AGENT_OBSERVATION,
                agent=agent,
                data={
                    "resources": state.resources,
                    "wealth": state.wealth,
                    "health": state.health,
                    "status": state.status,
                    "available_actions": observation.available_actions,
                    "nearby_agents": [
                        {"id": a["id"], "name": a["name"]}
                        for a in observation.other_agents
                    ],
                    "world_resources": observation.world_state["resources"],
                    "source": "simulation_generated",
                },
            )
            tick_events.append(e_obs)

            # Decision via real agent runtime
            adapter = AgentAdapter(agent)
            try:
                runtime = get_agent_runtime(adapter)
                action = runtime.decide(adapter, observation)
                trace = runtime.trace_metadata()
            except Exception as error:
                action = Action(
                    agent_id=agent.id,
                    action_type="wait",
                    parameters={},
                )
                trace = {
                    "error": str(error),
                    "validation_result": "error",
                }

            decision_data = {
                "runtime": agent.runtime,
                "provider": agent.provider,
                "model": agent.model,
                "action": action.action_type,
                "parameters": action.parameters,
                "source": "simulation_generated",
            }
            if trace:
                decision_data["trace"] = trace

            e_dec = self.tracker.record(
                tick=next_tick,
                event_type=EventTypes.AGENT_DECISION,
                agent=agent,
                data=decision_data,
            )
            tick_events.append(e_dec)

            # Action execution
            action_result = self._execute_action(agent, state, action, next_tick)

            e_act = self.tracker.record(
                tick=next_tick,
                event_type=EventTypes.AGENT_ACTION,
                agent=agent,
                data={**action_result, "source": "simulation_generated"},
            )
            tick_events.append(e_act)

            # Optional resource trade message events
            if action.action_type == "buy" and action_result.get("success"):
                res_name = action_result["resource"]
                res_val = dict(state.resources or {}).get(res_name, 0)
                e_res = self.tracker.record(
                    tick=next_tick,
                    event_type=EventTypes.RESOURCE_CHANGED,
                    agent=agent,
                    data={
                        "resource": res_name,
                        "change": action_result["quantity"],
                        "current": res_val,
                        "reason": "buy",
                    },
                )
                tick_events.append(e_res)

            elif action.action_type == "sell" and action_result.get("success"):
                res_name = action_result["resource"]
                res_val = dict(state.resources or {}).get(res_name, 0)
                e_res = self.tracker.record(
                    tick=next_tick,
                    event_type=EventTypes.RESOURCE_CHANGED,
                    agent=agent,
                    data={
                        "resource": res_name,
                        "change": -action_result["quantity"],
                        "current": res_val,
                        "reason": "sell",
                    },
                )
                tick_events.append(e_res)

            elif action.action_type == "communicate":
                e_msg = self.tracker.record(
                    tick=next_tick,
                    event_type=EventTypes.MESSAGE_CREATED,
                    agent=agent,
                    data={
                        "recipient_id": action_result.get("recipient_id"),
                        "content": action_result.get("content", ""),
                        "conversation_id": action_result.get("conversation_id", ""),
                        "intent": action_result.get("intent", "information"),
                    },
                )
                tick_events.append(e_msg)

            elif action.action_type == "propose_trade":
                e_trade_prop = self.tracker.record(
                    tick=next_tick,
                    event_type=EventTypes.TRADE_PROPOSED,
                    agent=agent,
                    data={
                        "target_agent_id": action_result.get("recipient_id"),
                        "offer": action_result.get("offer", {}),
                    },
                )
                tick_events.append(e_trade_prop)

            elif action.action_type in ("accept_trade", "reject_trade", "wait"):
                pass

            # 3. Agent state changed event after action execution
            e_state = self.tracker.record(
                tick=next_tick,
                event_type=EventTypes.AGENT_STATE_CHANGED,
                agent=agent,
                data={
                    "wealth": state.wealth,
                    "resources": state.resources,
                    "status": "active",
                    "action": action.action_type,
                    "success": action_result.get("success", True),
                    "source": "simulation_generated",
                },
            )
            tick_events.append(e_state)

        # Check completion condition
        if next_tick >= self.simulation.total_ticks:
            self.simulation.status = "completed"
            self.simulation.save(update_fields=["status", "updated_at"])
            e_comp = self.tracker.record(
                tick=next_tick,
                event_type=EventTypes.SIMULATION_COMPLETED,
                data={"total_ticks": self.simulation.total_ticks, "final_tick": next_tick},
            )
            tick_events.append(e_comp)

        return {
            "status": self.simulation.status,
            "tick": next_tick,
            "events_count": len(tick_events),
            "simulation": self.snapshot(),
        }

    def step_locked(self, target_tick: Optional[int] = None) -> Dict[str, Any]:
        """Execute a single tick protected by database-level row locking.

        Uses select_for_update() to prevent two workers from processing the
        same simulation tick simultaneously.
        """
        operation_id = self.simulation.operation_id

        with transaction.atomic():
            # Lock the simulation row to prevent concurrent tick execution
            locked_sim = Simulation.objects.select_for_update().get(
                id=self.simulation.id
            )

            # Idempotency: if already completed, don't re-execute
            if locked_sim.status == "completed" or locked_sim.current_tick >= locked_sim.total_ticks:
                if locked_sim.status != "completed":
                    locked_sim.status = "completed"
                    locked_sim.save(update_fields=["status", "updated_at"])
                return {
                    "status": "already_completed",
                    "simulation": self.snapshot(),
                    "events": [],
                }

            # If target_tick was explicitly specified and already executed
            if target_tick is not None and locked_sim.current_tick >= target_tick:
                return {
                    "status": "already_executed",
                    "tick": locked_sim.current_tick,
                    "simulation": self.snapshot(),
                }

            self.simulation = locked_sim
            self.tracker = ActivityTracker(locked_sim)
            result = self.step()
            logger.info(
                "tick_completed sim_id=%s operation_id=%s tick=%s status=%s events=%s",
                locked_sim.id,
                operation_id,
                result.get("tick"),
                result.get("status"),
                result.get("events_count", 0),
            )
            return result

    def run_to_completion(self) -> Dict[str, Any]:
        """Run the simulation continuously until completion or pause.

        This method is designed for a worker process, not for HTTP requests.
        It loops over self.step_locked() until the simulation reaches a
        terminal state (completed, paused, or error).

        Concurrency safety:
        - Each tick is protected by select_for_update() in step_locked().
        - Paused/error statuses cause the loop to stop.
        - Provider failures are captured per-agent within step(), not here.
        """
        results = []

        while True:
            self.simulation.refresh_from_db()
            if self.simulation.status in ("paused", "error", "completed"):
                break
            if self.simulation.current_tick >= self.simulation.total_ticks:
                self.simulation.status = "completed"
                self.simulation.save(update_fields=["status", "updated_at"])
                break

            result = self.step_locked()

            if result.get("error") or result.get("status") in ("already_completed", "completed", "paused", "error"):
                results.append(result)
                break

            results.append(result)

            self.simulation.refresh_from_db()
            if self.simulation.status in ("paused", "error", "completed"):
                break

        return {
            "status": self.simulation.status,
            "tick": self.simulation.current_tick,
            "total_ticks": self.simulation.total_ticks,
            "steps_executed": len(results),
            "simulation": self.snapshot(),
        }

    def snapshot(self) -> Dict[str, Any]:
        """Return the current complete snapshot of the simulation and all agents."""
        agents_data = []
        for agent in self.simulation.agents.all().order_by("id"):
            state = AgentState.objects.filter(simulation=self.simulation, agent=agent).first()
            agents_data.append({
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "runtime": agent.runtime,
                "provider": agent.provider,
                "model": agent.model,
                "wealth": state.wealth if state else 0.0,
                "resources": state.resources if state else {},
                "health": state.health if state else 100.0,
                "status": state.status if state else "active",
                "current_action": state.current_action if state else "",
                "last_action": state.last_action if state else "",
                "last_decision": state.last_decision if state else {},
                "last_observation_tick": state.last_observation_tick if state else 0,
            })

        latest_event = ActivityEvent.objects.filter(simulation=self.simulation).order_by("-sequence").first()

        return {
            "simulation": {
                "id": self.simulation.id,
                "operation_id": str(self.simulation.operation_id),
                "name": self.simulation.name,
                "status": self.simulation.status,
                "current_tick": self.simulation.current_tick,
                "total_ticks": self.simulation.total_ticks,
                "seed": self.simulation.seed,
                "created_at": self.simulation.created_at.isoformat(),
                "updated_at": self.simulation.updated_at.isoformat(),
            },
            "latest_sequence": latest_event.sequence if latest_event else 0,
            "world": {
                "current_tick": self.simulation.current_tick,
                "status": self.simulation.status,
                "agent_count": len(agents_data),
                "total_events": latest_event.sequence if latest_event else 0,
            },
            "agents": agents_data,
        }
