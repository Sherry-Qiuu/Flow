"""Module entry point: ``python -m service`` starts a single worker."""

from __future__ import annotations

import argparse

import uvicorn

from service.config import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Flow backend")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    settings = load_settings()
    host = args.host or settings.app.host
    port = args.port or settings.app.port
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        workers=1,
        reload=False,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
