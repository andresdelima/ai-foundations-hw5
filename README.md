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

Both databases are included in `data/`:
- `campus_customs.db`: the **original**. Never modified, and used for resets.
- `campus_customs_new.db`: the **working copy**. It's committed in its state after the P9 full run (3 resolved tickets, $160.00 in checking, 2 approved payments). Click **Reset shop** on the board, or call `POST /api/reset`, to start fresh from $3,400.00.

## Run

**Terminal 1: backend** (http://localhost:8000, docs at `/docs`)
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2: dashboard** (http://localhost:5173)
```bash
cd frontend
npm run dev
```

On the board:
1. Click **Reset shop**.
2. Pick a ticket and click **Send in the team**.
3. Type your name under **Signing as**, then **Approve & pay** when the agents ask.

After you approve, the team goes back in automatically to finish the ticket.

**Without the UI**, from `backend/`:
```bash
python team.py --all            # reset, then work every open ticket
python team.py --ticket 101     # reset, then work one ticket
```

**The MCP server in a coding assistant:** `.mcp.json` registers it as `campus-customs`. It runs `.venv/bin/python mcp_server/server.py` from the repo root. Agents and assistants can't approve payments: that tool needs a key that only the running backend has.

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
