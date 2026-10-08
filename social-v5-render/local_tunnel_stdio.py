"""Run existing Social V5 FREE tool registrations locally over stdio.
Does not open an HTTP port; retains all current provider and research guards.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
