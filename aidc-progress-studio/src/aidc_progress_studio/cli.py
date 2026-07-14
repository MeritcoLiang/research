from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AIDC Progress Studio")
    parser.add_argument("--host", default=os.getenv("AIDC_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("AIDC_PORT", "8080")))
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("aidc_progress_studio.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
