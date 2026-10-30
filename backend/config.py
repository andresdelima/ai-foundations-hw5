"""Settings shared by the backend and the agent team."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
OUTPUT_DIR = ROOT / "output"
MCP_DIR = ROOT / "mcp_server"
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"      # never modified
WORKING_DB = ROOT / "data" / "campus_customs_new.db"   # what the MCP server reads and writes
AUDIT_TRAIL = OUTPUT_DIR / "audit_trail.json"          # appended every step, never wiped

# Make the MCP server package importable (the backend attaches it in-process).
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

# The key lives in a .env file: this folder's first, then the nearest parent's.
for folder in [ROOT, *ROOT.parents]:
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env", override=False)

# HW5 rule: every agent uses this one model through Portkey. Deliberately not
# configurable, so no other model can sneak into a run.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def portkey_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Put it in a .env file (see .env.example).")
    return key


# Delegation guardrails (shop choice: bounded mesh).
MAX_DEPTH = 3            # hops below the Boss: Boss -> A -> B -> C
MAX_DELEGATIONS = 6      # per ticket, across all agents
REQUEST_LIMIT = 8        # model requests per single agent run
MODEL_TIMEOUT_S = 60     # one model call (Portkey) before it is retried
AGENT_TIMEOUT_S = 240    # one whole agent run, including its delegations
