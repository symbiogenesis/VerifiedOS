# SPDX-License-Identifier: Apache-2.0
"""Serve the local pure Vela browser editor and compile-time expression console."""

import argparse
import sys

from vos.vela_playground import PlaygroundServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    parser.add_argument("--port", type=int, default=8765,
                        help="IPv4 loopback port (default: 8765; zero selects an available port)")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        with PlaygroundServer(args.port) as server:
            print(f"Vela playground: {server.launch_url}", flush=True)
            print("Pure Nat/bool prototype. Ctrl+C stops the local service.", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except OSError as error:
        print(f"Vela playground unavailable: {error}", file=sys.stderr)
        return 1
    return 0
