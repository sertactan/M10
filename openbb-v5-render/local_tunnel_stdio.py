"""Run the existing OpenBB V5 FREE MCP tools locally over stdio.
Keep the production HTTP BearerGate intact; its one-time local variable
only satisfies initialization when importing the existing server module.
No HTTP listener is started by this entrypoint.
"""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("MERIDYEN_MCP_BEARER_TOKEN", secrets.token_urlsafe(48))
from server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
