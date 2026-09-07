from django.urls import path

from . import simulation_api

urlpatterns = [
    # Snapshot
    path('<int:simulation_id>/snapshot/', simulation_api.simulation_snapshot, name='simulation_snapshot'),
    # Event ledger
    path('<int:simulation_id>/events/', simulation_api.simulation_events, name='simulation_events'),
    path('<int:simulation_id>/agents/<int:agent_id>/events/', simulation_api.agent_events, name='agent_events'),
    # Control actions
    path('<int:simulation_id>/start/', simulation_api.simulation_start, name='simulation_start'),
    path('<int:simulation_id>/pause/', simulation_api.simulation_pause, name='simulation_pause'),
    path('<int:simulation_id>/step/', simulation_api.simulation_step, name='simulation_step'),
    # Real‑time streaming (SSE)
    path('<int:simulation_id>/stream/', simulation_api.simulation_stream, name='simulation_stream'),
]
