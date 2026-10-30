"""The Campus Customs agent team: five roles, full connectivity via `delegate`."""

from agents import accounting, boss, customer_service, facilities, inventory
from agents.base import RoleSpec, get_agent, run_agent
from models import AgentName

ROLES: dict[AgentName, RoleSpec] = {
    spec.name: spec
    for spec in (boss.SPEC, inventory.SPEC, accounting.SPEC, facilities.SPEC, customer_service.SPEC)
}

__all__ = ["ROLES", "get_agent", "run_agent"]
