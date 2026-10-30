# Campus Customs — Agent Harness

This file is the agents' map of the shop. It grew with each problem; the sections below are in the order they were built.

## At a glance

| Piece | Where | Details below |
|---|---|---|
| **Database tables** (9 original + 2 board tables) | `data/campus_customs.db` (original, read-only) → `data/campus_customs_new.db` (working copy) | [Database tables](#database-tables), [MCP tools (22) and the tables they use](#mcp-tools-22-and-the-tables-they-use) |
| **MCP server** (22 tools, FastMCP) | `mcp_server/server.py` + `shop_db.py`, registered for the vibe coder in `.mcp.json` | [Full map](#agents-and-mcp-tools-full-map-problem-5-part-2) |
| **Five agents** (Boss, Inventory, Accounting, Facilities, Customer Service) on **gpt-6-luna** via Portkey | `backend/agents/`, prompts in `backend/prompts/`, types in `backend/models.py` | [Agent team](#agent-team-problem-5), [Agents](#agents) |
| **API routes** (FastAPI) | `backend/main.py` → `uvicorn main:app --reload --port 8000` | [Backend routes](#backend-routes-problem-7) |
| **Dashboard** (React + Vite + TS) | `frontend/` → `npm run dev` (http://localhost:5173) | [Dashboard](#dashboard-problem-8), `output/design.md` |
| **Safety rules** | Enforced in `shop_db.py` / `server.py` / `agents/base.py` / `main.py` | [Shop rules enforced in code](#shop-rules-enforced-in-code-not-just-prompts), [Safety](#safety-what-a-real-business-would-want) |
| **Audit trail** | `output/audit_trail.json` (append-only) + `output/runs/` | [Audit trail](#audit-trail) |
| **Full run results** | `output/desk_tickets.html`, `output/resolved_tickets.json`, `output/resolved_board.html` | [Full run](#full-run-problem-9) |

- **Original database:** `data/campus_customs.db`. It is read-only and only used for resets.
- **Working copy:** `data/campus_customs_new.db`. The MCP server and backend read and write this file.

## Database tables

### `desk`
Fields: `date_today`, `notes`

Holds the shop's "today" (2026-08-31). Every overdue or due-soon check uses this date, never the real clock.

### `tickets`
Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id` (→ `leases.id`), `invoice_id` (→ `invoices.id`), `status`, `notes`, `created_at`

The work queue on the board. The Boss reads `type` to route each ticket, and the optional link fields point to the rows each agent needs.

### `inventory`
Fields: `sku`, `name`, `size`, `qty`, `location` (primary key: `sku` + `size`)

Stock on hand by SKU and size. Inventory checks it to see whether an order can be filled and how large any shortfall is.

### `pricing`
Fields: `sku`, `unit_cost`, `list_price`

What each item costs the shop and what it sells for. Used to judge discount requests (margin) and what a restock will cost.

### `vendors`
Fields: `id`, `name`, `specialty`, `lead_days`

Who can restock what, and how many days it takes. Inventory picks a vendor by `specialty` and gives an ETA from `lead_days`.

### `invoices`
Fields: `id`, `vendor_id` (→ `vendors.id`), `amount`, `due_date`, `status`, `description`

Bills the shop owes vendors. A vendor with an `open` invoice won't ship new product, so an unpaid invoice can block a restock.

### `leases`
Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`

The shop space. Facilities uses it to check the rent amount and the due date compared with `desk.date_today`.

### `cash_accounts`
Fields: `name`, `balance`, `date`

The money available to spend (cash only goes out). The pay tool must refuse any payment that would make the balance negative.

### `payments`
Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`

The record of every payment made, starting empty. A row is written only after a human approves, and `approved_by` records who approved it.

## How the 3 open tickets link to other tables

| Ticket | Type | Links | What the data shows |
|---|---|---|---|
| **101**: Tauhid Zaman, "Bulldog tee" | `customer_order` | `sku` CC-TEE-WHITE, `size` S, `qty` 1 → `inventory`; `invoice_id` 501 → `invoices` → `vendors` 1 | Size S stock is **0**, so the order can't be filled now. Apparel restocks come from Bulldog Print Co (lead time 5 days), but invoice 501 for **$840** was due 2026-08-28, is still `open`, and is **3 days overdue**. Until it's paid, the vendor won't ship. |
| **102**: Elm City Properties, "Rent due" | `rent_notice` | `lease_id` 1 → `leases` | Chapel Street shop rent of **$2,400** is due **2026-09-02**, 2 days after today. It's due soon but not overdue. |
| **103**: Yale AI Club, "Bulk hoodie discount" | `price_override` | `sku` CC-HOOD-NAVY, `size` M, `qty` 20 → `inventory`, `pricing` | They want 20 size M hoodies at a bulk discount. Only **8 M** are in stock (32 across all sizes), a shortfall of 12. Unit cost is $22 and list price is $58. A restock would come from Bulldog Print Co, which is also blocked by invoice 501. |

**Cash check:** checking holds **$3,400**. Invoice 501 ($840) plus rent ($2,400) comes to $3,240, which leaves **$160**. Both payments fit, but very little is left after them, for example not enough for a 12-hoodie restock at cost ($264). Any payment still needs human approval first.

## MCP tools (Problem 3)

The server is `mcp_server/server.py` (FastMCP). Every tool reads the working copy `data/campus_customs_new.db` and uses `desk.date_today` as "today".

### `get_vendor_status(vendor_id)`
- **Reads:** `vendors` (name, specialty, `lead_days`), `invoices` (open rows for that vendor), and `desk` (`date_today`).
- **Unlocks:** **Ticket 101**, Tauhid Zaman's size S Bulldog tee.
- **Why it's the right tool:** size S has 0 on hand and the ticket links to invoice 501, so `get_vendor_status(1)` shows Bulldog Print Co can't ship the reprint (`can_ship: false`) because its $840 invoice 501 is 3 days overdue, which tells the agents the order is blocked by an unpaid bill (5-day lead time once paid), not just low stock.

### `get_lease_rent(lease_id)`
- **Reads:** `leases` (rent, landlord, `next_due`), `desk` (`date_today`), and `cash_accounts` (balance).
- **Unlocks:** **Ticket 102**, the Elm City Properties rent notice.
- **Why it's the right tool:** the ticket only gives `lease_id` 1, and `get_lease_rent(1)` turns that into the exact facts Facilities needs: $2,400 rent on the Chapel Street shop, due 2026-09-02 (2 days after 2026-08-31, so not overdue), with $3,400 in checking to cover it.

### `check_order_fill(sku, size, qty)`
- **Reads:** `inventory` (qty and location for that SKU and size, plus its other sizes) and `pricing` (`unit_cost`, `list_price`).
- **Unlocks:** **Ticket 103**, the Yale AI Club request for 20 size M hoodies at a bulk discount. It also confirms ticket 101's shortfall: CC-TEE-WHITE size S has 0 on hand, so 1 is short.
- **Why it's the right tool:** the request asks both "do we have 20 size M?" and "how much discount can we afford?", and `check_order_fill("CC-HOOD-NAVY", "M", 20)` answers both at once: 8 on hand (12 short), $22 cost against a $58 list price, and $1,160 at list versus $440 at cost, which sets the floor for any discount.

## Agent team (Problem 5)

Built with PydanticAI in `backend/`. Every agent runs on **`gpt-6-luna` through Portkey**. The model is set once in `backend/config.py` and can't be overridden. The agents attach the MCP server in-process, and each role only sees the MCP tools on its allowlist. Prompts are in `backend/prompts/`: one file per agent, plus `shared_rules.md`, which every agent loads.

| Agent | File / prompt | Job | MCP tools it can call |
|---|---|---|---|
| **Boss** | `agents/boss.py`, `prompts/boss.md` | Reads each ticket, routes it, decides discounts, makes the final call (`TicketDecision`) | `get_ticket`, `list_open_tickets`, `get_cash_balance`, `list_payment_requests`, `list_drafts`, `check_discount_policy` |
| **Inventory** | `agents/inventory.py`, `prompts/inventory.md` | Stock by SKU and size, shortfalls, vendor match, restock drafts | `get_ticket`, `check_order_fill`, `list_vendors`, `get_vendor_status`, `draft_restock_order` |
| **Accounting** | `agents/accounting.py`, `prompts/accounting.md` | Cash, invoices, payment requests (the only role that requests payments) | `get_ticket`, `get_cash_balance`, `list_open_invoices`, `list_payment_requests`, `request_payment`, `pay_approved_request`, `get_vendor_status`, `get_lease_rent`, `check_order_fill` |
| **Facilities** | `agents/facilities.py`, `prompts/facilities.md` | Lease, rent due date, landlord | `get_ticket`, `get_lease_rent`, `get_cash_balance` |
| **Customer Service** | `agents/customer_service.py`, `prompts/customer_service.md` | Drafts every outgoing message (warm Yale voice, under 120 words) | `get_ticket`, `draft_customer_message`, `list_drafts` |

### Full connectivity and the agent loop
- **Loop:** `backend/team.py` runs the Boss once per open ticket, in id order, because all tickets share one cash account. A full run (`--all`) resets the database first.
- **Delegation:** every agent has `delegate(to, task)` and can reach any of the other four. The specialist's `SpecialistReport` comes back as the tool result.
- **Guardrails (bounded mesh):** at most 3 hops below the Boss and 6 delegations per ticket. An agent can't delegate to itself or to an agent already in the current chain, which prevents A → B → A loops. Each agent run is capped at 8 model requests and 240 seconds.
- **Logging:** every delegation, report, MCP tool call and decision is logged as a `TeamEvent` and saved to `output/runs/run-<time>.json`, together with the token usage.

### Shop rules enforced in code (not just prompts)

| Rule | Where |
|---|---|
| Today = `desk.date_today` | `shop_db._today()` is used by every date calculation |
| Amounts come from the DB | `request_payment` reads the invoice amount or the lease rent; agents can't type an amount |
| A vendor with an open invoice won't ship | `draft_restock_order` refuses while `can_ship` is false |
| Every payment needs human approval | There is no approve tool. `decide_payment_request` is called only by the backend/dashboard with a human name, and `pay_approved_request` refuses anything not `approved` |
| No negative cash | `request_payment` refuses when cash minus pending requests can't cover it; `pay_approved_request` refuses when the balance can't |
| A payment updates the tables | `payments` row (with `approved_by`), `cash_accounts.balance`, `invoices.status = paid` or `leases.next_due` moved forward one month |
| Drafts only | Messages and restock orders go to the `drafts` table and nothing is sent |
| Discount band (10% at 10+, 15% at 20+, floor 2× cost) | `check_discount_policy`, which `team.py` re-checks on the Boss's decision |
| Who acted is accurate | The backend stamps the calling agent's role into `actor` on write tools |

### MCP tools added in Problem 5

| Tool | Reads / writes | Unlocks |
|---|---|---|
| `list_open_tickets`, `get_ticket` | `tickets` + linked `invoices`/`vendors`/`leases`/`inventory`/`pricing` | All three tickets: the Boss's starting point |
| `update_ticket` | writes `tickets.status`, `notes` | Records the Boss's final call (done by the backend) |
| `get_cash_balance` | `cash_accounts`, `payment_requests` | 101/102: what's left after the $840 and $2,400 requests ($160) |
| `list_open_invoices` | `invoices`, `vendors`, `tickets` | 101: invoice 501 is 3 days overdue and blocks ticket 101 |
| `list_vendors` | `vendors` | 101/103: apparel goes to Bulldog Print Co (5-day lead time) |
| `request_payment` | writes `payment_requests` (pending) | 101: invoice 501; 102: lease 1 rent |
| `list_payment_requests` | `payment_requests` | Approval status, and Accounting checks before paying |
| `pay_approved_request` | writes `payments`, `cash_accounts`, `invoices`/`leases` | Runs only after a human approves |
| `check_discount_policy` | `pricing` | 103: 20 hoodies, max 15% = $49.30 each, $986 total, floor $44 |
| `draft_customer_message`, `draft_restock_order`, `list_drafts` | writes/reads `drafts` | 101/103: customer updates; restock once vendor 1 can ship |

The working copy also gets two board tables the original doesn't have: `payment_requests` and `drafts`. They're created on first use and recreated empty on every reset.

### Test runs (Problem 5)
Each run reset the database first. All were on `gpt-6-luna` and saved in `output/runs/`.
- **`run-20261029T211154Z.json`:** ticket 101 only, as a smoke test. Boss → Inventory and Accounting, then Inventory → Accounting, then Boss → Customer Service. The result was payment request #1 ($840, pending) and draft #1.
- **`run-20261029T212331Z.json`:** the first full board. It showed three problems on ticket 103:
  - The discount was priced on 8 units instead of the full 20-unit order. The code check flagged it `within_policy: false`.
  - Accounting called the already-requested invoice "short".
  - Customer Service wrote two drafts.

  The fixes: tool outputs now show existing payment requests, the Boss prompt prices the tier on the full order and sends Customer Service last, and the Customer Service prompt quotes only prices that passed the policy.
- **`run-20261029T212624Z.json`:** the full board after the fixes. All three tickets ended `waiting_approval`:
  - Request #1 is invoice 501 ($840) and request #2 is rent ($2,400). Both are pending human approval.
  - Ticket 103 got 15% on all 20 hoodies: $49.30 each, $986 total, within policy.
  - There is one draft for each customer ticket.
  - No money moved: cash is still $3,400 and the `payments` table is empty.
  - The run used 52 model calls, 139K input tokens and 10K output tokens.

- **`run-20261029T213034Z.json`:** tickets 101 and 103 again, after tightening the Customer Service prompt. The ticket 103 draft from the previous run had told the club a payment "is still pending". Customer messages may no longer mention invoices, payments, cash or approvals, and must reread for those words before saving. Both new drafts say only "waiting on a supplier restock". The 103 draft quotes $49.30 each, $986.00 for all 20, with 8 shipping now.

After testing, the working copy was reset to the original values.

## Agents and MCP tools: full map (Problem 5, part 2)

**One path to the shop:** every shop fact comes from the Campus Customs MCP server, which reads `data/campus_customs_new.db`.
- The agents use the server through PydanticAI's `MCPToolset`.
- The agent loop (`backend/team.py`) uses it through `backend/shop_client.py`, a FastMCP client.
- Both talk to the same in-process server, so nothing in `backend/` opens the database. (`grep shop_db backend/` finds nothing.)
- The only exception is reset: a plain file copy of the original database over the working copy, done before a full run. It reads no shop facts.

**Problem 5 step 1 was fixed in this part:** `team.py` used to call `shop_db` directly to read tickets, write the Boss's decision and check discounts. Those calls now go through MCP tools.

### Agents

| Agent | Role | MCP tools it may call (plus `delegate` to any other agent) |
|---|---|---|
| **Boss** | Reads each ticket, routes it, decides discounts, makes the final call | `get_shop_date`, `get_ticket`, `list_open_tickets`, `get_cash_balance`, `list_payment_requests`, `list_payments`, `list_drafts`, `check_discount_policy` |
| **Inventory** | Stock by SKU and size, shortfalls, vendor match, restock drafts | `get_shop_date`, `get_ticket`, `check_order_fill`, `list_inventory`, `list_vendors`, `get_vendor_status`, `draft_restock_order` |
| **Accounting** | Cash, invoices, payment requests, payment history | `get_shop_date`, `get_ticket`, `get_cash_balance`, `list_open_invoices`, `list_payment_requests`, `request_payment`, `pay_approved_request`, `list_payments`, `get_vendor_status`, `get_lease_rent`, `list_leases`, `check_order_fill` |
| **Facilities** | Lease, rent due date, landlord | `get_shop_date`, `get_ticket`, `get_lease_rent`, `list_leases`, `get_cash_balance` |
| **Customer Service** | Drafts every outgoing message | `get_shop_date`, `get_ticket`, `draft_customer_message`, `list_drafts` |

### MCP tools (22) and the tables they use

| Tool | Tables read | Tables written | Added in |
|---|---|---|---|
| `get_vendor_status` | `vendors`, `invoices`, `desk`, `payment_requests` | none | P3 |
| `get_lease_rent` | `leases`, `desk`, `cash_accounts` | none | P3 |
| `check_order_fill` | `inventory`, `pricing` | none | P3 |
| `list_open_tickets` | `tickets` | none | P5 |
| `get_ticket` | `tickets`, `desk`, `invoices`, `vendors`, `leases`, `inventory`, `pricing`, `drafts`, `payment_requests` | none | P5 |
| `update_ticket` | `tickets`, `desk` | `tickets` (status, notes) | P5 |
| `get_cash_balance` | `cash_accounts`, `payment_requests`, `desk` | none | P5 |
| `list_open_invoices` | `invoices`, `vendors`, `tickets`, `payment_requests`, `desk` | none | P5 |
| `list_vendors` | `vendors` | none | P5 |
| `check_discount_policy` | `pricing` | none | P5 |
| `list_payment_requests` | `payment_requests`, `cash_accounts` | none | P5 |
| `request_payment` | `invoices`, `vendors`, `leases`, `cash_accounts`, `payment_requests`, `desk` | `payment_requests` (pending) | P5 |
| `pay_approved_request` | `payment_requests`, `cash_accounts`, `invoices`, `leases`, `desk` | `payments`, `cash_accounts`, `invoices` or `leases`, `payment_requests` | P5 |
| `draft_customer_message` | `tickets`, `desk` | `drafts` | P5 |
| `draft_restock_order` | `vendors`, `invoices`, `inventory`, `pricing`, `cash_accounts`, `payment_requests`, `desk` | `drafts` | P5 |
| `list_drafts` | `drafts` | none | P5 |
| `get_shop_date` | `desk` | none | P5 part 2 |
| `list_inventory` | `inventory`, `pricing` | none | P5 part 2 |
| `list_leases` | `leases`, `desk` | none | P5 part 2 |
| `list_payments` | `payments` | none | P5 part 2 |
| `list_tickets` | `tickets` | none | P7 |
| `human_decide_payment` | `payment_requests`, `desk` | `payment_requests` (approved or rejected, with approver) | P7 (**human only**: needs the backend's per-start approval key, is on no agent's allowlist, and is blocked in the agent tool hook) |

Every original table now has at least one tool that reads it. `payment_requests` and `drafts` are board tables the MCP server adds to the working copy.

### Audit trail
**What gets recorded:** every agent-loop step is appended to `output/audit_trail.json`, a JSON array that is never wiped. Each entry has:
- `ts`, `run_id`, `ticket_id`, `agent`
- `chain`: who asked whom, for example `["boss", "inventory", "accounting"]`
- `model`: Portkey reports `gpt-6-luna-global`, its deployment name for gpt-6-luna
- `detail`

**Entry kinds:**

| Kind | What it records |
|---|---|
| `run_start`, `run_end` | Tickets, reset info and limits at the start; token totals and final statuses at the end |
| `ticket_start` | The ticket being worked |
| `model_step` | One per model response: the prompt on step 1, the tool calls the model asked for with their arguments, any text, and input/output tokens |
| `tool` | One per MCP call: arguments (with the real `actor` stamped in) and the full result |
| `delegate`, `delegate_refused`, `report` | Who asked whom for what, and what came back |
| `decision` | The Boss's final `TicketDecision` |
| `error` | Request-limit or timeout hits |

**How it's written:** writes are atomic (a temp file, then a swap). If the file is ever damaged, it's set aside rather than overwritten. Each run is also saved whole in `output/runs/run-<run_id>.json`.

## Safety: what a real business would want

This system drafts messages and requests money, so the guardrails matter more than the prompts.

**Money**
- **Built:** a human approves every payment. There's no approve tool and agents only request. The pay tool refuses anything not approved, and anything that would make cash negative.
- **Built:** amounts come from the database, never from the model, so an agent can't pay a made-up amount or pay twice (duplicate requests are refused).
- **For real use:**
  - Two-person approval above a threshold (for example over $1,000), and separation of duties so the requester can't also approve.
  - Daily and per-vendor payment caps.
  - Check vendor bank details against a master list, not against what's on an invoice.
  - Real authentication on the approve button, with the approver's identity coming from the login and not from a typed name.

**Customers**
- **Built:** nothing is sent. Every message is a draft for a human to review.
- **Built:** customer messages can't mention internal money matters.
- **Built:** discounts are capped by policy in code (10% or 15% tiers, floor of 2× cost), and anything outside the band needs a human.
- **For real use:**
  - Human review before sending, then a send log.
  - Rate limits per customer.
  - A PII policy: minimal customer data in prompts, and the audit trail redacted and kept for a set period.
  - A clear way to escalate to a person.

**Data and access**
- **Built:** least privilege. Each agent sees only its allowlisted MCP tools, the backend stamps who acted on every write, and the original database is never modified (reset copies it).
- **For real use:**
  - A read-only database user for read tools.
  - Backups before each run.
  - Alerts on unusual activity, such as many requests in a short time.
  - Prompt-injection screening on free-text ticket notes, which come from outside the shop.

**Token and cost limits**

| Limit | Value | Where |
|---|---|---|
| Model | One cheap model (`gpt-6-luna`) for every agent | Fixed in `config.py` |
| Model requests per agent run | 8 | `REQUEST_LIMIT` |
| Delegations per ticket | 6 | `MAX_DELEGATIONS` |
| Hops below the Boss | 3 | `MAX_DEPTH` |
| Repeat delegation | Not allowed to an agent already in the chain | No ping-pong loops |
| Per model call | 60 s | `MODEL_TIMEOUT_S`, max 2 retries |
| Per agent run | 240 s | `AGENT_TIMEOUT_S` |

- **Efficiency:** tickets run one at a time. Tools return compact JSON instead of whole tables, and `check_discount_policy` does the math so agents don't spend tokens on it.
- **Measured:** a full 3-ticket run is about 50 model calls and 140K input tokens. Token use per step is in the audit trail.
- **For real use:**
  - A per-run token budget that stops the run.
  - Alerts on cost spikes.
  - Caching repeated lookups within a run.

## Backend routes (Problem 7)

Start the backend from `backend/` with `uvicorn main:app --reload --port 8000`. It runs at http://localhost:8000, with interactive docs at `/docs`. Every route reads or writes the shop through the MCP server.

- `GET /api/health`: model, database file, and whether the team is busy right now.
- `GET /api/tickets`: all tickets with their status and whether each is `open` or `resolved`.
- `POST /api/tickets/{id}/run`: runs the agent team on one ticket without resetting. Returns the Boss's decision, delegations and token use. Gives a 409 if a run is already going.
- `GET /api/tickets/{id}/summary`: a short summary of what each agent did on the ticket across every run since the last reset (who asked it, who it asked, what it said, its tools and tokens), plus the Boss's latest call. *(Added in P8 for the dashboard.)*
- `GET /api/events?since=&ticket_id=&run_id=&limit=&current_only=`: recent events from the audit trail, each with a `seq` number and a one-line `summary` (what the agent said, which tool it called, who it delegated to). Poll with `since=last_seq` to refresh the board. By default it only returns events since the latest reset (`current_only=true`).
- `GET /api/payments?status=`: payment requests the agents prepared, payments already made, and the cash picture.
- `POST /api/payments/{request_id}/approve` (body `{"approver": "name"}`): a person approves. This is **the only thing that moves cash**. It also returns `followup_ready` when no other payment on that ticket is waiting, so the dashboard can send the team back to finish the ticket. It records the approval through the human-only MCP tool, then calls `pay_approved_request`. It refuses with a 409 if cash would go negative or the request isn't pending.
- `POST /api/payments/{request_id}/reject` (body `{"approver": "name", "note": "..."}`): a person rejects. No money moves.
- `GET /api/cash`: the current checking balance from `cash_accounts`, plus what pending requests have committed.
- `GET /api/drafts?ticket_id=`: customer messages and restock orders on the board. Nothing is ever sent.
- `POST /api/reset`: copies `campus_customs.db` over the working copy for a fresh run. The audit trail is kept, and the reset is logged in it.

Human approvals, rejections and resets are appended to `output/audit_trail.json` with `agent: "human"` and the approver's name.

**Route test (2026-10-29), from a fresh reset:**
- `POST /api/tickets/101/run` ended `waiting_approval` with request #1 and draft #1. It took 15 model calls.
- While it ran, `/api/events` polls returned 1, then 3, then 21 new events. A second run sent mid-run got a 409.
- **Approve #1:**
  - It paid $840 to Bulldog Print Co and checking went from $3,400 to $2,560.
  - It wrote a `payments` row with `approved_by` and set invoice 501 to `paid`.
  - Approving #1 a second time got a 409.
- **Reject:** a test rent request was rejected with no money moved.
- **Overdraft:** approving $2,400 with only $100 in checking was refused, and the cash stayed at $100.
- **No key:** a keyless approval through the stdio MCP server was refused.
- **Reset:** the database is back to $3,400 with all three tickets open.

## Dashboard (Problem 8)

`frontend/` is React + Vite + TypeScript. Start it with `npm run dev` at http://localhost:5173. It calls the routes above at `http://localhost:8000`. The design choices are in `output/design.md`.

**Backend changes for the board:**
- **Final calls:** the Boss's final status can only be `waiting_approval`, `blocked` or `resolved`, enforced in `TicketDecision`.
- **What resolved means:** nothing is waiting on a person, the payments are **paid**, and the drafts are saved. Drafts count as finished work, because sending them is a person's job.
- **Follow-up runs:** when a ticket already has payment requests or drafts, the Boss is told it's a follow-up and finishes only what's left.

**Browser test (2026-10-29), starting from a reset:**
- **Ticket 101:**
  - It went to *Needs your signature* with request #1 ($840).
  - Approving it dropped checking from $3,400 to $2,560.
  - The automatic follow-up had Inventory draft the restock (draft #2, ETA 2026-09-05) and Customer Service write an updated message (draft #3).
  - "Run again" then had the Boss close it as **resolved** in 2 model calls.
- **Ticket 102:**
  - It went Boss → Facilities → Accounting, matching the P6 plan, and stopped at request #2 ($2,400).
  - That approval is left for a person to sign on the board.

## Full run (Problem 9)

**Setup:**
- Reset `data/campus_customs_new.db` through `POST /api/reset`. The **starting checking balance was $3,400.00**.
- All three tickets ran from the React board on gpt-6-luna, and every run was appended to `output/audit_trail.json` (entries after #275).
- Prompt change before the run: a `price_override` ticket now resolves once the discount is decided within policy and the customer has an accurate draft. If cash can't cover the restock, the Boss records the gap in the note instead of blocking.

| Ticket | Runs | First call | Human approval | Cash | Final |
|---|---|---|---|---|---|
| 101 Bulldog tee | first + follow-up (26 calls) | Inventory | #1: $840.00 to Bulldog Print Co (invoice 501), by AdL | $3,400.00 → $2,560.00 | resolved |
| 102 Rent due | first + follow-up (20 calls) | Facilities | #2: $2,400.00 to Elm City Properties (rent, lease 1), by AdL | $2,560.00 → $160.00 | resolved |
| 103 Hoodie discount | one (25 calls) | Inventory | none (no payment) | $160.00 → $160.00 | resolved |

**Ending checking: $160.00.** That's $3,400 − $840 − $2,400, and it matches `cash_accounts.checking`. The `payments` table has 2 rows totaling $3,240.00, both `approved_by = AdL`. The run used **71 model calls**, 207,894 input tokens and 16,609 output tokens.

**Plan vs actual** (details on each ticket tab of `desk_tickets.html`):
- **First calls:** all three matched the plan: Inventory, Facilities, Inventory.
- **Ticket 102:** the Boss routed the rent to Accounting itself, instead of Facilities handing it over as planned.
- **Ticket 103:** Customer Service added three peer cross-checks, using all 6 allowed delegations.
- **Follow-ups:** follow-up runs after each approval took 101 and 102 past *waiting_approval* to *resolved*. The plan had stopped at waiting.

**Known issue found in this run:** on 102's follow-up, Facilities saw `next_due` already moved to 2026-10-02, because paying the rent moves it forward one month. It read that as a conflict with the notice's 09-02 date, and Customer Service drafted a landlord note asking to confirm the date (draft #4). No money was affected and nothing was sent. The fix: `get_lease_rent` should also show the last rent payment and the period it covered.

**Saved:**
- `output/desk_tickets.html`: Actual sections and Cash tab
- `output/resolved_tickets.json`: per ticket, status, outcome, each agent's contribution, human approvals and cash
- `output/resolved_board.html`: screenshots of the board for 101, 102 and 103 (also in `output/screenshots/`)
