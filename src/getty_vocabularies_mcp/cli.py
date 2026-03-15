"""Command-line entry point for getty-vocabularies-mcp."""

import sys


def main():
    """Start the Getty Vocabularies MCP server."""
    from getty_vocabularies_mcp.server import start_mcp_server

    port = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    start_mcp_server(port=port)


if __name__ == "__main__":
    main()