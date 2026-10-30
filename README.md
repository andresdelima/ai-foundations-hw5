# Campus Customs · Multi-Agent Ops Desk (HW5)

An agent team that runs **Campus Customs**, a Yale merch shop on Chapel Street. Open tickets (customer orders, rent notices, discount requests) land on a board. Five PydanticAI agents work them through an MCP server, and a person approves every payment on a React dashboard.

- **MCP server** (`mcp_server/`): FastMCP with 22 tools over `data/campus_customs_new.db`. It's the only way into the shop's data.
- **Backend** (`backend/`): FastAPI plus the agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Any agent can delegate to any other.
- **Dashboard** (`frontend/`): React + Vite + TypeScript. Pick a ticket, watch the agents work live, approve payments and see cash drop.

Every agent uses **`gpt-6-luna` through Portkey**. The model is fixed in `backend/config.py`.

## Shop rules (enforced in code)
- **Today:** "today" is `desk.date_today` (2026-08-31), never the real clock.
- **Lead times:** vendor lead times come from the `vendors` table.
- **Unpaid invoices:** a vendor with an open unpaid invoice won't ship, so restock drafts are refused.
- **Payments:**
  - Every payment needs human approval. Agents can only *request* one.
  - The only route that moves cash is `POST /api/payments/{id}/approve`.
  - A paid request updates `payments`, `cash_accounts`, and `invoices` or `leases`.
- **Cash:** the pay tool refuses anything that would make cash negative. Cash only goes out, because no revenue is modeled.
- **Drafts only:** nothing is emailed and no vendor is contacted. Messages and restock orders stay as drafts on the board.
- **Reset:** reset the working database to the original before a full run (`POST /api/reset` or `--all` in `team.py`).

## Setup

You need **Python 3.12+**, **Node.js 20+** and a **Portkey API key**.

```bash
# 1. API key: copy the example and put your key in it (never commit .env)
cp .env.example .env

# 2. Python packages (backend + MCP server share one environment)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Dashboard packages
cd frontend && npm install && cd ..
```

## Run it, step by step

Run every command from the repo root unless a step says otherwise, with the virtual environment active (`source .venv/bin/activate`).

### 1. Copy the original database to the working copy (for a clean run)

`data/` has two databases:
- **`campus_customs.db`:** the **original**. It's never modified.
- **`campus_customs_new.db`:** the **working copy**. The MCP server, and so every agent and the backend, reads and writes only this file. It's committed in its state after my P9 full run: 3 resolved tickets, $160.00 in checking, 2 approved payments.

To get a clean run, overwrite the working copy with the original:

```bash
cp data/campus_customs.db data/campus_customs_new.db          # macOS / Linux
# copy data\campus_customs.db data\campus_customs_new.db      # Windows
```

Afterwards the shop is back to the start: 3 open tickets, $3,400.00 in checking, no payments and no drafts. The MCP server recreates its two board tables (`payment_requests`, `drafts`) on first use.

### 2. Start the MCP server

The **backend attaches the MCP server in-process**, so you don't need a separate terminal for the app: starting the backend (step 3) starts it too. The server is `mcp_server/server.py` (FastMCP, 22 tools over `data/campus_customs_new.db`).

To run it on its own, for example to test the tools or connect a coding assistant:

```bash
python mcp_server/server.py          # stdio (what .mcp.json uses)
python mcp_server/server.py --http   # HTTP at http://127.0.0.1:8001/mcp
```

`.mcp.json` registers it for a coding assistant as `campus-customs`, running `.venv/bin/python mcp_server/server.py` from the repo root. A standalone copy can read and draft but **can't approve payments**: approval needs a key that only the running backend has.

### 3. Start the FastAPI backend (terminal 1)

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The backend runs at http://localhost:8000, and http://localhost:8000/docs lists every route. It loads `PORTKEY_API_KEY` from `.env`, and every agent runs on `gpt-6-luna`.

### 4. Start the React board (terminal 2)

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board calls the backend at `http://localhost:8000`.

### 5. Reset the database before a full 3-ticket run

Always start a full run from the original data. Any one of these resets it:
- On the board, click **Reset shop**.
- Call `curl -X POST http://localhost:8000/api/reset`.
- Run the `cp` command from step 1 (with the backend stopped).

Reset keeps `output/audit_trail.json` and logs the reset in it. Then work the tickets in order, because they share one cash account:

1. **101:** click **Send in the team**. When the agents ask, type your name under **Signing as** and approve request #1 ($840 for invoice 501). The team goes back in automatically and resolves the ticket.
2. **102:** send in the team, then approve request #2 ($2,400 rent). The follow-up resolves it.
3. **103:** send in the team. There's no payment; the 15% discount is set and the ticket resolves.

Expected cash: **$3,400.00 → $2,560.00 → $160.00 → $160.00**. That should match `cash_accounts.checking` in the working copy.

**Without the UI**, from `backend/`:

```bash
python team.py --all            # resets the DB, then works all open tickets
python team.py --ticket 101     # resets, then works one ticket (add --no-reset to continue)
```

Payments still need a person: approve them through the board or `POST /api/payments/{id}/approve` with `{"approver": "your name"}`.

## API routes

| Route | What it does |
|---|---|
| `GET /api/tickets` | All tickets, open or resolved |
| `POST /api/tickets/{id}/run` | Run the agent team on one ticket |
| `GET /api/tickets/{id}/summary` | What each agent did on that ticket |
| `GET /api/events?since=` | Live agent events (who said what, which tools) |
| `GET /api/payments` | Payment requests and payments made |
| `POST /api/payments/{id}/approve` / `reject` | A person approves (moves cash) or rejects |
| `GET /api/cash` | Checking balance from `cash_accounts` |
| `GET /api/drafts` | Drafts on the board |
| `POST /api/reset` | Reset the working database to the original |

## File layout

```
hw5/
├── AI_prompts.md                 # what I typed to the vibe coder, per problem
├── requirements.txt
├── .env.example                  # PORTKEY_API_KEY placeholder (real .env is not committed)
├── .gitignore
├── .mcp.json                     # registers the MCP server for the vibe coder
├── README.md
├── data/
│   ├── campus_customs.db         # original (for resets)
│   └── campus_customs_new.db     # working copy
├── mcp_server/
│   ├── server.py                 # FastMCP: 22 tools
│   ├── shop_db.py                # database logic + shop rules behind the tools
│   └── README.md
├── frontend/                     # React + Vite + TS dashboard (photos in public/yale, credits.json)
├── backend/
│   ├── main.py                   # FastAPI routes
│   ├── models.py                 # data types
│   ├── agents/                   # boss, inventory, accounting, facilities, customer_service + base (delegation)
│   ├── team.py                   # agent loop (per ticket, follow-ups)
│   ├── shop_client.py            # backend's MCP client
│   ├── audit.py, config.py
│   └── prompts/
│       ├── boss.md
│       ├── inventory.md
│       ├── accounting.md
│       ├── facilities.md
│       ├── customer_service.md
│       └── shared_rules.md       # rules every agent loads
├── docs/prompt_options.md        # the prompt options I chose from (P5)
└── output/
    ├── harness.md                # tables, MCP tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json            # P4 tool tests through MCP
    ├── desk_tickets.html         # plan vs actual per ticket, Cash, Reflection
    ├── design.md                 # dashboard design choices
    ├── resolved_tickets.json
    ├── resolved_board.html       # board screenshots for 101, 102, 103
    ├── audit_trail.json          # every agent-loop step (append-only)
    ├── github_url.txt
    ├── runs/                     # each run saved whole
    └── screenshots/
```

Campus Customs is a class project, not an official Yale site. Photo credits are in `frontend/public/yale/credits.json` and the dashboard footer.
