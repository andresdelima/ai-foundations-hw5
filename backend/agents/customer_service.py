"""Customer Service: drafts every outgoing message (drafts stay on the board)."""

from agents.base import RoleSpec
from models import SpecialistReport

SPEC = RoleSpec(
    name="customer_service",
    prompt_file="customer_service.md",
    tools=frozenset({"get_shop_date", "get_ticket", "draft_customer_message", "list_drafts"}),
    output_type=SpecialistReport,
)
