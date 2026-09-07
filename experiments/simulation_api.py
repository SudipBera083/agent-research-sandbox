# -*- coding: utf-8 -*-
"""REST API and SSE Real-Time Streaming for Simulation Activity Tracking (Step 31A)."""

import json
import queue
import time
from typing import Generator

from django.http import Http404, HttpRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .activity import EventPublisher, SimulationController
from .models import ActivityEvent, Simulation, SimulationAgent


def _serialize_event(event: ActivityEvent) -> dict:
    """Format an ActivityEvent matching the exact frontend contract."""
    return {
        "id": event.id,
        "simulation_id": event.simulation_id,
        "tick": event.tick,
        "sequence": event.sequence,
        "event_type": event.event_type,
        "agent_id": event.agent_id,
        "timestamp": event.timestamp.isoformat(),
        "data": event.data or {},
    }


# ----------------------------------------------------------------------
# State & Snapshot API
# ----------------------------------------------------------------------

@require_GET
def simulation_snapshot(request: HttpRequest, simulation_id: int) -> JsonResponse:
    """GET /api/simulations/<id>/snapshot - Return current simulation & agent states."""
    simulation = get_object_or_404(Simulation, id=simulation_id)
    controller = SimulationController(simulation)
    return JsonResponse(controller.snapshot())


# ----------------------------------------------------------------------
# Event Ledger API (Historical & Polling)
# ----------------------------------------------------------------------

@require_GET
def simulation_events(request: HttpRequest, simulation_id: int) -> JsonResponse:
    """GET /api/simulations/<id>/events - Return event ledger after sequence."""
    simulation = get_object_or_404(Simulation, id=simulation_id)

    try:
        after_seq = int(request.GET.get("after_sequence", 0))
    except (TypeError, ValueError):
        after_seq = 0

    try:
        limit = min(int(request.GET.get("limit", 100)), 1000)
    except (TypeError, ValueError):
        limit = 100

    event_type = request.GET.get("event_type")

    queryset = ActivityEvent.objects.filter(
        simulation=simulation,
        sequence__gt=after_seq,
    )
    if event_type:
        queryset = queryset.filter(event_type=event_type)

    events = list(queryset.order_by("sequence")[:limit])
    serialized = [_serialize_event(e) for e in events]
    latest_seq = serialized[-1]["sequence"] if serialized else after_seq

    return JsonResponse({
        "simulation_id": simulation.id,
        "after_sequence": after_seq,
        "limit": limit,
        "count": len(serialized),
        "latest_sequence": latest_seq,
        "events": serialized,
    })


@require_GET
def agent_events(request: HttpRequest, simulation_id: int, agent_id: int) -> JsonResponse:
    """GET /api/simulations/<id>/agents/<agent_id>/events - Filter events for one agent."""
    simulation = get_object_or_404(Simulation, id=simulation_id)
    agent = get_object_or_404(SimulationAgent, id=agent_id, simulation=simulation)

    try:
        after_seq = int(request.GET.get("after_sequence", 0))
    except (TypeError, ValueError):
        after_seq = 0

    try:
        limit = min(int(request.GET.get("limit", 100)), 1000)
    except (TypeError, ValueError):
        limit = 100

    queryset = ActivityEvent.objects.filter(
        simulation=simulation,
        agent=agent,
        sequence__gt=after_seq,
    ).order_by("sequence")[:limit]

    serialized = [_serialize_event(e) for e in queryset]
    latest_seq = serialized[-1]["sequence"] if serialized else after_seq

    return JsonResponse({
        "simulation_id": simulation.id,
        "agent_id": agent.id,
        "after_sequence": after_seq,
        "limit": limit,
        "count": len(serialized),
        "latest_sequence": latest_seq,
        "events": serialized,
    })


# ----------------------------------------------------------------------
# Simulation Control API
# ----------------------------------------------------------------------

@csrf_exempt
@require_POST
def simulation_start(request: HttpRequest, simulation_id: int) -> JsonResponse:
    """POST /api/simulations/<id>/start - Start or resume simulation."""
    simulation = get_object_or_404(Simulation, id=simulation_id)
    controller = SimulationController(simulation)
    result = controller.start()
    if result.get("error") == "invalid_transition":
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def simulation_pause(request: HttpRequest, simulation_id: int) -> JsonResponse:
    """POST /api/simulations/<id>/pause - Pause a running simulation."""
    simulation = get_object_or_404(Simulation, id=simulation_id)
    controller = SimulationController(simulation)
    result = controller.pause()
    if result.get("error") == "invalid_transition":
        return JsonResponse(result, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def simulation_step(request: HttpRequest, simulation_id: int) -> JsonResponse:
    """POST /api/simulations/<id>/step - Advance simulation by one tick."""
    simulation = get_object_or_404(Simulation, id=simulation_id)
    controller = SimulationController(simulation)
    result = controller.step()
    if result.get("error") == "invalid_transition":
        return JsonResponse(result, status=400)
    return JsonResponse(result)


# ----------------------------------------------------------------------
# Real-Time SSE Stream API
# ----------------------------------------------------------------------

def _sse_event_stream(simulation_id: int, after_sequence: int = 0, max_messages: int = 100) -> Generator[str, None, None]:
    """Generate Server-Sent Events (SSE) from the database ledger and live publisher."""
    # 1. Yield historical backlog from the authoritative database ledger
    historical = ActivityEvent.objects.filter(
        simulation_id=simulation_id,
        sequence__gt=after_sequence,
    ).order_by("sequence")[:max_messages]

    last_sent_seq = after_sequence
    for e in historical:
        payload = _serialize_event(e)
        last_sent_seq = e.sequence
        yield f"event: {e.event_type}\ndata: {json.dumps(payload)}\n\n"

    # 2. Subscribe to live real-time broadcasts
    sub_queue = EventPublisher.subscribe(simulation_id)
    try:
        iterations = 0
        while iterations < 50:  # Bound streaming iterations to avoid hanging worker threads
            iterations += 1
            try:
                event_data = sub_queue.get(timeout=1.0)
                if event_data.get("sequence", 0) > last_sent_seq:
                    last_sent_seq = event_data["sequence"]
                    yield f"event: {event_data.get('event_type', 'message')}\ndata: {json.dumps(event_data)}\n\n"
            except queue.Empty:
                # Keepalive heartbeat
                yield ": keepalive\n\n"
    finally:
        EventPublisher.unsubscribe(simulation_id, sub_queue)


@require_GET
def simulation_stream(request: HttpRequest, simulation_id: int) -> StreamingHttpResponse:
    """GET /api/simulations/<id>/stream - Server-Sent Events (SSE) endpoint."""
    simulation = get_object_or_404(Simulation, id=simulation_id)

    try:
        after_seq = int(request.GET.get("after_sequence", 0))
    except (TypeError, ValueError):
        after_seq = 0

    response = StreamingHttpResponse(
        _sse_event_stream(simulation.id, after_sequence=after_seq),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
