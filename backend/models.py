"""Data types for the Campus Customs agent team."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai.usage import RunUsage

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")
TicketStatus = Literal["open", "in_progress", "waiting_approval", "blocked", "resolved"]


# ------------------------------------------------------- agent outputs ---

class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities and Customer Service hand back."""

    summary: str = Field(description="One or two sentences: what you found or did.")
    facts: list[str] = Field(default_factory=list, description="Key facts, each with figures quoted from tool results.")
    actions: list[str] = Field(default_factory=list, description="Things you created or delegated, with ids (draft #, payment request #).")
    blockers: list[str] = Field(default_factory=list, description="What still stands in the way, if anything.")
    recommendation: str = Field(default="", description="What the Boss should do next.")


class DiscountDecision(BaseModel):
    pct: float = Field(description="Discount granted as a fraction of list price, e.g. 0.15.")
    unit_price: float
    qty: int
    total: float
    within_policy: bool
    needs_human: bool = Field(description="True if the customer asked for more than policy allows.")


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    decision: str = Field(description="One or two sentences: the call and the reason.")
    status: Literal["waiting_approval", "blocked", "resolved"] = Field(
        description="Final call only: waiting_approval, blocked or resolved (never open/in_progress)."
    )
    who_worked: list[AgentName] = Field(default_factory=list)
    payment_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    discount: DiscountDecision | None = None
    note: str = Field(default="", description="Key facts with figures from the tools.")


# ------------------------------------------------------ run bookkeeping ---

EventKind = Literal[
    "run_start", "run_end", "ticket_start", "model_step", "tool", "delegate", "delegate_refused",
    "report", "decision", "error",
]


class TeamEvent(BaseModel):
    """One agent-loop step. Appended to output/audit_trail.json and (later) streamed to the dashboard."""

    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
    run_id: str = ""
    ticket_id: int | None = None
    kind: EventKind
    agent: AgentName
    chain: list[AgentName] = Field(default_factory=list, description="Who asked whom to get here, e.g. boss -> inventory.")
    to: AgentName | None = None
    model: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


Emit = Callable[[TeamEvent], Awaitable[None]]


@dataclass
class RunState:
    """Shared by every agent working on the same ticket."""

    ticket_id: int | None
    run_id: str = ""
    emit: Emit | None = None                                  # live stream (CLI print, later the dashboard)
    audit: Callable[[dict[str, Any]], None] | None = None     # append-only audit trail
    delegations: int = 0
    events: list[TeamEvent] = field(default_factory=list)
    usage: RunUsage = field(default_factory=RunUsage)

    async def log(self, event: TeamEvent) -> None:
        event.run_id = event.run_id or self.run_id
        if event.ticket_id is None:
            event.ticket_id = self.ticket_id
        self.events.append(event)
        if self.audit is not None:
            self.audit(event.model_dump())
        if self.emit is not None:
            await self.emit(event)


@dataclass
class ShopDeps:
    """Per-agent dependencies: who I am and how I got here."""

    agent: AgentName
    chain: list[AgentName]       # e.g. ["boss", "inventory"] while Inventory works for the Boss
    state: RunState
