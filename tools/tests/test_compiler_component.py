# SPDX-License-Identifier: Apache-2.0
"""Per-coordinate controls for the reference component comparison."""

import json
import re
from pathlib import Path

from tests.harness import Case, ensure
from vos import compiler_component as cc
from vos import gallina


def _population_and_wrappers() -> None:
    root = Path(__file__).resolve().parents[2]
    gallina = (root / "tools/wasm-oracle/ipc_oracle.v").read_text(encoding="utf-8")
    c_source = (root / "tools/wasm-oracle/ipc_oracle.c").read_text(encoding="utf-8")
    g, c, ids = cc.wrappers(gallina, c_source)
    ensure(bool(ids) and len(set(ids)) == len(ids), "nonempty unique source-owned population")
    ensure(g.replace("Compile Wasm ipc_checks.", "Compile Wasm ipc_oracle.") == gallina,
           "the Gallina wrapper changes only the observed definition")
    ensure("observed[k] = checks[k]" in c and "return (int)(k + 1)" in c,
           "the C wrapper serializes actual checks and preserves first failure")
    reordered = c_source.replace("enumeration_checks(checks + n)", "temporary(checks + n)")
    reordered = reordered.replace("act_checks(checks + n)", "enumeration_checks(checks + n)")
    reordered = reordered.replace("temporary(checks + n)", "act_checks(checks + n)")
    for bad in (reordered, c_source.replace("c[n++] = same_bool(bit_at(0, 13), 1)",
                                          "c[n] = same_bool(bit_at(0, 13), 1)")):
        try:
            cc.wrappers(gallina, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("changed C family population accepted")


def _every_coordinate_and_shape() -> None:
    root = Path(__file__).resolve().parents[2]
    ids = cc.population((root / "tools/wasm-oracle/ipc_oracle.v").read_text(encoding="utf-8"))
    good = cc.decode(cc.encode(ids, (True,) * len(ids), 0), ids)
    for index in range(len(ids)):
        values = [True] * len(ids)
        values[index] = False
        altered = cc.decode(cc.encode(ids, tuple(values), index + 1), ids)
        try:
            cc.compare(good, altered)
        except ValueError as err:
            ensure(str(index + 1) in str(err), "the first disagreement is localized")
        else:
            raise AssertionError(f"coordinate {index + 1} survived")
    canonical = cc.encode(ids, good.values, 0)
    for label in ("missing", "extra", "reordered", "non-Boolean", "first-failure", "truncated"):
        raw = json.loads(canonical)
        if label == "missing":
            raw["checks"].pop()
        elif label == "extra":
            raw["checks"].append(raw["checks"][0])
        elif label == "reordered":
            raw["checks"][0], raw["checks"][1] = raw["checks"][1], raw["checks"][0]
        elif label == "non-Boolean":
            raw["checks"][0][1] = 1
        elif label == "first-failure":
            raw["first_failure"] = 1
        text = json.dumps(raw) if label != "truncated" else canonical[:-1]
        try:
            cc.decode(text, ids)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{label} observation accepted")


def _declared_switch_and_prover_release() -> None:
    root = Path(__file__).resolve().parents[2]
    lock = (root / "tools/opam/certirocq.lock").read_text(encoding="utf-8")
    listed = cc.installed(lock)
    ensure(len(listed) > 1 and f"rocq-certirocq.{gallina.CERTIROCQ_VERSION}" in listed,
           f"the snapshot's installed list is read: {listed[:3]}")
    # An imported switch's re-export drops the compiler section (F-496) and may order
    # its lines otherwise; it is still the snapshot's switch.
    reexport = re.sub(r"^compiler: \[.*?^\]\n", "", lock, flags=re.MULTILINE | re.DOTALL)
    head, _, tail = reexport.partition("installed: [\n")
    body, _, rest = tail.partition("]")
    reexport = head + "installed: [\n" + "".join(reversed(body.splitlines(keepends=True))) + "]" + rest
    ensure("compiler:" not in reexport and cc.installed(reexport) == listed,
           "a re-export without the compiler section installs the snapshot's packages")
    other = lock.replace(f'"rocq-certirocq.{gallina.CERTIROCQ_VERSION}"\n', "")
    ensure(cc.installed(other) != listed, "a switch lacking a package is another switch")
    for label, text in (("no list", "opam-version: \"2.0\"\n"),
                        ("an empty list", "installed: [\n]\n"),
                        ("a repeated package", 'installed: [\n  "a.1"\n  "a.1"\n]\n')):
        try:
            cc.installed(text)
        except ValueError:
            pass
        else:
            raise AssertionError(f"an export with {label} was read")
    release = gallina.ORACLE_ROCQ_VERSION
    banner = (f"The Rocq Prover, version {release}\n"
              f"compiled with OCaml {gallina.ORACLE_OCAML_VERSION}\n")
    ensure(cc.reports_release(banner, release), f"the banner reports {release}")
    ensure(cc.reports_release(f"version {release}.", release), "a closing full stop is no part")
    for wrong in (f"{release}0", f"{release}.1", f"{release}+dev", f"{release}~rc1", "9.3.0"):
        ensure(not cc.reports_release(banner.replace(release, wrong), release),
               f"version {wrong} is not {release}")


def cases() -> list[Case]:
    return [Case("source-owned-component-wrappers", _population_and_wrappers),
            Case("component-coordinate-and-shape-refusals", _every_coordinate_and_shape),
            Case("declared-switch-and-prover-release", _declared_switch_and_prover_release)]
