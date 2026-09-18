"""Run the local processing service: python -m hvsr_service [--host] [--port] [--workers] [--token]"""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

from .app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hvsr-service", description="QuakeLogic HVSR Studio engine service")
    parser.add_argument("--host", default=os.environ.get("HVSR_ENGINE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("HVSR_ENGINE_PORT", "8765")))
    parser.add_argument("--workers", type=int, default=None, help="job worker threads (default: cpu/2)")
    parser.add_argument("--token", default=None, help="shared secret required in X-Engine-Token (default: $HVSR_ENGINE_TOKEN)")
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args(argv)

    app = create_app(workers=args.workers, token=args.token)
    print(f"QuakeLogic HVSR Studio engine service listening on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level, access_log=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
