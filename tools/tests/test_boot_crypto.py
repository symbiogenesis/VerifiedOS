# SPDX-License-Identifier: Apache-2.0
"""Offline controls for selection, refusal, receipt freshness and native C."""

import argparse
import json
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import boot_crypto as b
from vos import toolenv
from vos.cli import boot_crypto as cli


def selected_interfaces() -> None:
    def group(interface: str, prehash: str, mu: bool = False) -> dict[str, object]:
        return {"tgId": 1, "parameterSet": "ML-DSA-87", "signatureInterface": interface,
                "preHash": prehash, "externalMu": mu, "tests": [
                    {"tcId": i, "testPassed": bool(i), "pk": "00", "message": "01", "mu": "02",
                     "context": "", "signature": "03"} for i in range(2)]}
    rows, omitted = b.cases({"testGroups": [group("external", "pure"), group("internal", "none"),
                            group("internal", "none", True), group("external", "preHash")]}, "mldsa")
    ensure({c.mode for c in rows} == {"mldsa", "mldsa-internal", "mldsa-mu"}, "interface selection")
    ensure(len(rows) == 6 and len(omitted) == 2, "prehash exclusion is visible")
    ensure(next(c for c in rows if c.mode.endswith("-mu")).message == b"\x02", "mu uses its own input")
    try:
        b.cases({"testGroups": []}, "mldsa")
    except ValueError:
        return
    raise AssertionError("empty campaign was accepted")


def controls_preserve_positive() -> None:
    original = b.Case("authored", "mldsa", bytes(2592), b"message", b"", bytes(4627), True)
    cases = b.refusals(original)
    ensure(original.expected and original.signature == bytes(4627), "positive mutated")
    ensure(all(not case.expected for case in cases), "refusal expected value")
    names = {c.name.removeprefix("authored-") for c in cases}
    ensure({"wrong-root", "signature-flipped", "positive-z-bound", "negative-z-bound",
            "hint-end-overflow", "message-overlong", "context-overlong"} <= names, "missing refusal family")
    for label, expected in (("positive-z-bound", 524168), ("negative-z-bound", -524168)):
        data = next(c.signature for c in cases if c.name.endswith(label))
        value = int.from_bytes(data[64:67], "little") & ((1 << 20)-1)
        ensure(524288-value == expected, "incorrect strict boundary control")


def drift_refuses() -> None:
    with patch.object(b, "input_snapshot", return_value={"source": "changed"}):
        try:
            b.require_unchanged(TOOLS.parent, {"source": "before"})
        except ValueError:
            return
    raise AssertionError("changed source kept valid evidence")


def operational_failure_is_not_refusal() -> None:
    case = b.Case("control", "slh", bytes(64), b"message", b"", bytes(29792), False)
    with tempfile.TemporaryDirectory() as name:
        work = Path(name)
        with patch.object(b, "run", return_value="garbage"):
            try:
                b.invoke(work / "unused", work, case)
            except ValueError:
                pass
            else:
                raise AssertionError("malformed driver verdict became signature refusal")
        with patch.object(b.subprocess, "run", return_value=subprocess.CompletedProcess([], 2, "", "error")):
            try:
                b.openssl_verify(work, case)
            except ValueError:
                return
    raise AssertionError("OpenSSL operational failure became signature refusal")


def failed_rerun_replaces_pass() -> None:
    with tempfile.TemporaryDirectory() as name:
        work = Path(name)
        report = work / "report.json"
        report.write_text('{"passed": true}', encoding="utf-8")
        args = argparse.Namespace(out=str(work), gallina=False, first=False)
        with (patch.object(cli.env, "load", return_value=SimpleNamespace(root=TOOLS.parent, lane_root=work)),
              patch.object(cli.env, "hold_lock", return_value=nullcontext()),
              patch.object(b, "campaign", side_effect=ValueError("failed control"))):
            ensure(cli.cmd_run(args) == 1, "failed campaign returned success")
        after = json.loads(report.read_text(encoding="utf-8"))
        ensure(after["passed"] is False and after["status"] == "failed", "stale pass survived failure")


def native_controls() -> None:
    work = toolenv.environment(TOOLS.parent, sys.platform).parent / "boot-crypto-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as name:
        output = Path(name)
        binary = b.build(TOOLS.parent, output)
        ensure(b.run([str(binary), "bounds"], output) == "0", "invalid length reached input read")
        for mode, p, s in (("slh", 64, 29792), ("mldsa", 2592, 4627)):
            case = b.Case("all-zero-refusal", mode, bytes(p), b"message", b"", bytes(s), False)
            ensure(not b.invoke(binary, output, case), "all-zero signature accepted")
        for case in b.offline_fixtures(TOOLS.parent):
            ensure(b.invoke(binary, output, case), f"{case.mode} positive refused")
            ensure(not b.invoke(binary, output, b.refusals(case)[0]), f"{case.mode} corrupt neighbor accepted")


def cases() -> list[Case]:
    return [Case("pure internal and mu selection", selected_interfaces),
            Case("corruption and strict boundary controls", controls_preserve_positive),
            Case("source drift invalidates evidence", drift_refuses),
            Case("operational failures are not refusals", operational_failure_is_not_refusal),
            Case("failed rerun replaces previous success", failed_rerun_replaces_pass),
            Case("sanitized native bounds and refusals", native_controls, lane="guest")]
