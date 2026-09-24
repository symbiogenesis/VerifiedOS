# SPDX-License-Identifier: Apache-2.0
"""Supervisor differential syntax, coverage and the native consumer controls."""

import subprocess
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import env
from vos import supervisor as s


def generated_domains_are_nonempty() -> None:
    cases = s.generated()
    families = {case.inputs[0] for case in cases}
    ensure(families == {0, 1, 2}, "a comparison family disappeared")
    order_cases = [case for case in cases if case.inputs[0] == 0]
    ensure(len(order_cases) == 23, "control plus twenty weakenings and two strangers")
    ensure({case.inputs[1] for case in cases if case.inputs[0] == 1} == set(range(8)),
           "a detector is absent")
    ensure(len([case for case in cases if case.inputs[0] == 2]) == 25,
           "manifest/retired edge cross-product is incomplete")


def answer_translation_uses_the_reference() -> None:
    case = s.Comparison((1,), ("spec_detect demo (fun _ => 3) PoolLow",
                               "spec_limiter demo (declared_at 0 3 2 0) RefuseTheNewRequest"),
                        ("bool", "action"))
    text = s.comparison_source([case], "1 9\n")
    ensure("Require Import SupervisionTree." in text, "lost the actual reference")
    ensure("= true := eq_refl." in text and "= EscalateToRotReset := eq_refl." in text,
           "C answers were not bound to exact Gallina equalities")
    changed = s.comparison_source([case], "0 0\n")
    ensure("= false := eq_refl." in changed and "= RefuseTheNewRequest := eq_refl." in changed,
           "answer translation silently corrected an incorrect C answer")


def malformed_answers_are_refused() -> None:
    case = s.Comparison((0,), ("bringup_ok demo nil",), ("bool",))
    for answer in ("", "0\n0\n", "0 1\n", "2\n", "-1\n", "1.0\n", "true\n", "\u0661\n"):
        try:
            s.comparison_source([case], answer)
        except ValueError:
            continue
        raise AssertionError(f"accepted malformed answer {answer!r}")
    try:
        s.comparison_source([], "")
    except ValueError:
        return
    raise AssertionError("an empty comparison passed")


def native_consumer_controls() -> None:
    compiler = s.c_compiler()
    ensure(compiler is not None, "guest native C compiler is missing")
    if compiler is None:
        return
    work = env.load().lane_root / "supervisor-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as directory:
        binary = Path(directory) / "host"
        compiled = s.build_host(TOOLS.parent / "supervisor", binary, compiler)
        ensure(compiled.returncode == 0, compiled.stderr)
        done = subprocess.run([str(binary), "controls"], capture_output=True,
                              text=True, timeout=60, check=False)
        ensure(done.returncode == 0, done.stderr)
        ensure("fixed consumer controls" in done.stderr, "consumer controls did not report")
        for bad in ("9\n", "0 18\n", "1 8 3 0 0 2 0\n", "2 5 0\n", "garbage\n"):
            refused = subprocess.run([str(binary)], input=bad, capture_output=True,
                                     text=True, timeout=60, check=False)
            ensure(refused.returncode != 0, f"malformed C input accepted: {bad!r}")


def cases() -> list[Case]:
    return [
        Case("generated comparison domains", generated_domains_are_nonempty),
        Case("answers become exact reference equalities", answer_translation_uses_the_reference),
        Case("malformed answers fail closed", malformed_answers_are_refused),
        Case("native C consumer refusals", native_consumer_controls, lane="guest"),
    ]
