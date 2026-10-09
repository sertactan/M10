"""Run the locally authenticated research-only MCP endpoint, manually."""
import argparse
from pathlib import Path
from core.hermes_team.mcp_local import serve

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    serve(parser.parse_args().db)

if __name__ == "__main__":
    main()
