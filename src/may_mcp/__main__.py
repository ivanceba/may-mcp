"""Run the May MCP server over stdio."""

import logging
import os
import sys

from may_mcp.config import Settings
from may_mcp.server import create_server


def main() -> None:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    try:
        settings = Settings.from_env(os.environ)
    except ValueError as error:
        print(f"Invalid May MCP configuration: {error}", file=sys.stderr)
        raise SystemExit(2) from None
    create_server(settings).run(transport="stdio")


if __name__ == "__main__":
    main()
