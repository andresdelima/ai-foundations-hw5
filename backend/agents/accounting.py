"""Accounting: cash, vendor invoices, and payment requests (human approval required)."""

from agents.base import RoleSpec
from models import SpecialistReport

SPEC = RoleSpec(
    name="accounting",
    prompt_file="accounting.md",
    tools=frozenset({"get_shop_date", "list_payments", "list_leases", "get_ticket", "get_cash_balance", "list_open_invoices", "list_payment_requests",
                     "request_payment", "pay_approved_request", "get_vendor_status", "get_lease_rent",
                     "check_order_fill"}),
    output_type=SpecialistReport,
)
