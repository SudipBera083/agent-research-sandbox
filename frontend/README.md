# Agent Research live simulation frontend

This React/Vite application consumes the Step 33 simulation contract.

## Run locally

```bash
npm ci
npm run dev
```

Set `VITE_API_BASE_URL` to the backend origin, for example:

```text
https://api.example.com
```

The frontend appends the documented `/api/simulations/` routes. It does not append `/api/benchmarks`.

## Live behavior

The app loads a simulation snapshot, replays events after the snapshot sequence, and opens an SSE stream. Events are deduplicated and sorted by the backend `sequence` value. Sequence gaps are recovered from the event ledger, and serverless stream disconnects reconnect with exponential backoff.

The controls call the documented `start`, `pause`, and `step` POST endpoints. Agent cards, decision traces, inventories, the activity ledger, and agent-specific event history are rendered only from backend data.

## Verification

```bash
npm test
npm run build
```

The backend must enable CORS for the deployed frontend origin and expose the Step 33 routes. The current supplied Vercel backend URL serves Django's default page and returns 404 for `/api/simulations/1/snapshot/`, so the dashboard shows a truthful connection error until those routes are deployed.
