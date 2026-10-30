"""Agent loop: the Boss works each open ticket; anyone can delegate to anyone.

    cd backend
    ../.venv/bin/python team.py --all            # reset DB, then work every open ticket
    ../.venv/bin/python team.py --ticket 101     # reset DB, then work one ticket
    ../.venv/bin/python team.py --ticket 101 --no-reset   # continue on the current working copy

Every shop read/write goes through the Campus Customs MCP server: the agents
via MCPToolset, this loop via shop_client.call(). Every agent-loop step is
appended to output/audit_trail.json (never wiped), and each run is also saved
whole to output/runs/<timestamp>.json. Tickets are worked one at a time, in id
order, because they share one cash account.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import audit
import config
from agents import run_agent
from models import Emit, RunState, ShopDeps, TeamEvent, TicketDecision
from shop_client import call, reset_working_copy

RUNS_DIR = config.OUTPUT_DIR / "runs"


async def _enforce_discount_policy(decision: TicketDecision) -> TicketDecision:
    """Re-check the Boss's discount against the shop rule via MCP (never trust the math)."""
    if decision.discount is None:
        return decision
    ticket = await call("get_ticket", ticket_id=decision.ticket_id)
    sku = (ticket.get("ticket") or {}).get("sku")
    if not sku:
        return decision
    check = await call("check_discount_policy", sku=sku, qty=decision.discount.qty, requested_pct=decision.discount.pct)
    req = check.get("requested")
    if req:
        decision.discount.within_policy = req["within_policy"]
        decision.discount.unit_price = req["unit_price"]
        decision.discount.total = req["total"]
        if not req["within_policy"]:
            decision.discount.needs_human = True
    return decision


async def run_ticket(ticket_id: int, run_id: str, emit: Emit | None = None) -> dict[str, Any]:
    state = RunState(ticket_id=ticket_id, run_id=run_id, emit=emit, audit=audit.append)
    ticket = await call("get_ticket", ticket_id=ticket_id)
    if not ticket["found"]:
        raise ValueError(f"No ticket {ticket_id}")
    t = ticket["ticket"]
    await call("update_ticket", ticket_id=ticket_id, status="in_progress", note="Boss picked up the ticket.", actor="boss")
    await state.log(TeamEvent(kind="ticket_start", agent="boss", chain=["boss"],
                              detail={"type": t["type"], "requester": t["requester"], "subject": t["subject"]}))

    prompt = (
        f"Work ticket {ticket_id} ({t['type']}: {t['subject']}, from {t['requester']}). "
        f"Start with get_ticket({ticket_id}), route it to the right agents, and make the final call."
    )
    if ticket["payment_requests"] or ticket["drafts"]:
        prompt += (" This is a FOLLOW-UP run: the team worked this ticket before and a person may have approved "
                   "payments since. Check what changed (request statuses, existing drafts) and finish only what is left.")
    try:
        decision = await run_agent("boss", prompt, ShopDeps(agent="boss", chain=["boss"], state=state))
        if not isinstance(decision, TicketDecision):
            raise RuntimeError(f"Boss did not return a decision: {decision}")
        decision.ticket_id = ticket_id
        decision = await _enforce_discount_policy(decision)
        await call("update_ticket", ticket_id=ticket_id, status=decision.status,
                   note=f"{decision.decision} {decision.note}".strip(), actor="boss")
        await state.log(TeamEvent(kind="decision", agent="boss", chain=["boss"], model=config.MODEL_NAME,
                                  detail=decision.model_dump()))
        result = decision.model_dump()
    except Exception as exc:  # keep going with the other tickets
        error = f"{type(exc).__name__}: {exc}"
        await state.log(TeamEvent(kind="error", agent="boss", chain=["boss"], detail={"error": error}))
        await call("update_ticket", ticket_id=ticket_id, status="blocked", note=f"Run failed: {type(exc).__name__}", actor="boss")
        result = {"ticket_id": ticket_id, "status": "blocked", "error": error}

    return {
        "ticket_id": ticket_id,
        "decision": result,
        "delegations": state.delegations,
        "usage": {"requests": state.usage.requests, "input_tokens": state.usage.input_tokens,
                  "output_tokens": state.usage.output_tokens},
        "events": [e.model_dump() for e in state.events],
    }


async def run_board(ticket_ids: list[int] | None = None, reset: bool = True, emit: Emit | None = None) -> dict[str, Any]:
    """Work tickets one by one. A full run starts from a fresh copy of the original DB."""
    started = datetime.now(timezone.utc)
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    reset_info = reset_working_copy() if reset else None
    if ticket_ids is None:
        ticket_ids = [t["id"] for t in (await call("list_open_tickets"))["tickets"]]

    board = RunState(ticket_id=None, run_id=run_id, emit=emit, audit=audit.append)
    await board.log(TeamEvent(kind="run_start", agent="boss", model=config.MODEL_NAME,
                              detail={"tickets": ticket_ids, "reset": reset_info, "database": config.WORKING_DB.name,
                                      "limits": {"max_depth": config.MAX_DEPTH, "max_delegations": config.MAX_DELEGATIONS,
                                                 "request_limit": config.REQUEST_LIMIT, "agent_timeout_s": config.AGENT_TIMEOUT_S}}))

    tickets = [await run_ticket(tid, run_id, emit) for tid in ticket_ids]
    usage_total = {k: sum(t["usage"][k] for t in tickets) for k in ("requests", "input_tokens", "output_tokens")}
    board_after = {
        "tickets": await call("list_open_tickets"),
        "payment_requests": await call("list_payment_requests"),
        "drafts": await call("list_drafts"),
    }
    await board.log(TeamEvent(kind="run_end", agent="boss", model=config.MODEL_NAME,
                              detail={"usage_total": usage_total,
                                      "statuses": {t["ticket_id"]: t["decision"].get("status") for t in tickets}}))

    run = {
        "run_id": run_id,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": config.MODEL_NAME,
        "database": config.WORKING_DB.name,
        "reset": reset_info,
        "tickets": tickets,
        "board_after": board_after,
        "usage_total": usage_total,
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"run-{run_id}.json"
    path.write_text(json.dumps(run, indent=2, default=str), encoding="utf-8")
    run["saved_to"] = str(path.relative_to(config.ROOT))
    return run


async def _print_event(event: TeamEvent) -> None:
    arrow = f" -> {event.to}" if event.to else ""
    d = event.detail
    what = {
        "run_start": lambda: f"tickets {d.get('tickets')}",
        "run_end": lambda: f"{d.get('statuses')} usage {d.get('usage_total')}",
        "ticket_start": lambda: d.get("subject", ""),
        "model_step": lambda: f"step {d.get('step')}: " + (", ".join(c["tool"] for c in d.get("tool_calls", [])) or "(text)"),
        "delegate": lambda: d.get("task", "")[:110],
        "delegate_refused": lambda: d.get("reason", ""),
        "report": lambda: d.get("summary", "")[:110],
        "tool": lambda: f"{d.get('tool')}({', '.join(f'{k}={v}' for k, v in d.get('args', {}).items())})"[:110],
        "decision": lambda: f"{d.get('status')}: {d.get('decision', '')}"[:140],
        "error": lambda: d.get("error", "")[:140],
    }[event.kind]()
    print(f"  [{event.ticket_id}] {event.kind:<16} {event.agent}{arrow}: {what}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="work every open ticket")
    group.add_argument("--ticket", type=int, action="append", help="work this ticket (repeatable)")
    parser.add_argument("--no-reset", action="store_true", help="keep the current working copy instead of resetting")
    args = parser.parse_args()

    run = asyncio.run(run_board(None if args.all else args.ticket, reset=not args.no_reset, emit=_print_event))
    print(f"\nRun {run['run_id']} | model {run['model']} | usage {run['usage_total']} | saved {run['saved_to']}")
    print(f"Audit trail: {config.AUDIT_TRAIL.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
