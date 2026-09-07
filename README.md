# Agent Research Sandbox

An experimental research and benchmarking platform for studying autonomous AI agents, multi-agent economic interactions, and emergent behavior inside controlled virtual simulations.

---

## Overview

The **Agent Research Sandbox** provides a complete infrastructure for running, observing, and evaluating multi-agent systems. It integrates deterministic and LLM-powered agent runtimes, real-time activity ledgers, state-machine simulation lifecycles, and automated benchmark evaluation suites.

The platform is designed with a **database-first architecture**, making it fully compatible with serverless backend environments (such as Vercel) while supporting continuous worker execution for simulation runs.

---

## Key Features & Architecture (Steps 28–33)

```text
       Vercel Frontend / UI Client
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   REST APIs            SSE Stream
 (Snapshot / Events)  (Live Activity)
        │                   │
        └─────────┬─────────┘
                  ▼
          Django API Layer
       (CORS / JSON Error Shield)
                  │
                  ▼
        Simulation Controller
       (One-Tick Atomic Locking)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
  Agent Runtimes     World Environment
(Rule/Random/LLMs)   (Trades/Resources)
        │                   │
        └─────────┬─────────┘
                  ▼
           Activity Tracker
       (Monotonic Sequence Engine)
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
 Authoritative DB      In-Memory Pub/Sub
 (ActivityEvent Ledger) (Live SSE Delivery)
```

### 1. Real-Time Activity Ledger & State Tracking
* **Append-Only Event Ledger:** Every observation, decision, action, message, trade, and resource change is recorded in the `ActivityEvent` database table with a globally unique, strictly monotonic `sequence` integer per simulation.
* **Synchronized Agent Snapshots:** `AgentState` records mirror live agent wealth, health, and inventory updates in lockstep with committed events.
* **Secret Sanitization:** Built-in recursive sanitization purges sensitive credentials (`api_key`, `token`, `secret`, `password`) before database persistence or client broadcast.

### 2. Multi-Engine Agent Runtimes
* **Rule-Based Runtimes (`rule`):** Archetype-driven heuristic strategies (`wealth`, `survival`, `cooperative`).
* **Random Walk Runtime (`random`):** Uniform stochastic action selection for baseline benchmarking.
* **LLM Runtimes (`llm`):** Direct integrations with **Groq** (`llama3-70b-8192`) and **xAI** (`grok-beta`), plus an offline `deterministic` simulator for unit tests.
* **Failure Isolation:** Provider timeouts, rate limits, or network errors are isolated per agent. Failed calls safely fall back to `action="wait"` and record error traces without crashing or halting the simulation.

### 3. Production Simulation Orchestration
* **One-Tick Atomicity:** Row-level database locking (`select_for_update()`) inside atomic transactions prevents concurrent workers or duplicate API requests from executing the same tick.
* **Finite-State Machine (FSM):** Strict state transition guarantees (`created` $\to$ `running` $\to$ `paused` $\to$ `completed`) with automated auto-completion when `current_tick >= total_ticks`.
* **Worker Execution Pattern:** Continuous background worker loops via `SimulationController.run_to_completion()`.
* **Vercel & Serverless Middleware:** Includes `SimpleCORSMiddleware` for cross-origin frontend requests, `JSONNotFoundMiddleware` (API 404s to JSON), and `JSONServerErrorMiddleware` (safe 500 error shields).

### 4. Benchmark Analytics & Decision Engine
* **Multi-Scenario Suites:** Evaluates agents across diverse market scenarios (`baseline_market`, `resource_scarcity`, `collaborative_commons`).
* **Analytical Insights:** Calculates wealth distributions, Gini inequality coefficients, trade volumes, LLM latency profiles, and token efficiency.
* **Decision Summaries:** Formulates deterministic, non-causal recommendation summaries with structured tie-breaking (`BenchmarkDecisionSummary`).

---

## API Summary

The backend exposes a clean REST and Server-Sent Events API mounted at `/api/simulations/` (trailing slash mandatory):

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/simulations/{id}/snapshot/` | Returns the complete simulation, world state, `latest_sequence`, and agent vital signs. |
| `GET` | `/api/simulations/{id}/events/` | Query historical event ledger with sequence-based replay (`after_sequence`, `limit`). |
| `GET` | `/api/simulations/{id}/agents/{agent_id}/events/` | Query historical event ledger filtered for a single agent. |
| `POST` | `/api/simulations/{id}/start/` | Starts or resumes simulation execution. |
| `POST` | `/api/simulations/{id}/pause/` | Pauses a running simulation. |
| `POST` | `/api/simulations/{id}/step/` | Atomically executes exactly 1 simulation tick across all agents. |
| `GET` | `/api/simulations/{id}/stream/` | Real-time Server-Sent Events (SSE) stream supporting reconnect replay. |

📖 For the full integration guide, payload schemas, and frontend code examples, refer to [**`docs/FRONTEND_API_CONTRACT.md`**](docs/FRONTEND_API_CONTRACT.md).

---

## Management Commands & CLI Tools

### Run a Simulation Worker
Execute a simulation continuously to completion using the background worker command:
```bash
python manage.py run_simulation --name "Market-Test" --ticks 50 --agent-runtimes "rule,random" --seed 42
```

### Generate Benchmark Reports
Run the comprehensive benchmark evaluation and export charts and analytical decision summaries:
```bash
python manage.py run_benchmark_report --output-dir reports
```
Outputs `reports/report.json` and metric visualization plots (`wealth.png`, `trade_volume.png`, etc.).

---

## Local Development Setup

### 1. Prerequisites
* Python 3.11 or higher
* Git

### 2. Installation
Clone the repository and set up a virtual environment:
```bash
git clone https://github.com/SudipBera083/agent-research-sandbox.git
cd ai-agent-sandbox

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory:
```env
DEBUG=True
SECRET_KEY=your-development-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Optional LLM API Keys (for live LLM agent testing)
GROQ_API_KEY=your_groq_api_key_here
XAI_API_KEY=your_xai_api_key_here
```

### 4. Database Setup & Migrations
```bash
python manage.py migrate
```

### 5. Run the Development Server
```bash
python manage.py runserver
```
The API will be available at `http://127.0.0.1:8000/api/simulations/`.

---

## Testing & Quality Assurance

The codebase features an automated test suite with 100% pass rates across unit, integration, and orchestration layers:

```bash
# Run the entire test suite
python manage.py test

# Run specific test modules
python manage.py test experiments.tests.test_orchestration
python manage.py test experiments.tests.test_simulation_api
python manage.py test experiments.tests.test_simulation_stream
python manage.py test experiments.tests.test_runtime_integration
python manage.py test experiments.tests.test_decision_summary
```

System verification checks:
```bash
python manage.py check
python manage.py makemigrations --check --dry-run
git diff --check
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.