"""Campus Customs MCP server — the shared toolbox for every agent in HW5.

All tools work on the working copy data/campus_customs_new.db (never the
original campus_customs.db, which is kept untouched for resets). "Today" is
always desk.date_today from the database, not the computer's clock. The
database logic and the shop rules live in shop_db.py.

Tools only report what is in the database. When a row doesn't exist they say
so instead of guessing. There is deliberately NO approve tool: approving a
payment is a human action on the dashboard.

Run (stdio):  python mcp_server/server.py
Run (HTTP):   python mcp_server/server.py --http   ->  http://127.0.0.1:8001/mcp
"""

from __future__ import annotations

import argparse
import hmac
import os
import sys
from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shop_db  # noqa: E402

mcp = FastMCP("campus-customs")

# ----------------------------------------------------- P3: ticket tools ---

@mcp.tool
def get_vendor_status(vendor_id: int) -> dict[str, Any]:
    """Can this vendor ship right now? Returns the vendor's specialty and lead time,
    its open (unpaid) invoices with days overdue versus desk.date_today, and
    can_ship = false while any invoice is still open (vendors don't ship with
    an unpaid invoice outstanding).

    Use for: restock questions, e.g. ticket 101 (vendor 1, invoice 501).
    """
    return shop_db.get_vendor_status(vendor_id)


@mcp.tool
def get_lease_rent(lease_id: int) -> dict[str, Any]:
    """Rent status for a lease: monthly rent, landlord, next due date, days until
    due (negative = overdue) versus desk.date_today, and the cash account
    balances so you can see whether the rent can be covered. Read-only — it
    does not pay anything.

    Use for: rent notices, e.g. ticket 102 (lease 1).
    """
    return shop_db.get_lease_rent(lease_id)


@mcp.tool
def check_order_fill(sku: str, size: str, qty: int) -> dict[str, Any]:
    """Can we fill an order of `qty` units of a SKU in one size from stock?
    Returns units on hand, the shortfall, stock in the SKU's other sizes, and
    the SKU's unit cost and list price with order totals at cost and at list
    (for judging discount requests).

    Use for: customer orders and bulk/discount requests, e.g. ticket 101
    (CC-TEE-WHITE, S, 1) and ticket 103 (CC-HOOD-NAVY, M, 20).
    """
    return shop_db.check_order_fill(sku, size, qty)


@mcp.tool
def check_discount_policy(sku: str, qty: int, requested_pct: float | None = None) -> dict[str, Any]:
    """The shop's bulk-discount rule applied to a SKU and quantity: 10% off list
    at 10+ units, 15% at 20+, never below 2x unit cost. Returns the largest
    discount allowed, the price floor and the totals. Pass requested_pct
    (e.g. 15) to check a specific discount; anything above the band needs a human.

    Use for: discount requests, e.g. ticket 103 (CC-HOOD-NAVY, 20 units).
    """
    return shop_db.check_discount_policy(sku, qty, requested_pct)


# ---------------------------------------------------------- shop basics ---

@mcp.tool
def get_shop_date() -> dict[str, Any]:
    """The shop's 'today' (desk.date_today) and desk notes. Use this date, never the real clock."""
    return shop_db.get_shop_date()


@mcp.tool
def list_inventory(sku: str | None = None) -> dict[str, Any]:
    """All stock rows (or one SKU) with qty, shelf location, unit cost and list price,
    plus a list of SKU/sizes at 0 — for spotting shortfalls beyond a single ticket."""
    return shop_db.list_inventory(sku)


@mcp.tool
def list_leases() -> dict[str, Any]:
    """Every lease with rent, landlord, next_due and days until due (vs desk.date_today)."""
    return shop_db.list_leases()


@mcp.tool
def list_payments() -> dict[str, Any]:
    """Payments already made (each with who approved it) and the total paid."""
    return shop_db.list_payments()


# ------------------------------------------------------------ the board ---

@mcp.tool
def list_tickets() -> dict[str, Any]:
    """Every ticket on the board (open and resolved) with its status and board_state."""
    return shop_db.list_tickets()


@mcp.tool
def list_open_tickets() -> dict[str, Any]:
    """Every ticket on the board that is not resolved (id, type, requester, subject, status)."""
    return shop_db.list_open_tickets()


@mcp.tool
def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket with every row it links to: invoice (+ vendor, days overdue),
    lease, inventory row and pricing for its SKU/size, plus drafts and payment
    requests already made for it."""
    return shop_db.get_ticket(ticket_id)


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"],
    note: str,
    actor: str = "agent",
) -> dict[str, Any]:
    """Set a ticket's status and append a dated note (the decision and why).
    `actor`: who is acting (agent name); the backend fills this in automatically."""
    return shop_db.update_ticket(ticket_id, status, note, actor)


# ---------------------------------------------------------------- money ---

@mcp.tool
def get_cash_balance() -> dict[str, Any]:
    """Cash in the checking account, how much is already committed to pending or
    approved payment requests, and what is available after those. Cash only
    goes out — no revenue is modeled."""
    return shop_db.get_cash_balance()


@mcp.tool
def list_open_invoices() -> dict[str, Any]:
    """All unpaid vendor invoices with vendor name, amount, due date, days overdue
    (versus desk.date_today) and which open tickets each one blocks."""
    return shop_db.list_open_invoices()


@mcp.tool
def list_vendors() -> dict[str, Any]:
    """All vendors with their specialty and lead_days (restock lead time)."""
    return shop_db.list_vendors()


@mcp.tool
def list_payment_requests(status: Literal["pending", "approved", "rejected", "paid"] | None = None) -> dict[str, Any]:
    """Payment requests on the board (optionally filtered by status) plus the cash picture."""
    return shop_db.list_payment_requests(status)


@mcp.tool
def request_payment(
    kind: Literal["invoice", "rent"],
    ref_id: int,
    reason: str,
    ticket_id: int | None = None,
    actor: str = "agent",
) -> dict[str, Any]:
    """Ask a human to approve a payment. This does NOT pay anything.
    kind='invoice' -> ref_id is invoices.id; kind='rent' -> ref_id is leases.id.
    The amount is taken from the database. Refused if the invoice isn't open,
    if a request already exists, or if cash minus other pending requests can't
    cover it. `actor`: who is acting (agent name); the backend fills this in automatically."""
    return shop_db.request_payment(kind, ref_id, reason, actor, ticket_id)


@mcp.tool
def pay_approved_request(request_id: int) -> dict[str, Any]:
    """Pay a request that a HUMAN has already approved on the dashboard. Refuses
    if the request is not approved, or if cash would go negative. On success it
    writes a payments row, lowers the cash balance, and marks the invoice paid
    (or moves the lease's next_due forward one month)."""
    return shop_db.pay_approved_request(request_id)


# ------------------------------------------------------- human only ---

# The backend sets this to a fresh random secret every time it starts and only
# its approve/reject routes send it. Agents never see it (and the tool is not on
# any agent's allowlist); a separate stdio copy of this server has no key at
# all, so it can never approve anything.
APPROVAL_KEY_ENV = "CC_HUMAN_APPROVAL_KEY"


@mcp.tool
def human_decide_payment(request_id: int, approve: bool, approver: str, approval_key: str) -> dict[str, Any]:
    """HUMAN ONLY — records a person's approve/reject decision from the dashboard.
    Agents must never call this. Requires the dashboard's approval key and the
    approver's name. Approving does not pay; pay_approved_request does that."""
    expected = os.getenv(APPROVAL_KEY_ENV, "")
    if not expected or not hmac.compare_digest(expected, approval_key or ""):
        return {"decided": False, "message": "Refused: approvals can only come from a human on the dashboard."}
    return shop_db.decide_payment_request(request_id, approve, approver)


# --------------------------------------------------------------- drafts ---

@mcp.tool
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, actor: str = "agent") -> dict[str, Any]:
    """Save a message for a customer (or landlord) as a DRAFT on the board.
    Nothing is emailed. `actor`: who is acting (agent name); the backend fills this in automatically."""
    return shop_db.draft_customer_message(ticket_id, recipient, subject, body, actor)


@mcp.tool
def draft_restock_order(
    vendor_id: int, sku: str, size: str, qty: int, ticket_id: int | None = None, actor: str = "agent"
) -> dict[str, Any]:
    """Save a restock order for a vendor as a DRAFT (the vendor is not contacted).
    Refused while the vendor has an open invoice. Cost = qty x unit_cost and
    ETA = desk.date_today + vendor lead_days. `actor`: who is acting (agent name); the backend fills this in automatically."""
    return shop_db.draft_restock_order(vendor_id, sku, size, qty, actor, ticket_id)


@mcp.tool
def list_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """Drafts on the board (customer messages and restock orders), optionally for one ticket."""
    return shop_db.list_drafts(ticket_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument("--http", action="store_true", help="serve over HTTP instead of stdio")
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8001)
    else:
        mcp.run()
