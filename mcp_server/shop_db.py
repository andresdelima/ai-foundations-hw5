"""Campus Customs database layer, shared by the MCP server and the backend.

Every function works on the working copy data/campus_customs_new.db. The
original data/campus_customs.db is never touched here (the backend copies it to reset).

Shop rules enforced here (in code, not just in prompts):
- "Today" is desk.date_today, never the computer clock.
- Amounts always come from the database (invoice amount, lease rent, unit cost).
- A vendor with an open invoice cannot get a restock order.
- Payments: agents can only request. Only a human decision
  (decide_payment_request, called by the dashboard/backend, never exposed as
  an MCP tool) can approve, and pay_approved_request refuses anything that is
  not approved or would make cash negative.
- Nothing is sent anywhere: messages and restock orders are saved as drafts.
"""

from __future__ import annotations

import calendar
import sqlite3
from contextlib import closing, contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
DB_PATH = ROOT / "data" / "campus_customs_new.db"

TICKET_STATUSES = ("open", "in_progress", "waiting_approval", "blocked", "resolved")
CASH_ACCOUNT = "checking"

# Tables the team adds to the working copy. The original DB never gets these.
BOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- 'invoice' | 'rent'
    ref_id INTEGER NOT NULL,         -- invoices.id or leases.id
    amount REAL NOT NULL,
    payee TEXT NOT NULL,
    reason TEXT,
    ticket_id INTEGER,
    requested_by TEXT NOT NULL,      -- agent name
    status TEXT NOT NULL,            -- pending | approved | rejected | paid
    requested_on TEXT NOT NULL,      -- shop date (desk.date_today)
    decided_by TEXT,                 -- human who approved/rejected
    decided_on TEXT,
    payment_id INTEGER               -- payments.id once paid
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,              -- customer_message | restock_order
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
);
"""


# ------------------------------------------------------------ plumbing ---

@contextmanager
def connect(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    if not path.exists():
        raise FileNotFoundError(f"Working database not found: {path}. Reset it from campus_customs.db first.")
    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(BOARD_SCHEMA)
        with conn:  # commit on success, roll back on error
            yield conn


def _today(conn: sqlite3.Connection) -> date:
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"])


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def _one(conn: sqlite3.Connection, sql: str, *args: Any) -> dict[str, Any] | None:
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _request_for(conn: sqlite3.Connection, kind: str, ref_id: int) -> dict[str, Any] | None:
    """An active (pending/approved) payment request for this invoice or lease, if any."""
    return _one(conn, "SELECT id, status, amount FROM payment_requests WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'approved') ORDER BY id DESC", kind, ref_id)


def _cash(conn: sqlite3.Connection) -> dict[str, Any]:
    acct = _one(conn, "SELECT name, balance, date FROM cash_accounts WHERE name = ?", CASH_ACCOUNT)
    committed = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM payment_requests WHERE status IN ('pending', 'approved')"
    ).fetchone()[0]
    return {
        "account": CASH_ACCOUNT,
        "balance": acct["balance"] if acct else 0.0,
        "as_of": acct["date"] if acct else None,
        "committed_to_requests": round(committed, 2),
        "available_after_requests": round((acct["balance"] if acct else 0.0) - committed, 2),
    }


# --------------------------------------------------------- shop basics ---

def get_shop_date() -> dict[str, Any]:
    with connect() as conn:
        desk = _one(conn, "SELECT date_today, notes FROM desk LIMIT 1")
    return {"today": desk["date_today"], "notes": desk["notes"]}


def list_inventory(sku: str | None = None) -> dict[str, Any]:
    """Every stock row (optionally one SKU) with its pricing, flagging sizes at 0."""
    with connect() as conn:
        sql = """SELECT i.sku, i.name, i.size, i.qty, i.location, p.unit_cost, p.list_price
                 FROM inventory i LEFT JOIN pricing p ON p.sku = i.sku"""
        args: tuple = ()
        if sku:
            sql, args = sql + " WHERE i.sku = ?", (sku.strip().upper(),)
        rows = _rows(conn.execute(sql + " ORDER BY i.sku, i.size", args))
    return {"count": len(rows), "items": rows,
            "out_of_stock": [f"{r['sku']} {r['size']}" for r in rows if r["qty"] == 0]}


def list_leases() -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        rows = _rows(conn.execute("SELECT * FROM leases ORDER BY id"))
    for r in rows:
        r["days_until_due"] = (date.fromisoformat(r["next_due"]) - today).days
    return {"today": today.isoformat(), "leases": rows}


def list_payments() -> dict[str, Any]:
    with connect() as conn:
        rows = _rows(conn.execute("SELECT * FROM payments ORDER BY id"))
    return {"count": len(rows), "payments": rows, "total_paid": round(sum(r["amount"] for r in rows), 2)}


# ----------------------------------------------------------------- P3 ----

def get_vendor_status(vendor_id: int) -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        vendor = _one(conn, "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?", vendor_id)
        if vendor is None:
            return {"found": False, "vendor_id": vendor_id, "message": "No vendor with this id."}
        invoices = _rows(conn.execute(
            "SELECT id, amount, due_date, description FROM invoices WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
            (vendor_id,),
        ))
        open_invoices = [
            {
                "invoice_id": inv["id"],
                "amount": inv["amount"],
                "due_date": inv["due_date"],
                "days_overdue": max(0, (today - date.fromisoformat(inv["due_date"])).days),
                "description": inv["description"],
                # Already set aside? Then the cash for it is committed, not missing.
                "payment_request": _request_for(conn, "invoice", inv["id"]),
            }
            for inv in invoices
        ]
    can_ship = not open_invoices
    return {
        "found": True,
        "today": today.isoformat(),
        "vendor_id": vendor["id"],
        "name": vendor["name"],
        "specialty": vendor["specialty"],
        "lead_days": vendor["lead_days"],
        "can_ship": can_ship,
        "open_invoices": open_invoices,
        "open_balance": round(sum(i["amount"] for i in open_invoices), 2),
        "reason": "No open invoices." if can_ship
        else f"Blocked: {len(open_invoices)} open invoice(s) must be paid before this vendor ships.",
    }


def get_lease_rent(lease_id: int) -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        lease = _one(conn, "SELECT * FROM leases WHERE id = ?", lease_id)
        if lease is None:
            return {"found": False, "lease_id": lease_id, "message": "No lease with this id."}
        accounts = _rows(conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name"))
    days = (date.fromisoformat(lease["next_due"]) - today).days
    return {
        "found": True,
        "today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "days_until_due": days,
        "status": "overdue" if days < 0 else "due today" if days == 0 else "not yet due",
        "notes": lease["notes"],
        "cash_accounts": [
            {"name": a["name"], "balance": a["balance"], "as_of": a["date"],
             "covers_rent": a["balance"] >= lease["monthly_rent"]}
            for a in accounts
        ],
    }


def check_order_fill(sku: str, size: str, qty: int) -> dict[str, Any]:
    sku, size = sku.strip().upper(), size.strip().upper()
    with connect() as conn:
        rows = _rows(conn.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku,)))
        price = _one(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", sku)
    if not rows:
        return {"found": False, "sku": sku, "message": "No inventory rows for this SKU."}
    match = next((r for r in rows if r["size"] == size), None)
    if match is None:
        return {"found": False, "sku": sku, "size": size, "message": "This SKU is not stocked in that size.",
                "sizes_on_hand": {r["size"]: r["qty"] for r in rows}}
    result: dict[str, Any] = {
        "found": True,
        "sku": sku,
        "name": match["name"],
        "size": size,
        "location": match["location"],
        "requested": qty,
        "on_hand": match["qty"],
        "can_fill_from_stock": match["qty"] >= qty,
        "shortfall": max(0, qty - match["qty"]),
        "other_sizes_on_hand": {r["size"]: r["qty"] for r in rows if r["size"] != size},
    }
    if price is None:
        result["pricing"] = None
        result["pricing_message"] = "No pricing row for this SKU."
    else:
        result["pricing"] = {
            "unit_cost": price["unit_cost"],
            "list_price": price["list_price"],
            "margin_per_unit": round(price["list_price"] - price["unit_cost"], 2),
            "order_total_at_list": round(qty * price["list_price"], 2),
            "order_total_at_cost": round(qty * price["unit_cost"], 2),
        }
    return result


# ------------------------------------------------------- discount rule ---

# Shop policy chosen for HW5 (option A): 10% off list at 10+ units, 15% at 20+,
# never below 2x unit_cost. Anything outside this band needs a human.
DISCOUNT_TIERS = ((20, 0.15), (10, 0.10))
PRICE_FLOOR_MULTIPLE = 2.0


def check_discount_policy(sku: str, qty: int, requested_pct: float | None = None) -> dict[str, Any]:
    sku = sku.strip().upper()
    with connect() as conn:
        price = _one(conn, "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", sku)
    if price is None:
        return {"found": False, "sku": sku, "message": "No pricing row for this SKU."}
    tier_pct = next((pct for min_qty, pct in DISCOUNT_TIERS if qty >= min_qty), 0.0)
    floor = round(PRICE_FLOOR_MULTIPLE * price["unit_cost"], 2)
    floor_pct = max(0.0, 1 - floor / price["list_price"])
    max_pct = round(min(tier_pct, floor_pct), 4)
    unit_at_max = round(price["list_price"] * (1 - max_pct), 2)
    result: dict[str, Any] = {
        "found": True,
        "sku": sku,
        "qty": qty,
        "list_price": price["list_price"],
        "unit_cost": price["unit_cost"],
        "policy": "10% off list at 10+ units, 15% at 20+, never below 2x unit cost; outside this needs a human",
        "tier_pct": tier_pct,
        "price_floor": floor,
        "max_pct_allowed": max_pct,
        "unit_price_at_max": unit_at_max,
        "total_at_list": round(qty * price["list_price"], 2),
        "total_at_max": round(qty * unit_at_max, 2),
        "margin_per_unit_at_max": round(unit_at_max - price["unit_cost"], 2),
    }
    if requested_pct is not None:
        pct = requested_pct / 100 if requested_pct > 1 else requested_pct
        unit = round(price["list_price"] * (1 - pct), 2)
        result["requested"] = {
            "pct": round(pct, 4),
            "unit_price": unit,
            "total": round(qty * unit, 2),
            "within_policy": pct <= max_pct + 1e-9,
            "needs_human": pct > max_pct + 1e-9,
        }
    return result


# ------------------------------------------------------------- tickets ---

def list_tickets() -> dict[str, Any]:
    """Every ticket, with its raw status and a simple open/resolved board state."""
    with connect() as conn:
        tickets = _rows(conn.execute(
            "SELECT id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at FROM tickets ORDER BY id"
        ))
    for t in tickets:
        t["board_state"] = "resolved" if t["status"] == "resolved" else "open"
    return {"count": len(tickets), "tickets": tickets,
            "open": sum(t["board_state"] == "open" for t in tickets),
            "resolved": sum(t["board_state"] == "resolved" for t in tickets)}


def list_open_tickets() -> dict[str, Any]:
    with connect() as conn:
        tickets = _rows(conn.execute(
            "SELECT id, type, requester, subject, status, created_at FROM tickets WHERE status != 'resolved' ORDER BY id"
        ))
    return {"count": len(tickets), "tickets": tickets}


def get_ticket(ticket_id: int) -> dict[str, Any]:
    """The ticket plus every row it links to (invoice + vendor, lease, inventory)."""
    with connect() as conn:
        today = _today(conn)
        t = _one(conn, "SELECT * FROM tickets WHERE id = ?", ticket_id)
        if t is None:
            return {"found": False, "ticket_id": ticket_id, "message": "No ticket with this id."}
        linked: dict[str, Any] = {}
        if t["invoice_id"] is not None:
            inv = _one(conn, "SELECT * FROM invoices WHERE id = ?", t["invoice_id"])
            if inv:
                inv["vendor"] = _one(conn, "SELECT * FROM vendors WHERE id = ?", inv["vendor_id"])
                inv["days_overdue"] = max(0, (today - date.fromisoformat(inv["due_date"])).days)
            linked["invoice"] = inv
        if t["lease_id"] is not None:
            linked["lease"] = _one(conn, "SELECT * FROM leases WHERE id = ?", t["lease_id"])
        if t["sku"]:
            linked["inventory"] = _one(conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", t["sku"], t["size"])
            linked["pricing"] = _one(conn, "SELECT * FROM pricing WHERE sku = ?", t["sku"])
        drafts = _rows(conn.execute("SELECT id, kind, recipient, subject, created_by FROM drafts WHERE ticket_id = ?", (ticket_id,)))
        requests = _rows(conn.execute("SELECT id, kind, ref_id, amount, status FROM payment_requests WHERE ticket_id = ?", (ticket_id,)))
    return {"found": True, "today": today.isoformat(), "ticket": t, "linked": linked,
            "drafts": drafts, "payment_requests": requests}


def update_ticket(ticket_id: int, status: str, note: str, actor: str) -> dict[str, Any]:
    if status not in TICKET_STATUSES:
        return {"updated": False, "message": f"status must be one of {TICKET_STATUSES}"}
    with connect() as conn:
        today = _today(conn)
        t = _one(conn, "SELECT notes FROM tickets WHERE id = ?", ticket_id)
        if t is None:
            return {"updated": False, "message": "No ticket with this id."}
        notes = (t["notes"] or "").rstrip() + f"\n[{today} {actor}] {status}: {note.strip()}"
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes.strip(), ticket_id))
    return {"updated": True, "ticket_id": ticket_id, "status": status}


# ------------------------------------------------------- money (read) ---

def get_cash_balance() -> dict[str, Any]:
    with connect() as conn:
        return {"today": _today(conn).isoformat(), **_cash(conn)}


def list_open_invoices() -> dict[str, Any]:
    with connect() as conn:
        today = _today(conn)
        rows = _rows(conn.execute(
            """SELECT i.id, i.vendor_id, v.name AS vendor, i.amount, i.due_date, i.description
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status = 'open' ORDER BY i.due_date"""
        ))
        for r in rows:
            d = (date.fromisoformat(r["due_date"]) - today).days
            r["days_overdue"] = max(0, -d)
            r["status"] = "overdue" if d < 0 else "due today" if d == 0 else f"due in {d} days"
            r["blocks_tickets"] = [x[0] for x in conn.execute(
                "SELECT id FROM tickets WHERE invoice_id = ? AND status != 'resolved'", (r["id"],))]
            r["payment_request"] = _request_for(conn, "invoice", r["id"])
    return {"today": today.isoformat(), "count": len(rows), "invoices": rows,
            "total_open": round(sum(r["amount"] for r in rows), 2)}


def list_vendors() -> dict[str, Any]:
    with connect() as conn:
        return {"vendors": _rows(conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"))}


def list_payment_requests(status: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        sql, args = "SELECT * FROM payment_requests", ()
        if status:
            sql, args = sql + " WHERE status = ?", (status,)
        return {"requests": _rows(conn.execute(sql + " ORDER BY id", args)), **_cash(conn)}


# ------------------------------------------------------ money (write) ---

def request_payment(kind: str, ref_id: int, reason: str, actor: str, ticket_id: int | None = None) -> dict[str, Any]:
    """Create a PENDING payment request. The amount comes from the database.
    Nothing is paid until a human approves it."""
    with connect() as conn:
        today = _today(conn)
        if kind == "invoice":
            inv = _one(conn, "SELECT i.*, v.name AS vendor FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", ref_id)
            if inv is None:
                return {"created": False, "message": "No invoice with this id."}
            if inv["status"] != "open":
                return {"created": False, "message": f"Invoice {ref_id} is '{inv['status']}', not open."}
            amount, payee = inv["amount"], inv["vendor"]
        elif kind == "rent":
            lease = _one(conn, "SELECT * FROM leases WHERE id = ?", ref_id)
            if lease is None:
                return {"created": False, "message": "No lease with this id."}
            amount, payee = lease["monthly_rent"], lease["landlord"]
        else:
            return {"created": False, "message": "kind must be 'invoice' or 'rent'."}

        existing = _one(conn, "SELECT * FROM payment_requests WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'approved')", kind, ref_id)
        if existing:
            return {"created": False, "already_requested": True, "request": existing,
                    "message": f"Request #{existing['id']} for this already exists ({existing['status']})."}

        cash = _cash(conn)
        if amount > cash["available_after_requests"]:
            return {"created": False, "message": "Refused: not enough cash once other pending requests are counted.",
                    "amount": amount, **cash}
        cur = conn.execute(
            """INSERT INTO payment_requests (kind, ref_id, amount, payee, reason, ticket_id, requested_by, status, requested_on)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (kind, ref_id, amount, payee, reason, ticket_id, actor, today.isoformat()),
        )
        req = _one(conn, "SELECT * FROM payment_requests WHERE id = ?", cur.lastrowid)
        cash = _cash(conn)
    return {"created": True, "request": req, "needs_human_approval": True, **cash}


def decide_payment_request(request_id: int, approve: bool, approver: str) -> dict[str, Any]:
    """HUMAN ONLY. Called by the dashboard/backend, never exposed to agents."""
    if not approver.strip():
        return {"decided": False, "message": "An approver name is required."}
    with connect() as conn:
        req = _one(conn, "SELECT * FROM payment_requests WHERE id = ?", request_id)
        if req is None:
            return {"decided": False, "message": "No payment request with this id."}
        if req["status"] != "pending":
            return {"decided": False, "message": f"Request is already {req['status']}."}
        status = "approved" if approve else "rejected"
        conn.execute("UPDATE payment_requests SET status = ?, decided_by = ?, decided_on = ? WHERE id = ?",
                     (status, approver.strip(), _today(conn).isoformat(), request_id))
    return {"decided": True, "request_id": request_id, "status": status, "decided_by": approver.strip()}


def pay_approved_request(request_id: int) -> dict[str, Any]:
    """Pay a request a human already approved. Refuses if it isn't approved or if
    cash would go negative. Updates payments, cash_accounts, and the invoice
    (status -> paid) or lease (next_due -> one month later)."""
    with connect() as conn:
        today = _today(conn)
        req = _one(conn, "SELECT * FROM payment_requests WHERE id = ?", request_id)
        if req is None:
            return {"paid": False, "message": "No payment request with this id."}
        if req["status"] != "approved":
            return {"paid": False, "message": f"Refused: request #{request_id} is '{req['status']}'. A human must approve it on the dashboard first."}
        acct = _one(conn, "SELECT balance FROM cash_accounts WHERE name = ?", CASH_ACCOUNT)
        balance = acct["balance"] if acct else 0.0
        if req["amount"] > balance:
            return {"paid": False, "message": f"Refused: paying ${req['amount']:,.2f} would make {CASH_ACCOUNT} negative (balance ${balance:,.2f})."}

        if req["kind"] == "invoice":
            inv = _one(conn, "SELECT status FROM invoices WHERE id = ?", req["ref_id"])
            if inv is None or inv["status"] != "open":
                return {"paid": False, "message": f"Refused: invoice {req['ref_id']} is no longer open."}
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
            updated = {"invoice_id": req["ref_id"], "invoice_status": "paid"}
        else:
            lease = _one(conn, "SELECT next_due FROM leases WHERE id = ?", req["ref_id"])
            new_due = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
            updated = {"lease_id": req["ref_id"], "paid_period_due": lease["next_due"], "next_due": new_due}

        new_balance = round(balance - req["amount"], 2)
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today.isoformat(), CASH_ACCOUNT))
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], req["ref_id"], req["amount"], CASH_ACCOUNT, today.isoformat(), req["decided_by"]),
        )
        conn.execute("UPDATE payment_requests SET status = 'paid', payment_id = ? WHERE id = ?", (cur.lastrowid, request_id))
    return {"paid": True, "payment_id": cur.lastrowid, "amount": req["amount"], "payee": req["payee"],
            "approved_by": req["decided_by"], "new_balance": new_balance, **updated}


# -------------------------------------------------------------- drafts ---

def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, actor: str) -> dict[str, Any]:
    with connect() as conn:
        if _one(conn, "SELECT id FROM tickets WHERE id = ?", ticket_id) is None:
            return {"saved": False, "message": "No ticket with this id."}
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, kind, recipient, subject, body, created_by, created_on) VALUES (?, 'customer_message', ?, ?, ?, ?, ?)",
            (ticket_id, recipient, subject, body, actor, _today(conn).isoformat()),
        )
    return {"saved": True, "draft_id": cur.lastrowid, "sent": False, "note": "Saved as a draft on the board. Nothing was emailed."}


def draft_restock_order(vendor_id: int, sku: str, size: str, qty: int, actor: str, ticket_id: int | None = None) -> dict[str, Any]:
    sku, size = sku.strip().upper(), size.strip().upper()
    if qty <= 0:
        return {"saved": False, "message": "qty must be positive."}
    status = get_vendor_status(vendor_id)
    if not status["found"]:
        return {"saved": False, "message": "No vendor with this id."}
    if not status["can_ship"]:
        return {"saved": False, "blocked": True, "message": status["reason"], "open_invoices": status["open_invoices"]}
    with connect() as conn:
        today = _today(conn)
        item = _one(conn, "SELECT name FROM inventory WHERE sku = ? AND size = ?", sku, size)
        price = _one(conn, "SELECT unit_cost FROM pricing WHERE sku = ?", sku)
        if item is None or price is None:
            return {"saved": False, "message": "Unknown SKU/size or no pricing row."}
        cost = round(qty * price["unit_cost"], 2)
        eta = date.fromordinal(today.toordinal() + status["lead_days"]).isoformat()
        body = (f"Restock request: {qty} x {item['name']} ({sku}, size {size}). "
                f"Estimated cost {qty} x ${price['unit_cost']:.2f} = ${cost:,.2f}. "
                f"Lead time {status['lead_days']} days -> ETA {eta} if placed {today.isoformat()}.")
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, kind, recipient, subject, body, created_by, created_on) VALUES (?, 'restock_order', ?, ?, ?, ?, ?)",
            (ticket_id, status["name"], f"Restock {sku} {size} x{qty}", body, actor, today.isoformat()),
        )
        cash = _cash(conn)
    return {"saved": True, "draft_id": cur.lastrowid, "vendor": status["name"], "estimated_cost": cost,
            "eta": eta, "sent": False, "note": "Draft only. The vendor was not contacted.",
            "cash_available_after_requests": cash["available_after_requests"],
            "affordable_now": cost <= cash["available_after_requests"]}


def list_drafts(ticket_id: int | None = None) -> dict[str, Any]:
    with connect() as conn:
        sql, args = "SELECT * FROM drafts", ()
        if ticket_id is not None:
            sql, args = sql + " WHERE ticket_id = ?", (ticket_id,)
        return {"drafts": _rows(conn.execute(sql + " ORDER BY id", args))}
