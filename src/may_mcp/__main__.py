"""Run stdio by default or explicitly opt into authenticated Streamable HTTP."""

import argparse
import logging
import os
import sys

from may_mcp.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="May MCP server")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    try:
        settings = Settings.from_env(os.environ)
        oauth = None
        if args.transport == "http":
            from may_mcp.auth import OAuthSettings

            oauth = OAuthSettings.from_env(os.environ)
    except ValueError as error:
        print(f"Invalid May MCP configuration: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    from may_mcp.server import create_http_app, create_server

    if oauth is None:
        create_server(settings).run(transport="stdio")
    else:
        import uvicorn

        uvicorn.run(
            create_http_app(settings, oauth),
            host=args.host,
            port=args.port,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
