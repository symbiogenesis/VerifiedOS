# SPDX-License-Identifier: Apache-2.0
"""Serve Vela's local browser editor and bounded compile-time expression console."""

import argparse
import sys
from pathlib import Path

from filelock import Timeout

from vos.vela_playground import PlaygroundServer


def main(argv: list[str] | None = None) -> int:
    return serve(argv)


def serve(argv: list[str] | None = None, *, mathematical: bool = False) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    parser.add_argument("--port", type=int, default=8765,
                        help="IPv4 loopback port (default: 8765; zero selects an available port)")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    try:
        native_parser: Path | None = None
        if mathematical:
            from vos import vela_parser
            print("Preparing the locked mathematical parser in this native lane...", flush=True)
            native_parser = vela_parser.build(Path(__file__).resolve().parents[3]).executable
        with PlaygroundServer(args.port, mathematical_parser=native_parser) as server:
            print(f"Vela playground: {server.launch_url}", flush=True)
            scope = "Pure and dependent mathematical prototypes" if mathematical else "Pure Nat/bool prototype"
            print(f"{scope}. Ctrl+C stops the local service.", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, ValueError, Timeout) as error:
        print(f"Vela playground unavailable: {error}", file=sys.stderr)
        return 1
    return 0
