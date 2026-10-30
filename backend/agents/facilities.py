"""Facilities: the shop space — lease, rent, landlord."""

from agents.base import RoleSpec
from models import SpecialistReport

SPEC = RoleSpec(
    name="facilities",
    prompt_file="facilities.md",
    tools=frozenset({"get_shop_date", "list_leases", "get_ticket", "get_lease_rent", "get_cash_balance"}),
    output_type=SpecialistReport,
)
