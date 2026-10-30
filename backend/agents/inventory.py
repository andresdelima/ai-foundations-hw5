"""Inventory: stock by SKU and size, shortfalls, and which vendor can restock."""

from agents.base import RoleSpec
from models import SpecialistReport

SPEC = RoleSpec(
    name="inventory",
    prompt_file="inventory.md",
    tools=frozenset({"get_shop_date", "list_inventory", "get_ticket", "check_order_fill", "list_vendors", "get_vendor_status", "draft_restock_order"}),
    output_type=SpecialistReport,
)
