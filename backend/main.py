"""Campus Customs backend: the routes the React dashboard calls.

    cd backend
    uvicorn main:app --reload --port 8000        ->  http://localhost:8000  (docs at /docs)

Every shop read/write goes through the Campus Customs MCP server (shop_client.call).
Agents only *prepare* payments; the approve route is the only thing that moves cash,
and it only runs when a person clicks Approve and gives their name.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import audit
import config
from shop_client import call, reset_working_copy
from team import run_board

# A fresh secret per server start. Only the approve/reject routes send it to the
# MCP server's human-only tool; agents never see it.
os.environ["CC_HUMAN_APPROVAL_KEY"] = secrets.token_urlsafe(32)
APPROVAL_KEY = os.environ["CC_HUMAN_APPROVAL_KEY"]

app = FastAPI(title="Campus Customs operations backend", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# One agent run at a time: tickets share one cash account.
_run_lock = asyncio.Lock()


class Decision(BaseModel):
    approver: str = Field(min_length=1, description="Name of the person clicking Approve/Reject.")
    note: str | None = None


def _human_event(kind: str, detail: dict[str, Any], ticket_id: int | None = None) -> None:
    """Human actions go in the same append-only audit trail as agent steps."""
    audit.append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "run_id": "", "ticket_id": ticket_id, "kind": kind, "agent": "human",
        "chain": [], "to": None, "model": None, "detail": detail,
    })


def _summary(e: dict[str, Any]) -> str:
    """One readable line per event, for the board."""
    d, k = e.get("detail") or {}, e.get("kind")
    if k == "model_step":
        calls = ", ".join(c["tool"] for c in d.get("tool_calls", []))
        return (d.get("text") or "") + (f" [calls: {calls}]" if calls else "")
    if k == "tool":
        args = ", ".join(f"{a}={v}" for a, v in (d.get("args") or {}).items() if a != "actor")
        return f"{d.get('tool')}({args})"
    if k in ("delegate", "delegate_refused"):
        return d.get("task", "") + (f" — refused: {d['reason']}" if k == "delegate_refused" else "")
    if k == "report":
        return d.get("summary", "")
    if k == "decision":
        return f"{d.get('status')}: {d.get('decision', '')}"
    if k in ("human_approve", "human_reject", "reset"):
        return d.get("message", "")
    if k == "error":
        return d.get("error", "")
    if k == "ticket_start":
        return f"Picked up ticket #{e.get('ticket_id')}: {d.get('subject', '')} from {d.get('requester', '')}"
    if k == "run_start":
        return f"Run started on tickets {d.get('tickets')}"
    if k == "run_end":
        return f"Run finished: {d.get('statuses')}"
    return json.dumps(d)[:200]


def _audit_rows() -> list[dict[str, Any]]:
    if not config.AUDIT_TRAIL.exists():
        return []
    return json.loads(config.AUDIT_TRAIL.read_text(encoding="utf-8") or "[]")


def _since_last_reset(rows: list[dict[str, Any]]) -> int:
    """Sequence number of the latest reset (0 if none). Events before it belong to an older shop state."""
    for seq in range(len(rows), 0, -1):
        if rows[seq - 1].get("kind") == "reset":
            return seq
    return 0


# ------------------------------------------------------------------- routes ---

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "model": config.MODEL_NAME, "database": config.WORKING_DB.name,
            "agent_running": _run_lock.locked()}


@app.get("/api/tickets")
async def tickets() -> dict[str, Any]:
    """All tickets with status and whether each is open or resolved."""
    return await call("list_tickets")


@app.post("/api/tickets/{ticket_id}/run")
async def run_ticket(ticket_id: int) -> dict[str, Any]:
    """Run the agent team on one ticket (no reset). Poll /api/events while it runs."""
    found = await call("get_ticket", ticket_id=ticket_id)
    if not found.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}")
    if _run_lock.locked():
        raise HTTPException(409, "The team is already working a ticket. Try again when it finishes.")
    async with _run_lock:
        run = await run_board([ticket_id], reset=False)
    t = run["tickets"][0]
    return {"run_id": run["run_id"], "ticket_id": ticket_id, "decision": t["decision"],
            "delegations": t["delegations"], "usage": t["usage"], "saved_to": run["saved_to"]}


@app.get("/api/events")
async def events(
    since: int = Query(0, ge=0, description="Return events after this sequence number."),
    limit: int = Query(200, ge=1, le=1000),
    ticket_id: int | None = None,
    run_id: str | None = None,
    current_only: bool = Query(True, description="Only events since the latest database reset."),
) -> dict[str, Any]:
    """Recent agent events from the audit trail: who said what and which tools they used."""
    rows = _audit_rows()
    floor = max(since, _since_last_reset(rows) - 1 if current_only else 0)
    out = []
    for seq, e in enumerate(rows, start=1):
        if seq <= floor:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if run_id and e.get("run_id") != run_id:
            continue
        out.append({"seq": seq, **e, "summary": _summary(e)})
    out = out[-limit:]
    return {"events": out, "last_seq": len(rows), "agent_running": _run_lock.locked()}


AGENT_ORDER = ["boss", "inventory", "accounting", "facilities", "customer_service"]


@app.get("/api/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int) -> dict[str, Any]:
    """Short summary of what each agent did on the ticket, across every run since the last reset
    (first run plus any follow-ups after approvals). The decision is the latest one."""
    rows = _audit_rows()
    rows = rows[_since_last_reset(rows):]  # only runs on the current shop state
    mine = [e for e in rows if e.get("ticket_id") == ticket_id and e.get("run_id")]
    if not mine:
        return {"ticket_id": ticket_id, "run_id": None, "agents": [], "decision": None}
    run_id = mine[-1]["run_id"]
    run_ids = list(dict.fromkeys(e["run_id"] for e in mine))
    events = mine
    agents = []
    for name in AGENT_ORDER:
        ev = [e for e in events if e["agent"] == name]
        if not ev:
            continue
        tools = [e["detail"]["tool"] for e in ev if e["kind"] == "tool"]
        reports = [e["detail"].get("summary", "") for e in events if e["kind"] == "report" and e["agent"] == name]
        asked_by = sorted({e["agent"] for e in events if e["kind"] == "delegate" and e.get("to") == name})
        delegated_to = [e["to"] for e in ev if e["kind"] == "delegate"]
        tokens = sum((e["detail"].get("usage") or {}).get("input_tokens", 0) + (e["detail"].get("usage") or {}).get("output_tokens", 0)
                     for e in ev if e["kind"] == "model_step")
        agents.append({
            "agent": name,
            "asked_by": asked_by,
            "delegated_to": delegated_to,
            "tools": tools,
            "tool_counts": {t: tools.count(t) for t in dict.fromkeys(tools)},
            "said": reports[-1] if reports else None,
            "model_steps": sum(e["kind"] == "model_step" for e in ev),
            "tokens": tokens,
        })
    decision = next((e["detail"] for e in reversed(events) if e["kind"] == "decision"), None)
    return {"ticket_id": ticket_id, "run_id": run_id, "runs": len(run_ids), "started": events[0]["ts"],
            "agents": agents, "decision": decision}


@app.get("/api/payments")
async def payment_requests(status: str | None = None) -> dict[str, Any]:
    """Payment requests the agents prepared (pending ones need a human), plus payments made."""
    requests = await call("list_payment_requests", status=status)
    payments = await call("list_payments")
    return {**requests, "payments": payments["payments"], "total_paid": payments["total_paid"]}


@app.post("/api/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: Decision) -> dict[str, Any]:
    """A person approves an agent-prepared payment. This is the only route that moves cash:
    it records the approval, then pays (refused if cash would go negative)."""
    decided = await call("human_decide_payment", request_id=request_id, approve=True,
                         approver=body.approver, approval_key=APPROVAL_KEY)
    if not decided.get("decided"):
        raise HTTPException(409, decided.get("message", "Could not approve."))
    paid = await call("pay_approved_request", request_id=request_id)
    req = next((r for r in (await call("list_payment_requests"))["requests"] if r["id"] == request_id), {})
    msg = (f"{body.approver} approved request #{request_id}: paid ${paid['amount']:,.2f} to {paid['payee']}, "
           f"checking now ${paid['new_balance']:,.2f}") if paid.get("paid") else \
          f"{body.approver} approved request #{request_id}, but payment was refused: {paid.get('message')}"
    _human_event("human_approve", {"request_id": request_id, "approver": body.approver, "note": body.note,
                                   "payment": paid, "message": msg}, req.get("ticket_id"))
    if not paid.get("paid"):
        raise HTTPException(409, msg)
    ticket_id = req.get("ticket_id")
    still_pending = [r["id"] for r in (await call("list_payment_requests", status="pending"))["requests"]
                     if r.get("ticket_id") == ticket_id]
    return {"approved": True, "payment": paid, "cash": await call("get_cash_balance"), "message": msg,
            "ticket_id": ticket_id,
            # Nothing else on this ticket waits on a person: the board can send the team back to finish it.
            "followup_ready": ticket_id is not None and not still_pending}


@app.post("/api/payments/{request_id}/reject")
async def reject_payment(request_id: int, body: Decision) -> dict[str, Any]:
    """A person rejects an agent-prepared payment. No money moves."""
    decided = await call("human_decide_payment", request_id=request_id, approve=False,
                         approver=body.approver, approval_key=APPROVAL_KEY)
    if not decided.get("decided"):
        raise HTTPException(409, decided.get("message", "Could not reject."))
    msg = f"{body.approver} rejected request #{request_id}" + (f": {body.note}" if body.note else "")
    _human_event("human_reject", {"request_id": request_id, "approver": body.approver, "note": body.note, "message": msg})
    return {"rejected": True, "request_id": request_id, "message": msg}


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts (plus what pending requests have committed)."""
    return await call("get_cash_balance")


@app.get("/api/drafts")
async def drafts(ticket_id: int | None = None) -> dict[str, Any]:
    """Drafts on the board (customer messages, restock orders). Nothing is ever sent."""
    return await call("list_drafts", ticket_id=ticket_id)


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Reset the working copy to the original database for a fresh run. The audit trail is kept."""
    if _run_lock.locked():
        raise HTTPException(409, "Can't reset while the team is working a ticket.")
    info = reset_working_copy()
    _human_event("reset", {**info, "message": "Database reset to the original values (audit trail kept)."})
    return {**info, "tickets": await call("list_tickets"), "cash": await call("get_cash_balance")}
