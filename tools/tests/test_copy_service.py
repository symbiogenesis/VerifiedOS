# SPDX-License-Identifier: Apache-2.0
"""Copy-service comparison coverage, fail-closed syntax and native byte controls."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import copy_service as c
from vos import toolenv


def generated_domains() -> None:
    config = c.configuration(TOOLS.parent)
    cases = c.generated(config)
    ensure({case.inputs[0] for case in cases} == set(range(5)), "lost comparison family")
    indices = [case for case in cases if case.inputs[0] == 0]
    ensure({case.inputs[2] for case in indices} == set(range(config.span)), "wire bases incomplete")
    ensure(any(case.inputs[1] >= config.span for case in indices), "no wrapping live window")
    notifications = [case for case in cases if case.inputs[0] == 4]
    ensure({case.inputs[8] for case in notifications} == set(range(5)), "publication step missing")
    ensure({case.inputs[1] for case in notifications} == {0, 1}, "reset owner missing")
    ensure(len([case for case in cases if case.inputs[0] == 2]) == 6 * 6 * 3 * 2, "lifecycle product incomplete")


def answers_are_not_recomputed() -> None:
    case = c.Comparison((0, 0, 0), ("rv_occupancy (mk_ring_view 0 0)",))
    good = c.comparison_source([case], "0\n")
    bad = c.comparison_source([case], "1\n")
    ensure("Require Import RingContract CopyRingService." in good, "reference import missing")
    ensure("= 0." in good and "= 1." in bad, "C answer silently corrected")
    for text in ("", "0\n0\n", "0 1\n", "-1\n", "true\n", "1.0\n", "\u0661\n", "9999999999\n"):
        try:
            c.comparison_source([case], text)
        except ValueError:
            continue
        raise AssertionError(f"malformed C answer accepted: {text!r}")


def declaration_owns_constants() -> None:
    config = c.configuration(TOOLS.parent)
    header = c.configuration_header(config)
    ensure(f"#define VOS_COPY_CAPACITY {config.capacity}u" in header, "capacity not emitted")
    work = toolenv.environment(TOOLS.parent, sys.platform).parent / "copy-service-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="declaration-", dir=work) as temporary:
        root = Path(temporary)
        (root / "interfaces").mkdir()
        original = json.loads((TOOLS.parent / "interfaces" / "ring-reference.json").read_text(encoding="utf-8"))
        for span in (config.capacity, config.capacity + 1, 2**32, True):
            original["worlds"][0]["ring"]["index_span"] = span
            (root / "interfaces" / "ring-reference.json").write_text(json.dumps(original), encoding="utf-8")
            try:
                c.configuration(root)
            except ValueError:
                continue
            raise AssertionError(f"unsafe wire span accepted: {span!r}")


def native_payload_controls() -> None:
    compiler = c.c_compiler()
    ensure(compiler is not None, "native C compiler missing")
    if compiler is None:
        return
    work = toolenv.environment(TOOLS.parent, sys.platform).parent / "copy-service-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as temporary:
        lane = Path(temporary)
        compiled = c.build_host(TOOLS.parent, lane, compiler)
        ensure(compiled.returncode == 0, compiled.stderr)
        binary = lane / "copy-host"
        done = subprocess.run([str(binary), "controls"], capture_output=True, text=True, timeout=60, check=False)
        ensure(done.returncode == 0, done.stderr)
        ensure("fixed consumer controls" in done.stderr, "no control verdict")
        for text in ("9\n", "0 1 2\n", "2 6 0 0 0\n", "3 0 9999999999\n", "0 0 0 extra\n", "0 0 0"):
            refused = subprocess.run([str(binary)], input=text, capture_output=True, text=True, timeout=60, check=False)
            ensure(refused.returncode != 0, f"malformed harness input accepted: {text!r}")


def cases() -> list[Case]:
    return [Case("generated comparison domains", generated_domains),
            Case("C answers remain reference equalities", answers_are_not_recomputed),
            Case("declaration owns bounded C constants", declaration_owns_constants),
            Case("native atomic payload controls", native_payload_controls, lane="guest")]
