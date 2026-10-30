"""Entrypoint for StreetAccess server and local demonstration."""

import argparse
import sys
from pathlib import Path

# Ensure project root directory is in sys.path when invoked directly as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from streetaccess.api.app import app


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the Uvicorn web server hosting StreetAccess core."""
    print("=" * 60)
    print("Starting StreetAccess Deterministic Core API")
    print(f"Server URL: http://{host}:{port}")
    print(f"Interactive OpenAPI docs: http://{host}:{port}/docs")
    print("Runtime Perception Provider: Mock Fixture (Deterministic)")
    print("=" * 60)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StreetAccess Runner")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)

