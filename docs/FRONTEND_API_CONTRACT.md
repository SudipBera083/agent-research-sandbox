# AI Agent Sandbox — Frontend Integration API Contract (Step 33)

> **Audience:** Frontend Engineers, Full-Stack Developers, Integration Testers  
> **Status:** Authoritative & Implementation-Accurate (Step 33 Complete)  
> **Backend Engine:** Django 5.2 / Python 3.11  
> **Architecture:** Serverless-Compatible (Vercel Backend / Ephemeral Instances with DB-First Authority)

---

## 1. Backend Base URL & Connection Fundamentals

### Base URLs
* **Local Development Base URL:** `http://127.0.0.1:8000` (or `http://localhost:8000`)
* **Production API Base URL:** `Production API base URL: supplied by deployment environment`

### Routing & Protocol Rules
* **API Route Prefix:** `/api/simulations/`
* **Trailing Slash Requirement:** **MANDATORY**. Django's router has `APPEND_SLASH = True`. All requests must terminate with a trailing slash `/` (e.g., `/api/simulations/1/snapshot/`, NOT `/api/simulations/1/snapshot`). Omitting the trailing slash will trigger a 301 redirect or preflight failure.
* **HTTP Methods Supported:** `GET`, `POST`, `OPTIONS`
* **Content-Type:**
  * Standard REST endpoints: `application/json; charset=utf-8`
  * Real-time stream endpoint: `text/event-stream; charset=utf-8`
* **CORS Behavior (`SimpleCORSMiddleware`):**
  * Handled via Django middleware reading `CORS_ALLOWED_ORIGINS` from environment variables (comma-separated).
  * Automatically handles preflight HTTP `OPTIONS` requests and responds with status `204 No Content`.
  * Headers emitted for allowed origins:
    * `Access-Control-Allow-Origin: <origin>`
    * `Access-Control-Allow-Methods: GET, POST, OPTIONS`
    * `Access-Control-Allow-Headers: Content-Type, Authorization`
    * `Access-Control-Max-Age: 3600`
* **Authentication Status:**
  * Current status: **Unauthenticated / Open Access** for development and internal sandbox testing.
  * POST endpoints (`start`, `pause`, `step`) are decorated with `@csrf_exempt`. No CSRF cookie or bearer token is required in Step 33.
* **Standard JSON Error Response Schema:**
  Whenever an error occurs, the API returns a standardized JSON object:
  ```json
  {
    "error": "not_found",
    "detail": "Resource not found."
  }
  ```
  Or for lifecycle state machine errors:
  ```json
  {
    "error": "invalid_transition",
    "message": "Cannot pause a simulation in 'paused' status",
    "simulation": { ... }
  }
  ```

---

## 2. Complete API Inventory

The following table reflects the **entire set of active HTTP endpoints** implemented in `config/urls.py` and `experiments/urls.py`. No other HTTP endpoints are currently mounted in the router.

| Method | Endpoint | Purpose | Request Body | Query Parameters | Response | Errors |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/simulations/{id}/snapshot/` | Fetch complete current simulation, world, and agent state | None | None | `200 OK` (Snapshot JSON) | `404 Not Found` |
| `GET` | `/api/simulations/{id}/events/` | Query historical event ledger with pagination and replay | None | `after_sequence` (int, default 0)<br>`limit` (int, default 100, max 1000)<br>`event_type` (string, optional) | `200 OK` (Event List JSON) | `404 Not Found` |
| `GET` | `/api/simulations/{id}/agents/{agent_id}/events/` | Query historical event ledger filtered for a single agent | None | `after_sequence` (int, default 0)<br>`limit` (int, default 100, max 1000) | `200 OK` (Agent Events JSON) | `404 Not Found` |
| `POST` | `/api/simulations/{id}/start/` | Start or resume simulation execution | None | None | `200 OK` (Status JSON) | `400 Bad Request`<br>`404 Not Found` |
| `POST` | `/api/simulations/{id}/pause/` | Pause a running simulation | None | None | `200 OK` (Status JSON) | `400 Bad Request`<br>`404 Not Found` |
| `POST` | `/api/simulations/{id}/step/` | Advance simulation by exactly 1 tick (atomic execution) | None | None | `200 OK` (Step Result JSON) | `400 Bad Request`<br>`404 Not Found` |
| `GET` | `/api/simulations/{id}/stream/` | Server-Sent Events (SSE) real-time event stream | None | `after_sequence` (int, default 0) | `200 OK` (`text/event-stream`) | `404 Not Found` |

---

## 3. Snapshot API

* **Endpoint:** `GET /api/simulations/{simulation_id}/snapshot/`
* **Purpose:** Provides a complete point-in-time state of the simulation, the world, and every agent. Used for initial UI mounting, page refreshes, and state reconciliation.

### Realistic Response Example
```json
{
  "simulation": {
    "id": 1,
    "operation_id": "8c42b8e3-4f9e-4e3a-8b1e-9d2a6c1e5f3b",
    "name": "Market Competition Alpha",
    "status": "running",
    "current_tick": 14,
    "total_ticks": 100,
    "seed": 42,
    "created_at": "2026-09-07T12:00:00.000000+00:00",
    "updated_at": "2026-09-07T12:05:14.284910+00:00"
  },
  "latest_sequence": 84,
  "world": {
    "current_tick": 14,
    "status": "running",
    "agent_count": 2,
    "total_events": 84
  },
  "agents": [
    {
      "id": 1,
      "name": "Trader-Alpha",
      "role": "wealth",
      "runtime": "rule",
      "provider": "deterministic",
      "model": "rule",
      "wealth": 140.0,
      "resources": {
        "food": 14,
        "wood": 5
      },
      "health": 100.0,
      "status": "active",
      "current_action": "buy",
      "last_action": "buy",
      "last_decision": {
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
        "action": "buy",
        "parameters": {
          "resource": "food",
          "quantity": 1
        },
        "source": "simulation_generated"
      },
      "last_observation_tick": 14
    },
    {
      "id": 2,
      "name": "Agent-Beta",
      "role": "general",
      "runtime": "llm",
      "provider": "groq",
      "model": "llama3-70b-8192",
      "wealth": 95.0,
      "resources": {
        "food": 9,
        "wood": 6
      },
      "health": 98.5,
      "status": "active",
      "current_action": "communicate",
      "last_action": "communicate",
      "last_decision": {
        "runtime": "llm",
        "provider": "groq",
        "model": "llama3-70b-8192",
        "action": "communicate",
        "parameters": {
          "recipient_id": 1,
          "content": "Proposing food trade next tick.",
          "intent": "trade_inquiry"
        },
        "source": "simulation_generated",
        "trace": {
          "tokens_used": 142,
          "latency_ms": 312.4
        }
      },
      "last_observation_tick": 14
    }
  ]
}
```

### Detailed Field Breakdown

#### Root Level
* `simulation` (object): Metadata and configuration of the simulation instance.
* `latest_sequence` (int): The highest monotonic sequence number currently committed to the event ledger. **This is the canonical cursor for frontend event replay.**
* `world` (object): Global environment metrics.
  * `current_tick` (int): Current simulation tick count (0 to `total_ticks`).
  * `status` (string): Mirror of `simulation.status`.
  * `agent_count` (int): Total number of agents registered in this simulation.
  * `total_events` (int): Total count of events emitted across all ticks.
* `agents` (array of objects): Live snapshot of each agent's current state.

#### Agent Fields
| Field | Type | Description | Mutates During Execution? |
| :--- | :--- | :--- | :--- |
| `id` | int | Unique primary key of the agent. | No |
| `name` | string | Human-readable name of the agent. | No |
| `role` | string | Behavioral role archetype (`wealth`, `survival`, `cooperative`, `general`). | No |
| `runtime` | string | Runtime engine type (`rule`, `random`, `llm`). | No |
| `provider` | string | Model provider (`deterministic`, `groq`, `xai`). | No |
| `model` | string | Underlying model identifier (`rule`, `random`, `llama3-70b-8192`, `grok-beta`). | No |
| `wealth` | float | Current liquid currency balance. | **Yes** (Updated upon trades, buys, sells) |
| `resources` | object | Key-value inventory map (e.g. `{"food": 10, "wood": 5}`). | **Yes** (Updated on consumption or trade) |
| `health` | float | Agent health points (0.0 to 100.0). | **Yes** |
| `status` | string | Agent operational status (`active`, `died`, `resting`). | **Yes** |
| `current_action` | string | The action decided by the agent in the most recent tick. | **Yes** |
| `last_action` | string | The action executed by the agent in the previous tick. | **Yes** |
| `last_decision` | object | Complete decision payload including action parameters and execution trace. | **Yes** |
| `last_observation_tick` | int | The tick number during which the agent last received world observations. | **Yes** |

---

## 4. Event Ledger API

* **Endpoint:** `GET /api/simulations/{simulation_id}/events/`
* **Purpose:** Historical event query and sequence-based replay. Used when recovering from SSE network disconnects or paging through the activity log.

### Query Parameters
* `after_sequence` (int, default `0`): Only return events where `sequence > after_sequence`.
* `limit` (int, default `100`, maximum `1000`): Maximum number of events to return in a single page.
* `event_type` (string, optional): Filter by exact event type (e.g. `agent.decision`).

### Response Example
```json
{
  "simulation_id": 1,
  "after_sequence": 4,
  "limit": 3,
  "count": 3,
  "latest_sequence": 7,
  "events": [
    {
      "id": 5,
      "simulation_id": 1,
      "tick": 1,
      "sequence": 5,
      "event_type": "agent.decision",
      "agent_id": 1,
      "timestamp": "2026-09-07T12:00:01.215000+00:00",
      "data": {
        "runtime": "rule",
        "provider": "deterministic",
        "model": "rule",
        "action": "buy",
        "parameters": {
          "resource": "food",
          "quantity": 1
        },
        "source": "simulation_generated"
      }
    },
    {
      "id": 6,
      "simulation_id": 1,
      "tick": 1,
      "sequence": 6,
      "event_type": "agent.action",
      "agent_id": 1,
      "timestamp": "2026-09-07T12:00:01.218000+00:00",
      "data": {
        "action": "buy",
        "success": true,
        "resource": "food",
        "quantity": 1,
        "cost": 10,
        "source": "simulation_generated"
      }
    },
    {
      "id": 7,
      "simulation_id": 1,
      "tick": 1,
      "sequence": 7,
      "event_type": "resource.changed",
      "agent_id": 1,
      "timestamp": "2026-09-07T12:00:01.220000+00:00",
      "data": {
        "resource": "food",
        "change": 1,
        "current": 11,
        "reason": "buy"
      }
    }
  ]
}
```

### Event Object Properties
* `id` (int): Internal database primary key of the event record.
* `simulation_id` (int): Foreign key of the parent simulation.
* `tick` (int): Simulation tick during which the event occurred.
* `sequence` (int): **Monotonically increasing sequence integer**. Unique per simulation. Strictly defines causality and order.
* `event_type` (string): Canonical event string.
* `agent_id` (int | null): Associated agent ID, or `null` for global/world events.
* `timestamp` (string): ISO-8601 UTC creation timestamp.
* `data` (object): Event payload. Sanitized on the backend to guarantee that API keys, passwords, or authorization tokens are never included.

---

## 5. Agent Event API

* **Endpoint:** `GET /api/simulations/{simulation_id}/agents/{agent_id}/events/`
* **Purpose:** Filtered event ledger containing only events explicitly associated with the specified agent.

### Query Parameters
* `after_sequence` (int, default `0`): Minimum sequence cutoff.
* `limit` (int, default `100`, max `1000`): Page limit.

### Response Example
```json
{
  "simulation_id": 1,
  "agent_id": 2,
  "after_sequence": 0,
  "limit": 2,
  "count": 2,
  "latest_sequence": 12,
  "events": [
    {
      "id": 10,
      "simulation_id": 1,
      "tick": 2,
      "sequence": 11,
      "event_type": "agent.observation",
      "agent_id": 2,
      "timestamp": "2026-09-07T12:00:02.100000+00:00",
      "data": {
        "resources": {"food": 10, "wood": 5},
        "wealth": 100.0,
        "health": 100.0,
        "status": "active",
        "available_actions": ["wait", "buy", "sell", "communicate", "propose_trade"],
        "nearby_agents": [{"id": 1, "name": "Trader-Alpha"}],
        "world_resources": [{"name": "food", "quantity": 100, "price": 10}],
        "source": "simulation_generated"
      }
    },
    {
      "id": 11,
      "simulation_id": 1,
      "tick": 2,
      "sequence": 12,
      "event_type": "agent.decision",
      "agent_id": 2,
      "timestamp": "2026-09-07T12:00:02.450000+00:00",
      "data": {
        "runtime": "llm",
        "provider": "groq",
        "model": "llama3-70b-8192",
        "action": "wait",
        "parameters": {},
        "source": "simulation_generated",
        "trace": {
          "tokens_used": 98,
          "latency_ms": 284.1
        }
      }
    }
  ]
}
```

---

## 6. Simulation Lifecycle APIs

The backend manages state through a strictly validated finite-state machine (FSM):

```text
       ┌──────────────┐
       │   created    │
       └──────┬───────┘
              │ POST /start/ (or POST /step/)
              ▼
       ┌──────────────┐
  ┌───►│   running    │◄───┐
  │    └──────┬───────┘    │
  │           │            │
  │ POST      │ POST       │ POST
  │ /start/   │ /pause/    │ /start/
  │           ▼            │
  │    ┌──────────────┐    │
  └────┤    paused    ├────┘
       └──────────────┘
              │
              │ (when current_tick >= total_ticks)
              ▼
       ┌──────────────┐
       │  completed   │
       └──────────────┘
```

### 1. Start / Resume
* **Endpoint:** `POST /api/simulations/{simulation_id}/start/`
* **Allowed States:** `created`, `paused`, `running`
* **Transitions & Events:**
  * From `created`: Transitions to `running`. Emits `simulation.started` (tick 0).
  * From `paused`: Transitions to `running`. Emits `simulation.resumed` (tick = `current_tick`).
  * From `running`: Returns `{"status": "already_running", "simulation": { ... }}` with HTTP `200 OK`. No event emitted.
* **Invalid Transitions:**
  * Calling `/start/` on a `completed` or `error` simulation returns HTTP `400 Bad Request`:
    ```json
    {
      "error": "invalid_transition",
      "message": "Cannot start a simulation in 'completed' status",
      "simulation": { ... }
    }
    ```

### 2. Pause
* **Endpoint:** `POST /api/simulations/{simulation_id}/pause/`
* **Allowed States:** `running`
* **Transitions & Events:**
  * Transitions to `paused`. Emits `simulation.paused` (tick = `current_tick`).
* **Invalid Transitions:**
  * Calling `/pause/` on `paused`, `created`, or `completed` returns HTTP `400 Bad Request`:
    ```json
    {
      "error": "invalid_transition",
      "message": "Cannot pause a simulation in 'paused' status",
      "simulation": { ... }
    }
    ```

### 3. Step (Single Tick Execution)
* **Endpoint:** `POST /api/simulations/{simulation_id}/step/`
* **Allowed States:** `created`, `paused`, `running`
* **Execution Logic:**
  1. If status is `created`, it auto-starts and emits `simulation.started`.
  2. If status is `paused`, it auto-resumes and emits `simulation.resumed`.
  3. Increments `current_tick = current_tick + 1`.
  4. Locks database row via `select_for_update()` to prevent concurrent duplicate ticks.
  5. Emits the canonical per-tick event chain.
  6. If `current_tick >= total_ticks`, automatically transitions status to `completed` and emits `simulation.completed`.
* **Response Example:**
  ```json
  {
    "status": "running",
    "tick": 1,
    "events_count": 5,
    "simulation": { ... }
  }
  ```
* **Invalid Transitions:**
  * Calling `/step/` on `completed` or `error` returns HTTP `400 Bad Request`.

---

## 7. Canonical Per-Tick Event Sequence

The backend guarantees a **deterministic, monotonic execution order** within each tick. The frontend **MUST** use the event `sequence` field (NOT local browser arrival time) as the canonical sorting key.

```text
Tick N Execution Chain:
────────────────────────────────────────────────────────────────────────
[1] world.tick               (Announces tick start and world agent count)
────────────────────────────────────────────────────────────────────────
For each Agent (sorted strictly by Agent.id ascending):
    [2.1] agent.observation   (Payload of visible resources & nearby agents)
    [2.2] agent.decision      (Agent decision output + runtime trace metadata)
    [2.3] agent.action        (Action execution outcome: success/cost/payload)
    [2.4] Conditional Events:
          ├── resource.changed  (If buy or sell action succeeded)
          ├── message.created   (If communicate action executed)
          └── trade.proposed    (If propose_trade executed)
    [2.5] agent.state_changed (Updated wealth, health, and inventory state)
────────────────────────────────────────────────────────────────────────
[3] simulation.completed     (Emitted ONLY if next_tick >= total_ticks)
```

### Multi-Agent Tick Trace Example
For a simulation with Agent 1 (`rule`) and Agent 2 (`llm`):

| Sequence | Tick | Event Type | Target Agent | Key Data Fields |
| :--- | :--- | :--- | :--- | :--- |
| `101` | 12 | `world.tick` | `null` | `{"tick": 12, "agent_count": 2}` |
| `102` | 12 | `agent.observation` | Agent 1 | `{"wealth": 100.0, "resources": {"food": 10}}` |
| `103` | 12 | `agent.decision` | Agent 1 | `{"action": "buy", "parameters": {"resource": "food"}}` |
| `104` | 12 | `agent.action` | Agent 1 | `{"action": "buy", "success": true, "cost": 10}` |
| `105` | 12 | `resource.changed` | Agent 1 | `{"resource": "food", "change": 1, "current": 11}` |
| `106` | 12 | `agent.state_changed` | Agent 1 | `{"wealth": 90.0, "resources": {"food": 11}}` |
| `107` | 12 | `agent.observation` | Agent 2 | `{"wealth": 100.0, "resources": {"food": 10}}` |
| `108` | 12 | `agent.decision` | Agent 2 | `{"action": "wait", "trace": {"tokens_used": 110}}` |
| `109` | 12 | `agent.action` | Agent 2 | `{"action": "wait", "success": true}` |
| `110` | 12 | `agent.state_changed` | Agent 2 | `{"wealth": 100.0, "resources": {"food": 10}}` |

---

## 8. Real Agent Runtime Behavior & Safe Displays

The backend supports three core runtime architectures:

### 1. `rule` (Rule-Based Engine)
* **Underlying Provider:** `deterministic`
* **Operation:** Heuristic decision trees based on assigned archetype:
  * `wealth`: Aggressively buys food/resources to build asset base.
  * `survival`: Conserves wealth, buys food only when depleted.
  * `cooperative`: Prioritizes communication and trade proposals.
* **Latency:** < 1 ms.
* **Network Call:** None (local in-memory evaluation).

### 2. `random` (Stochastic Engine)
* **Underlying Provider:** `deterministic`
* **Operation:** Uniformly selects randomly between available legal actions (`wait`, `buy`, `accept_trade`).
* **Latency:** < 1 ms.
* **Network Call:** None.

### 3. `llm` (Large Language Model Runtimes)
* **Supported Providers:**
  * `groq` (Production Model: `llama3-70b-8192` or configured default)
  * `xai` (Production Model: `grok-beta` or configured default)
  * `deterministic` (Mock LLM response engine for offline testing)
* **Latency:** 200 ms – 1200 ms depending on provider availability.
* **Failure Isolation & Fallback Policy:**
  * Provider API errors, HTTP timeouts, network dropouts, or JSON schema validation failures **NEVER** crash the simulation.
  * The runtime catches the exception, forces a safe fallback action (`action: "wait"`), and records the error details in the decision trace:
    ```json
    "trace": {
      "error": "ConnectionError: Groq rate limit exceeded",
      "validation_result": "error"
    }
    ```
* **Security & Secret Stripping:**
  * The backend `ActivityTracker.sanitize_data()` method recursively strips keys matching `api_key`, `token`, `secret`, `authorization`, `password`, `groq_api_key`, and `xai_api_key`.
  * **Safe for frontend display:** `runtime`, `provider`, `model`, `tokens_used`, `latency_ms`, `error`.

---

## 9. Agent Activity Visualization Mapping

Use the following mapping to drive dashboard animations, status badges, and feeds:

| Backend `event_type` | UI Meaning | Suggested Dashboard Component | Visual Styling |
| :--- | :--- | :--- | :--- |
| `simulation.started` | Simulation initiated | Header Status Banner | Green pulse badge |
| `simulation.paused` | Simulation execution halted | Header Status Banner | Amber warning badge |
| `simulation.resumed` | Simulation execution restarted | Header Status Banner | Green pulse badge |
| `simulation.completed` | Simulation reached final tick | Completion Modal / Banner | Blue checkmark notification |
| `world.tick` | World time progressed | Global Tick Counter | Digital clock ticker increment |
| `agent.observation` | Agent perceived surroundings | Agent Inspector Drawer | Radar / Sensor sweep icon |
| `agent.decision` | Agent selected an action | Agent Card Thought Bubble | Brain icon; show latency tag |
| `agent.action` | Agent executed selected action | Activity Feed Item | Action badge (`BUY`, `WAIT`, `TRADE`) |
| `agent.state_changed` | Wealth/inventory modified | Agent Stat Bars | Green/red number flash |
| `resource.changed` | Resource stock changed | Inventory Progress Bars | Inventory delta counter (`+1 Food`) |
| `message.created` | Agent transmitted communication | Social / Chat Feed | Chat bubble with sender & recipient |
| `trade.proposed` | Trade offer posted | Active Trades Panel | Exchange offer card |
| `trade.completed` | Trade successfully settled | Transaction Ledger | Handshake icon; currency exchange |
| `agent.died` | Agent health depleted to 0 | Agent Card Status | Grayed-out / skull badge |

---

## 10. SSE Real-Time Stream (`/api/simulations/{id}/stream/`)

* **Endpoint:** `GET /api/simulations/{simulation_id}/stream/?after_sequence=N`
* **Protocol:** Standard Server-Sent Events (SSE)
* **Content-Type:** `text/event-stream`
* **Keepalive Mechanism:** The server yields `: keepalive\n\n` comments every 1.0 second during idle periods to prevent intermediate proxies and Vercel edge routers from terminating the connection.

### Wire Protocol Output
```text
event: world.tick
data: {"id":1,"simulation_id":1,"tick":1,"sequence":1,"event_type":"world.tick","agent_id":null,"timestamp":"2026-09-07T12:00:00.000000+00:00","data":{"tick":1,"agent_count":2}}

event: agent.observation
data: {"id":2,"simulation_id":1,"tick":1,"sequence":2,"event_type":"agent.observation","agent_id":1,"timestamp":"2026-09-07T12:00:00.010000+00:00","data":{"wealth":100.0}}

: keepalive

```

### Serverless Streaming Lifecycle
To accommodate serverless function execution limits (e.g. Vercel max execution duration), the backend generator is capped at **50 stream iterations** (~50 seconds of idle time or 50 queued events). Once the generator completes, the HTTP response ends cleanly. **The frontend EventSource must automatically reconnect using the highest received sequence.**

### Production Frontend JavaScript Implementation

```javascript
class SimulationStreamManager {
  constructor(apiBaseUrl, simulationId, onEventCallback) {
    this.apiBaseUrl = apiBaseUrl.replace(/\/+$/, '');
    this.simulationId = simulationId;
    this.onEvent = onEventCallback;
    this.lastSequence = 0;
    this.eventSource = null;
    this.isExplicitlyClosed = false;
    this.reconnectAttempts = 0;
  }

  start(initialSequence = 0) {
    this.lastSequence = initialSequence;
    this.isExplicitlyClosed = false;
    this.connect();
  }

  connect() {
    if (this.isExplicitlyClosed) return;

    const streamUrl = `${this.apiBaseUrl}/api/simulations/${this.simulationId}/stream/?after_sequence=${this.lastSequence}`;
    this.eventSource = new EventSource(streamUrl);

    // List of canonical event types emitted by the backend
    const eventTypes = [
      'world.tick',
      'agent.observation',
      'agent.decision',
      'agent.action',
      'agent.state_changed',
      'resource.changed',
      'message.created',
      'trade.proposed',
      'trade.accepted',
      'trade.rejected',
      'trade.completed',
      'simulation.started',
      'simulation.paused',
      'simulation.resumed',
      'simulation.completed',
      'simulation.error'
    ];

    eventTypes.forEach(eventType => {
      this.eventSource.addEventListener(eventType, (e) => {
        try {
          const payload = JSON.parse(e.data);
          // Strict deduplication guard
          if (payload.sequence > this.lastSequence) {
            this.lastSequence = payload.sequence;
            this.onEvent(payload);
          }
        } catch (err) {
          console.error('Failed to parse SSE payload:', err, e.data);
        }
      });
    });

    this.eventSource.onopen = () => {
      this.reconnectAttempts = 0;
      console.log(`SSE connected to simulation ${this.simulationId} at sequence ${this.lastSequence}`);
    };

    this.eventSource.onerror = (err) => {
      console.warn('SSE connection closed or interrupted. Reconnecting...', err);
      this.eventSource.close();
      if (!this.isExplicitlyClosed) {
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), delay);
      }
    };
  }

  stop() {
    this.isExplicitlyClosed = true;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}
```

---

## 11. Reconnection & Data Replay Strategy

```text
1. INITIAL MOUNT:
   GET /api/simulations/{id}/snapshot/
   ├── Populate World State
   ├── Populate Agent Cards
   └── Store local: lastSequence = snapshot.latest_sequence

2. REPLAY CHECK:
   GET /api/simulations/{id}/events/?after_sequence={lastSequence}
   ├── Process any missed events
   └── Update local: lastSequence = response.latest_sequence

3. LIVE STREAMING:
   Connect SSE: /api/simulations/{id}/stream/?after_sequence={lastSequence}
   └── When event arrives:
       ├── If event.sequence <= lastSequence: IGNORE (Deduplication)
       ├── Else: Process event & update lastSequence = event.sequence

4. UPON DISCONNECT (Serverless timeout or network drop):
   EventSource.onerror triggers
   └── Wait backoff delay (1s, 2s, 4s...)
   └── Reconnect: /api/simulations/{id}/stream/?after_sequence={lastSequence}
   └── (Backend automatically flushes DB backlog before switching to live queue)
```

---

## 12. Snapshot + Event Architecture Reconciliation

To prevent race conditions between snapshot fetching and event streaming:
1. **Initial Mount:** Fetch `GET /snapshot/` and set `lastSequence = snapshot.latest_sequence`.
2. **Buffer Live Events:** Immediately open SSE with `?after_sequence=${lastSequence}`.
3. **Atomic State Updates:** If an event arrives with `sequence <= lastSequence`, discard it. If `sequence === lastSequence + 1`, apply it directly to the frontend store.
4. **Out-of-Order Recovery:** If `event.sequence > lastSequence + 1`, the frontend has missed an event chunk. Execute `GET /events/?after_sequence=${lastSequence}` to patch the gap before applying the new event.

---

## 13. Benchmark / Historical Analysis APIs

> **CURRENT STATUS (Step 33):**  
> `These currently exist as backend reporting/CLI functionality and are not exposed as frontend HTTP endpoints.`

* **Backend Engine:** Implemented in `experiments/reporting.py`, `experiments/insights.py`, and `experiments/decision_summary.py`.
* **Execution Mechanism:** Generated via Django CLI command:
  ```bash
  python manage.py run_benchmark_report --output-dir reports
  ```
* **Output Format:** Generates `reports/report.json` containing complete metrics, runtime comparisons, cross-scenario consistency rankings, and visual charts (`reports/*.png`).
* **HTTP Exposure Status:** No URL routes exist under `/api/` for benchmarks. Frontend dashboards cannot query benchmarks via REST in Step 33.

---

## 14. Decision Summary

The decision summary engine is implemented in `experiments/decision_summary.py` (`BenchmarkDecisionSummary`).

### Data Structure Produced by Backend Service:
```json
{
  "overall_leader": {
    "runtime": "rule",
    "average_wealth": 142.5,
    "scenario_wins": 3
  },
  "scenario_leaders": {
    "baseline_market": {"winner": "rule", "wealth": 150.0},
    "resource_scarcity": {"winner": "llm", "wealth": 128.0}
  },
  "most_consistent_runtime": {
    "runtime": "rule",
    "wealth_range": 15.0
  },
  "strongest_observed_advantage": {
    "runtime": "rule",
    "metric": "wealth",
    "advantage_percent": 18.5
  },
  "llm_assessment": {
    "available": true,
    "provider": "groq",
    "model": "llama3-70b-8192",
    "average_latency_ms": 340.2,
    "failure_rate": 0.0
  },
  "trade_social_summary": {
    "most_active_trader": "Trader-Alpha",
    "total_trades": 24
  },
  "coverage_summary": {
    "scenarios_evaluated": 4,
    "runtimes_tested": ["rule", "random", "llm"]
  },
  "recommendations": [
    "Rule-based agents demonstrate highest average wealth in high-frequency trading scenarios.",
    "LLM agents exhibit superior adaptive behaviors under resource scarcity constraints."
  ]
}
```
* **How Frontend Can Access:** Currently inaccessible via HTTP. A future endpoint such as `GET /api/benchmarks/latest/` or `GET /api/simulations/{id}/summary/` would need to be added.

---

## 15. Error Handling Matrix

| HTTP Status | Error Code | Example Scenario | Frontend Handling Action |
| :--- | :--- | :--- | :--- |
| `400 Bad Request` | `"invalid_transition"` | Triggering `/pause/` on an already paused or completed simulation | Show toast notification indicating invalid action; refresh UI state with attached `simulation` object. |
| `404 Not Found` | `"not_found"` | Simulation ID `99999` does not exist | Display "Simulation Not Found" error page; redirect user to simulation selector. |
| `500 Internal Error` | `"internal_server_error"` | Unexpected server or database exception | Show non-technical error alert ("Simulation engine encountered a temporary fault"). Prompt user to retry. |

---

## 16. Frontend State Model (TypeScript Definition)

```typescript
export type SimulationStatus = 'created' | 'running' | 'paused' | 'completed' | 'error';
export type RuntimeType = 'rule' | 'random' | 'llm';
export type ProviderType = 'deterministic' | 'groq' | 'xai';

export interface SimulationMetadata {
  id: number;
  operation_id: string;
  name: string;
  status: SimulationStatus;
  current_tick: number;
  total_ticks: number;
  seed: number;
  created_at: string;
  updated_at: string;
}

export interface AgentDecisionTrace {
  tokens_used?: number;
  latency_ms?: number;
  error?: string;
  validation_result?: string;
}

export interface AgentDecision {
  runtime: RuntimeType;
  provider: ProviderType;
  model: string;
  action: string;
  parameters: Record<string, any>;
  source: string;
  trace?: AgentDecisionTrace;
}

export interface AgentState {
  id: number;
  name: string;
  role: string;
  runtime: RuntimeType;
  provider: ProviderType;
  model: string;
  wealth: number;
  resources: Record<string, number>;
  health: number;
  status: string;
  current_action: string;
  last_action: string;
  last_decision: AgentDecision;
  last_observation_tick: number;
}

export interface WorldState {
  current_tick: number;
  status: SimulationStatus;
  agent_count: number;
  total_events: number;
}

export interface ActivityEvent {
  id: number;
  simulation_id: number;
  tick: number;
  sequence: number;
  event_type: string;
  agent_id: number | null;
  timestamp: string;
  data: Record<string, any>;
}

export interface SimulationDashboardState {
  simulation: SimulationMetadata | null;
  world: WorldState | null;
  agents: Record<number, AgentState>;
  events: ActivityEvent[];
  latestSequence: number;
  isStreaming: boolean;
  reconnectCount: number;
}
```

---

## 17. Agent Detail Panel Specification

When a user clicks on an agent card, the frontend should display an **Agent Detail Panel** combining:
1. **Agent Metadata (from `GET /snapshot/`):**
   * Name, ID, Archetype Role, Runtime Engine (`rule` / `random` / `llm`), Provider & Model.
2. **Current Vital Signs (from `AgentState`):**
   * Wealth balance (formatted currency).
   * Resource Inventory (Food, Wood counts rendered as status bars).
   * Health meter (0% - 100%).
3. **Decision & Thought Trace (from `last_decision`):**
   * Selected Action & Parameter display.
   * Model latency badge (`latency_ms`).
   * Provider error banner (if `trace.error` exists).
4. **Agent-Specific Event Feed (from `GET /agents/{id}/events/`):**
   * Filtered chronological feed of this agent's observations, decisions, actions, trades, and status changes.

---

## 18. Simulation Dashboard Component Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ SIMULATION CONTROL BAR                                                      │
│ Status: [RUNNING]  Tick: [14 / 100]  Seq: #84   Controls: [START] [PAUSE] [STEP]│
├─────────────────────────────────────────────────────────────────────────────┤
│ WORLD ENVIRONMENT                                                           │
│ Agents: 2 | Total Ledger Events: 84 | Connection: SSE Active (0 drops)      │
├──────────────────────────────────────────┬──────────────────────────────────┤
│ AGENT CARDS GRID                         │ REAL-TIME ACTIVITY FEED          │
│ ┌──────────────────────────────────────┐ │ 12:05:14 [Tick 14] Trader-Alpha  │
│ │ 🤖 Trader-Alpha (rule)               │ │   Action: BUY 1 Food (Cost: 10)  │
│ │ Wealth: $140.0 | Food: 14            │ │ 12:05:14 [Tick 14] Agent-Beta    │
│ │ Current: buy | Last: buy             │ │   Message to Trader-Alpha        │
│ └──────────────────────────────────────┘ │ 12:05:15 [Tick 15] world.tick    │
│ ┌──────────────────────────────────────┐ │                                  │
│ │ 🧠 Agent-Beta (llm: groq/llama3)     │ │                                  │
│ │ Wealth: $95.0 | Food: 9              │ │                                  │
│ │ Thought: "Proposing trade..."        │ │                                  │
│ └──────────────────────────────────────┘ │                                  │
└──────────────────────────────────────────┴──────────────────────────────────┘
```

---

## 19. Concrete User Flow Sequences

### Flow A: Opening a Simulation Dashboard
1. Frontend executes: `GET /api/simulations/1/snapshot/`.
2. Frontend renders layout with current status, agent inventories, and tick count.
3. Frontend initializes SSE stream: `new EventSource('/api/simulations/1/stream/?after_sequence=' + snapshot.latest_sequence)`.

### Flow B: Starting the Simulation
1. User clicks **"Start"**.
2. Frontend issues: `POST /api/simulations/1/start/`.
3. Backend returns updated snapshot status (`running`).
4. SSE stream emits `simulation.started` or `simulation.resumed`.
5. UI updates start button to disabled, pause button to enabled.

### Flow C: Pausing the Simulation
1. User clicks **"Pause"**.
2. Frontend issues: `POST /api/simulations/1/pause/`.
3. Backend returns updated snapshot status (`paused`).
4. SSE stream emits `simulation.paused`.
5. UI updates pause button to disabled, start button to enabled.

### Flow D: Manual Single-Step
1. User clicks **"Step"**.
2. Frontend issues: `POST /api/simulations/1/step/`.
3. Backend atomically executes tick, returns step summary with updated snapshot.
4. SSE stream flushes the tick events (`world.tick` -> agent observations -> decisions -> actions -> state changes).
5. Frontend updates UI counters and animates agent cards.

### Flow E: Full Simulation Completion
1. While stepping or running continuously, `current_tick` reaches `total_ticks`.
2. Backend automatically updates database status to `completed`.
3. Backend emits `simulation.completed`.
4. SSE delivers `simulation.completed` event.
5. Frontend disables Start/Pause/Step buttons and displays completion summary.

---

## 20. Vercel & Serverless Deployment Constraints

* **Serverless Instance Ephemerality:** Vercel functions are stateless and spin down when idle. The backend **Database (SQLite / PostgreSQL)** is the authoritative event store. In-memory components (`EventPublisher`) only assist active HTTP streams connected to that specific process.
* **Stream Timeouts:** Serverless environments enforce hard execution timeouts (15–60 seconds). The backend SSE stream automatically terminates after 50 iterations (~50s). The frontend `EventSource` **must** gracefully reconnect with `?after_sequence=${lastKnownSequence}`.
* **Polling Fallback:** If a client browser or corporate firewall blocks SSE streaming (`text/event-stream`), the frontend can seamlessly fall back to HTTP polling:
  ```javascript
  setInterval(async () => {
    const res = await fetch(`/api/simulations/${simId}/events/?after_sequence=${lastSequence}&limit=100`);
    const data = await res.json();
    data.events.forEach(processEvent);
  }, 1000);
  ```

---

## 21. Security & Production Hardening Checklist

* [x] **Secret Sanitization:** `ActivityTracker.sanitize_data()` recursively purges API keys and tokens from event records before database commitment and SSE broadcast.
* [x] **CORS Configuration:** `SimpleCORSMiddleware` restricts origins based on `CORS_ALLOWED_ORIGINS` and safely handles preflight requests.
* [x] **Error Isolation:** Middleware converts unhandled exceptions into sanitized JSON responses (`{"error": "internal_server_error"}`), preventing traceback leaks.
* [ ] **Authentication & Authorization:** Currently open/unauthenticated. Future production builds will require JWT or session auth on control endpoints.
* [ ] **Rate Limiting:** No rate limiting is currently enforced on `/api/simulations/*`.
* [ ] **Public Simulation ID Guessing:** Simulation IDs are auto-incrementing integers (`1`, `2`, ...). While `operation_id` (UUID) exists on the model, URL routing is keyed on integer IDs.

---

## 22. Frontend Quick Reference & Event Cheat Sheet

### Endpoints Cheat Sheet
```text
GET   /api/simulations/{id}/snapshot/                    Fetch full simulation, world & agent state
GET   /api/simulations/{id}/events/?after_sequence=N     Fetch event ledger page after sequence N
GET   /api/simulations/{id}/agents/{aId}/events/         Fetch agent event ledger page after sequence N
POST  /api/simulations/{id}/start/                       Start / resume simulation execution
POST  /api/simulations/{id}/pause/                       Pause simulation execution
POST  /api/simulations/{id}/step/                        Advance simulation by 1 tick atomically
GET   /api/simulations/{id}/stream/?after_sequence=N     Connect SSE real-time event stream
```

### Canonical Event Vocabulary (`EventTypes`)
```text
simulation.created          Simulation record initialized
simulation.started          Simulation initiated execution (tick 0)
simulation.paused           Simulation execution paused
simulation.resumed          Simulation execution resumed
simulation.completed        Simulation reached total_ticks limit
simulation.error            Simulation encountered fatal execution error
world.tick                  Time advanced by 1 tick
agent.spawned               Agent entered simulation
agent.observation           Agent observed visible world state
agent.decision              Agent selected an action (includes trace)
agent.action                Agent executed action in world
agent.state_changed         Agent wealth, health, or status updated
agent.resource_changed      Agent resource count adjusted
message.created             Communication sent between agents
trade.proposed              Trade exchange proposed
trade.accepted              Trade exchange accepted
trade.rejected              Trade exchange rejected
trade.completed             Trade settled and wealth/resources transferred
resource.changed            Global or agent resource delta recorded
agent.died                  Agent health depleted to zero
agent.recovered             Agent returned to active status
```

---

## 23. Backend Gaps / Frontend Blockers

The following items represent architectural gaps where frontend capability is blocked or constrained by current backend implementation:

| Item | Status | Impact & Description |
| :--- | :--- | :--- |
| **Simulation Creation Endpoint** | `BLOCKING` | There is no `POST /api/simulations/` HTTP endpoint to create a new simulation with custom agent runtimes via the web. Simulations can currently only be created via the Django admin or CLI (`run_simulation`). |
| **Benchmark HTTP Endpoints** | `BLOCKING` | Benchmark reports, insights, and decision summaries (`BenchmarkDecisionSummary`) are only generated via CLI (`run_benchmark_report`) and are not exposed over HTTP. The frontend cannot build a live benchmark comparison dashboard without this API. |
| **Manual Simulation Stop Endpoint** | `NON-BLOCKING` | A simulation only reaches `completed` automatically when `current_tick >= total_ticks`. There is no `POST /stop/` endpoint to abort a simulation early. |
| **Authentication & RBAC** | `NON-BLOCKING` | All simulation control endpoints are unauthenticated. Suitable for internal sandbox testing, but requires auth for multi-tenant production. |
| **Dynamic World Map Detail** | `FUTURE ENHANCEMENT` | World state currently tracks aggregate counts (`agent_count`, `total_events`) rather than spatial grid coordinates or localized resource nodes. |

---

## 24. Final Frontend Integration Checklist

Frontend developers can use this checklist to track integration readiness:
* [ ] Base API URL configured via environment variable (`NEXT_PUBLIC_API_BASE_URL` / `VITE_API_BASE_URL`).
* [ ] CORS verified with Django backend.
* [ ] Initial snapshot loaded and rendered (`GET /snapshot/`).
* [ ] Monotonic sequence tracking initialized (`lastSequence = snapshot.latest_sequence`).
* [ ] SSE stream connected with reconnection loop (`GET /stream/?after_sequence=N`).
* [ ] Event deduplication guard implemented (`if event.sequence > lastSequence`).
* [ ] Keepalive comments (`: keepalive`) ignored by event parser.
* [ ] Start / Pause / Step control buttons wired to respective `POST` endpoints.
* [ ] HTTP `400 Bad Request` lifecycle errors handled gracefully.
* [ ] Agent cards display live wealth, resources, health, and current actions.
* [ ] Agent detail drawer wired to `GET /agents/{id}/events/`.
* [ ] Activity timeline sorted by `sequence` rather than client timestamp.
* [ ] Auto-reconnection tested under network drop and serverless stream timeout.
