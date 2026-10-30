"""Boss: reads each ticket, routes the work, and makes the final call."""

from agents.base import RoleSpec
from models import TicketDecision

SPEC = RoleSpec(
    name="boss",
    prompt_file="boss.md",
    tools=frozenset({"get_shop_date", "list_payments", "get_ticket", "list_open_tickets", "get_cash_balance", "list_payment_requests",
                     "list_drafts", "check_discount_policy"}),
    output_type=TicketDecision,
)
