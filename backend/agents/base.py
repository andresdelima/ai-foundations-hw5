"""Shared machinery for the five agents.

- One Portkey model (gpt-6-luna) for every agent.
- One in-process connection to the Campus Customs MCP server. Each role only
  sees the MCP tools on its allowlist.
- A `delegate(to, task)` tool every agent has: full connectivity, with the
  bounded-mesh guardrails from config.py.
- Every agent-loop step is logged as a TeamEvent (and so appended to
  output/audit_trail.json): each model response (tool calls it asked for,
  text, token usage), each MCP tool call with its full result, each
  delegation and report. Tools that record who acted get the calling agent's
  real role stamped in (agents can't spoof it).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

import config
from models import AGENT_NAMES, AgentName, ShopDeps, SpecialistReport, TeamEvent

# MCP tools that record who acted. The backend overwrites `actor` with the caller's role.
ACTOR_TOOLS = {"request_payment", "update_ticket", "draft_customer_message", "draft_restock_order"}
# MCP tools only a person may trigger (through the backend routes).
HUMAN_ONLY_TOOLS = {"human_decide_payment"}

LABELS: dict[AgentName, str] = {
    "boss": "Boss",
    "inventory": "Inventory agent",
    "accounting": "Accounting agent",
    "facilities": "Facilities agent",
    "customer_service": "Customer Service agent",
}


@dataclass(frozen=True)
class RoleSpec:
    name: AgentName
    prompt_file: str
    tools: frozenset[str]          # MCP tools this role may call
    output_type: type


_model: OpenAIResponsesModel | None = None
_mcp = None  # MCPToolset, filtered so human-only tools never reach an agent


def shop_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey — the only model in this project."""
    global _model
    if _model is None:
        key = config.portkey_api_key()
        client = AsyncOpenAI(api_key=key, base_url=config.PORTKEY_BASE_URL, default_headers={"x-portkey-api-key": key},
                             timeout=config.MODEL_TIMEOUT_S, max_retries=2)
        _model = OpenAIResponsesModel(config.MODEL_NAME, provider=OpenAIProvider(openai_client=client))
    return _model


async def _on_tool_call(ctx: RunContext[ShopDeps], call_tool, name: str, args: dict[str, Any]):
    deps = ctx.deps
    if name in HUMAN_ONLY_TOOLS:  # second lock: never let an agent reach the approval tool
        await deps.state.log(TeamEvent(kind="error", agent=deps.agent, chain=deps.chain,
                                       detail={"error": f"{deps.agent} tried human-only tool {name}"}))
        raise PermissionError(f"{name} is for humans on the dashboard only.")
    if name in ACTOR_TOOLS:
        args = {**args, "actor": deps.agent}
    result = await call_tool(name, args)
    await deps.state.log(TeamEvent(
        kind="tool", agent=deps.agent, chain=deps.chain,
        detail={"tool": name, "via": "mcp", "args": args, "result": result},
    ))
    return result


def shop_tools():
    """The Campus Customs MCP server, attached in-process (same Python process)."""
    global _mcp
    if _mcp is None:
        from server import mcp as campus_customs_mcp  # mcp_server/server.py

        _mcp = MCPToolset(campus_customs_mcp, process_tool_call=_on_tool_call, tool_error_behavior="failed")
        # Agents never even see human-only tools.
        _mcp = _mcp.filtered(lambda ctx, tool: tool.name not in HUMAN_ONLY_TOOLS)
    return _mcp


# ------------------------------------------------------------ delegation ---

async def delegate(ctx: RunContext[ShopDeps], to: AgentName, task: str) -> str:
    """Ask another agent on the team for help and get their report back.

    Args:
        to: Who should do it: boss, inventory, accounting, facilities or customer_service.
        task: A self-contained request. Include the ticket id and the facts they need.
    """
    deps, state = ctx.deps, ctx.deps.state
    hops = len(deps.chain) - 1

    def refuse(reason: str) -> str:
        return f"Delegation refused: {reason} Finish with what you have and say what is missing."

    reason = None
    if to == deps.agent:
        reason = "you cannot delegate to yourself."
    elif to in deps.chain:
        reason = f"{to} is already working in this chain ({' -> '.join(deps.chain)})."
    elif hops >= config.MAX_DEPTH:
        reason = f"the chain is already {hops} hops deep (max {config.MAX_DEPTH})."
    elif state.delegations >= config.MAX_DELEGATIONS:
        reason = f"this ticket already used {state.delegations} delegations (max {config.MAX_DELEGATIONS})."
    if reason:
        await state.log(TeamEvent(kind="delegate_refused", agent=deps.agent, chain=deps.chain, to=to,
                                  detail={"task": task, "reason": reason}))
        return refuse(reason)

    state.delegations += 1
    await state.log(TeamEvent(kind="delegate", agent=deps.agent, chain=deps.chain, to=to,
                              detail={"task": task, "delegations_used": state.delegations}))
    child = ShopDeps(agent=to, chain=[*deps.chain, to], state=state)
    output = await run_agent(to, task, child)
    report = output.model_dump() if hasattr(output, "model_dump") else {"summary": str(output)}
    await state.log(TeamEvent(kind="report", agent=to, chain=child.chain, to=deps.agent, detail=report))
    return json.dumps(report)


delegation_tools = FunctionToolset([delegate])


# ------------------------------------------------------------- building ---

def build_agent(spec: RoleSpec) -> Agent[ShopDeps, Any]:
    shared = (config.PROMPTS_DIR / "shared_rules.md").read_text(encoding="utf-8")
    role = (config.PROMPTS_DIR / spec.prompt_file).read_text(encoding="utf-8")
    agent = Agent(
        shop_model(),
        name=spec.name,
        deps_type=ShopDeps,
        output_type=spec.output_type,
        instructions=f"{shared}\n\n{role}",
        toolsets=[shop_tools().filtered(lambda ctx, tool, allowed=spec.tools: tool.name in allowed), delegation_tools],
    )

    @agent.instructions
    def where_am_i(ctx: RunContext[ShopDeps]) -> str:
        state = ctx.deps.state
        others = ", ".join(n for n in AGENT_NAMES if n != ctx.deps.agent)
        return (
            f"You are the {LABELS[ctx.deps.agent]}. Ticket in focus: {state.ticket_id}. "
            f"Delegation chain so far: {' -> '.join(ctx.deps.chain)}. "
            f"Delegations used on this ticket: {state.delegations}/{config.MAX_DELEGATIONS}. "
            f"You can delegate to: {others} (not to anyone already in the chain)."
        )

    return agent


_agents: dict[AgentName, Agent] = {}


def get_agent(name: AgentName) -> Agent[ShopDeps, Any]:
    if name not in _agents:
        from agents import ROLES

        _agents[name] = build_agent(ROLES[name])
    return _agents[name]


async def _loop(name: AgentName, prompt: str, deps: ShopDeps) -> Any:
    """The agent loop, step by step. Each model response is logged before its tools run."""
    agent = get_agent(name)
    step = 0
    async with agent.iter(prompt, deps=deps, usage_limits=UsageLimits(request_limit=config.REQUEST_LIMIT)) as run:
        async for node in run:
            if Agent.is_call_tools_node(node):
                step += 1
                response = node.model_response
                await deps.state.log(TeamEvent(
                    kind="model_step", agent=name, chain=deps.chain, model=response.model_name,
                    detail={
                        "step": step,
                        "prompt": prompt if step == 1 else None,
                        "tool_calls": [{"tool": p.tool_name, "args": p.args_as_dict()}
                                       for p in response.parts if isinstance(p, ToolCallPart)],
                        "text": " ".join(p.content for p in response.parts if isinstance(p, TextPart)) or None,
                        "usage": {"input_tokens": response.usage.input_tokens,
                                  "output_tokens": response.usage.output_tokens},
                    },
                ))
        deps.state.usage.incr(run.usage)
        return run.result.output


async def run_agent(name: AgentName, prompt: str, deps: ShopDeps) -> Any:
    """Run one agent to completion. Usage is added to the ticket's running total."""
    try:
        return await asyncio.wait_for(_loop(name, prompt, deps), timeout=config.AGENT_TIMEOUT_S)
    except (UsageLimitExceeded, asyncio.TimeoutError) as exc:
        why = (f"hit its {config.REQUEST_LIMIT}-request limit" if isinstance(exc, UsageLimitExceeded)
               else f"timed out after {config.AGENT_TIMEOUT_S}s")
        await deps.state.log(TeamEvent(kind="error", agent=name, chain=deps.chain,
                                       detail={"error": f"{LABELS[name]} {why}"}))
        if name == "boss":
            raise
        return SpecialistReport(summary=f"{LABELS[name]} {why} before finishing.", blockers=[why])
