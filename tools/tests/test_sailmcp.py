# SPDX-License-Identifier: Apache-2.0
"""Versioned wire behavior, cancellation and context-reader boundary preservation."""

import io
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft202012Validator

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from tests.test_sailcontext import _fixture
from vos import sailcontext, sailmcp


def _request(ident: int, method: str, **params: object) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "method": method,
            "params": {"_meta": {sailmcp.PREFIX + "protocolVersion": sailmcp.MODERN,
                                  sailmcp.PREFIX + "clientCapabilities": {}}, **params}}


def _exchange(root: Path, messages: list[object]) -> list[dict[str, Any]]:
    incoming = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
    outgoing = io.BytesIO()
    ensure(sailmcp.serve(root, incoming, outgoing) == 0, "stdio must end cleanly on EOF")
    return [json.loads(line) for line in outgoing.getvalue().splitlines()]


def _modern_and_legacy() -> None:
    root = TOOLS.parent
    results = _exchange(root, [_request(1, "server/discover"), _request(2, "tools/list"),
                               _request(3, "ping")])
    ensure([r["id"] for r in results] == [1, 2, 3], "response ids must correlate")
    discovery = results[0]["result"]
    ensure(discovery["supportedVersions"] == [sailmcp.MODERN, sailmcp.LEGACY] and
           discovery["capabilities"] == {"tools": {}}, "advertise only supported versions and capabilities")
    ensure(all(r["result"]["resultType"] == "complete" for r in results), "modern results need resultType")
    declarations = results[1]["result"]["tools"]
    ensure([t["name"] for t in declarations] == ["sail_references", "sail_search", "sail_symbol"],
           "tool order and finite membership are stable")
    for tool in declarations:
        Draft202012Validator.check_schema(tool["inputSchema"])
        Draft202012Validator.check_schema(tool["outputSchema"])
        ensure(tool["annotations"]["readOnlyHint"], "retrieval is read-only")
    legacy = _exchange(root, [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": sailmcp.LEGACY, "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ])
    ensure(len(legacy) == 2 and legacy[0]["result"]["protocolVersion"] == sailmcp.LEGACY,
           "legacy initialization must negotiate its exact version without answering notifications")
    ensure("resultType" not in legacy[1]["result"], "legacy results retain their version's shape")


def _wire_refusals() -> None:
    bad_version = _request(1, "ping")
    bad_version["params"]["_meta"][sailmcp.PREFIX + "protocolVersion"] = "9999-01-01"
    missing = _request(2, "ping")
    del missing["params"]["_meta"][sailmcp.PREFIX + "clientCapabilities"]
    results = _exchange(TOOLS.parent, [bad_version, missing, [],
        {"jsonrpc": "2.0", "id": True, "method": "ping"},
        _request(5, "unknown"), _request(6, "tools/list", cursor="unknown"),
        {"jsonrpc": "2.0", "method": "notifications/unknown"}])
    ensure([r["error"]["code"] for r in results] == [-32022, -32602, -32600, -32600, -32601, -32602],
           f"protocol errors must be precise: {results}")
    ensure(results[0]["error"]["data"]["requested"] == "9999-01-01", "version refusal retains request")
    for raw in (b'{"jsonrpc":"2.0","jsonrpc":"2.0"}\n', b'{"x":NaN}\n', b'\xff\n'):
        out = io.BytesIO()
        sailmcp.serve(TOOLS.parent, io.BytesIO(raw), out)
        ensure(json.loads(out.getvalue())["error"]["code"] == -32700, "invalid JSON must refuse")
    out = io.BytesIO()
    ensure(sailmcp.serve(TOOLS.parent, io.BytesIO(b"x" * (sailmcp.MAX_MESSAGE + 1)), out) == 1,
           "oversized input must stop after one bounded read")


def _context_and_freshness() -> None:
    files, _ = _fixture()
    with sandbox_tree(files) as root:
        results = _exchange(root, [_request(1, "tools/call", name="sail_symbol", arguments={"query": "shared"}),
                                  _request(2, "tools/call", name="sail_search", arguments={"query": "shared", "limit": 0}),
                                  _request(3, "tools/call", name="execute_shell", arguments={})])
        by_id = {r["id"]: r for r in results}
        report = by_id[1]["result"]["structuredContent"]
        ensure(report == sailcontext.context(root, "symbol", "shared"), "adapter must reuse exact context output")
        ensure(by_id[2]["result"]["isError"] and by_id[3]["error"]["code"] == -32602,
               "tool input errors and unknown tools have distinct error channels")
        (root / "model/model/a.sail").write_bytes(b"stale")
        result = _exchange(root, [_request(1, "tools/call", name="sail_symbol", arguments={"query": "shared"})])[0]
        ensure(result["result"]["isError"] and "structuredContent" not in result["result"],
               "stale context must remain a tool failure with no partial matches")


def _cancellation_and_pending_limits() -> None:
    entered, release = threading.Event(), threading.Event()

    def delayed(*args: object, **kwargs: object) -> dict[str, object]:
        entered.set()
        if not release.wait(5):
            raise RuntimeError("test did not release delayed context")
        return {"advisory_only": True}

    out = io.BytesIO()
    server = sailmcp.Server(TOOLS.parent, out)
    with patch.object(sailcontext, "context", side_effect=delayed):
        try:
            server.receive(_request(1, "tools/call", name="sail_symbol", arguments={"query": "x"}))
            ensure(entered.wait(5), "worker must start without blocking the reader")
            server.receive(_request(2, "tools/call", name="sail_symbol", arguments={"query": "x"}))
            server.receive({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 2}})
            ensure(2 not in server.pending, "cancelled queued work must release its pending slot")
            server.receive({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
            server.receive(_request(3, "ping"))
        finally:
            release.set()
            server.close()
    ensure([json.loads(line)["id"] for line in out.getvalue().splitlines()] == [3],
           "cancelled requests must produce no later response; unrelated requests still work")


def _real_stdio_dispatch() -> None:
    request = json.dumps(_request(1, "server/discover")).encode() + b"\n"
    run = subprocess.run([sys.executable, str(TOOLS / "run.py"), "sail-mcp"], cwd=TOOLS.parent,
                         input=request, capture_output=True, check=False, timeout=30)
    ensure(run.returncode == 0 and json.loads(run.stdout)["result"]["resultType"] == "complete",
           f"registered stdio command must emit only protocol JSON: {run.stderr!r}")


def cases() -> list[Case]:
    return [Case("modern-and-legacy-protocol", _modern_and_legacy),
            Case("wire-refusals", _wire_refusals),
            Case("context-reader-and-staleness", _context_and_freshness),
            Case("cancellation-and-pending-slots", _cancellation_and_pending_limits),
            Case("real-stdio-dispatch", _real_stdio_dispatch)]
