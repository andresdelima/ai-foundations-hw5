# Campus Customs MCP server

This is the shared toolbox for the Campus Customs operations team. Every agent (Boss, Inventory, Facilities and Customer Service) gets its facts about the shop from these tools, so all of them read the same data in the same way. The server is built with [FastMCP](https://gofastmcp.com) and lives in `server.py`.

## Database

- **Working copy:** `../data/campus_customs_new.db`. All tools read this file, and later tools will write to it.
- **Original:** `../data/campus_customs.db`. It stays untouched so the shop can be reset by copying it over the working copy.
- **Today:** always `desk.date_today` from the database, not the computer's clock.
- **No invented data:** tools only return values that are in the database. If a vendor, lease or SKU doesn't exist, the tool returns `found: false` instead of guessing.

## Tools (22)

The logic and the shop rules live in `shop_db.py`, and `server.py` exposes them as tools. The backend has no other way into the database: its agents use these tools through PydanticAI's `MCPToolset`, and its agent loop uses them through a FastMCP client.

| Tool | Inputs | Reads | Writes |
|---|---|---|---|
| `get_shop_date` | none | `desk` | none |
| `list_tickets` | none | `tickets` (all, with open/resolved) | none |
| `list_open_tickets` | none | `tickets` | none |
| `get_ticket` | `ticket_id` | `tickets` + linked `invoices`, `vendors`, `leases`, `inventory`, `pricing`, plus `drafts`, `payment_requests` | none |
| `update_ticket` | `ticket_id`, `status`, `note` | `tickets`, `desk` | `tickets` |
| `check_order_fill` | `sku`, `size`, `qty` | `inventory`, `pricing` | none |
| `list_inventory` | `sku` (optional) | `inventory`, `pricing` | none |
| `check_discount_policy` | `sku`, `qty`, `requested_pct` (optional) | `pricing` | none |
| `list_vendors` | none | `vendors` | none |
| `get_vendor_status` | `vendor_id` | `vendors`, `invoices`, `payment_requests`, `desk` | none |
| `get_lease_rent` | `lease_id` | `leases`, `cash_accounts`, `desk` | none |
| `list_leases` | none | `leases`, `desk` | none |
| `get_cash_balance` | none | `cash_accounts`, `payment_requests` | none |
| `list_open_invoices` | none | `invoices`, `vendors`, `tickets`, `payment_requests` | none |
| `list_payment_requests` | `status` (optional) | `payment_requests`, `cash_accounts` | none |
| `list_payments` | none | `payments` | none |
| `request_payment` | `kind` (`invoice`/`rent`), `ref_id`, `reason`, `ticket_id` | `invoices`, `leases`, `cash_accounts`, `payment_requests` | `payment_requests` (**pending**) |
| `pay_approved_request` | `request_id` | `payment_requests`, `cash_accounts`, `invoices`, `leases` | `payments`, `cash_accounts`, `invoices`/`leases`, `payment_requests` |
| `draft_customer_message` | `ticket_id`, `recipient`, `subject`, `body` | `tickets` | `drafts` |
| `draft_restock_order` | `vendor_id`, `sku`, `size`, `qty`, `ticket_id` | `vendors`, `invoices`, `inventory`, `pricing`, `cash_accounts` | `drafts` |
| `list_drafts` | `ticket_id` (optional) | `drafts` | none |
| `human_decide_payment` | `request_id`, `approve`, `approver`, `approval_key` | `payment_requests` | `payment_requests` (approved/rejected) — **human only** |

**Rules enforced in these tools:**
- **Payments:** `request_payment` takes the amount from the database and refuses duplicates or anything cash can't cover. `pay_approved_request` refuses anything a human hasn't approved, and anything that would make cash negative.
- **Restocks:** `draft_restock_order` refuses while the vendor has an open invoice.
- **Who acted:** write tools take an `actor`, which the backend fills in with the calling agent's role.

**Human-only approval:** agents never approve. `human_decide_payment` refuses unless it gets the approval key the backend generates on each start (environment variable `CC_HUMAN_APPROVAL_KEY`). Only the backend's approve and reject routes send that key, after a person clicks the button and gives their name. The tool is also on no agent's allowlist and is blocked in the backend's agent tool hook. A separate copy of this server started over stdio has no key, so it can't approve anything.

**Board tables:** `payment_requests` and `drafts` are created in the working copy on first use. **Resetting** isn't a tool: the backend copies the original `campus_customs.db` over the working copy before a full run.

## Run

You don't need to run it by hand. The backend will attach it later.

```bash
.venv/bin/python mcp_server/server.py          # stdio
.venv/bin/python mcp_server/server.py --http   # http://127.0.0.1:8001/mcp
```
