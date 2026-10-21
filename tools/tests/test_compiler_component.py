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
    ensure(cc.matches_oracle_snapshot(reexport, lock),
           "the real production snapshot recognizes its imported switch")
    if cc.legacy_oracle_snapshot(lock):
        metadata = f'opam-version: "2.0"\nversion: "{gallina.CERTIROCQ_VERSION}"\n'
        ensure(cc.matches_installed_oracle(metadata, lock, gallina.CERTIROCQ_VERSION),
               "the exact legacy snapshot retains installed-version recognition")
        ensure(not cc.matches_installed_oracle(metadata.replace(gallina.CERTIROCQ_VERSION, "0.9.1+9.2"),
                                               lock, "0.9.1+9.2"),
               "the legacy exception does not admit another installed version")
        for unknown in (lock + "\n", lock + "# unqualified version-only snapshot\n"):
            try:
                cc.matches_oracle_snapshot(reexport, unknown)
            except ValueError:
                pass
            else:
                raise AssertionError("unknown version-only snapshot bypassed frozen metadata")
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


def _frozen_oracle_provenance() -> None:
    # Same-version metadata must distinguish both obtaining and applying the fix.
    expected = '''opam-version: "2.0"
installed: [
  "ocaml.4.14.4"
  "rocq-certirocq.0.9.1+9.1"
]
package "rocq-certirocq" {
  version: "0.9.1+9.1"
  description: """A recipe with {braces}, # text and a package declaration."""
  patches: ["hd-val-971c1eb.patch"]
  build: [["make" "all"]]
  url {
    src: "https://example.invalid/certirocq-release.tar.gz"
    checksum: "sha512=release-source"
  }
  extra-source "hd-val-971c1eb.patch" {
    src: "https://github.com/CertiRocq/certirocq/commit/971c1eb1b5f0adecfc280872bd5b71b0d7f33a0f.patch"
    checksum: "sha256=f350152fd710608b912e9584ae6ef2a005fb8f7d2fc8b7b1e4b15911c9de109b"
  }
}
'''
    reformatted = expected.replace('  version:', '  # export comment\n    version:').replace(
        'patches: ["hd-val-971c1eb.patch"]', 'patches: [\n "hd-val-971c1eb.patch"\n ]')
    ensure(cc.matches_oracle_snapshot(reformatted, expected),
           "formatting/comments preserve a complete frozen recipe")
    for label, altered in (
        ("missing patch application", expected.replace('  patches: ["hd-val-971c1eb.patch"]\n', '')),
        ("wrong patch digest", expected.replace('sha256=f350152f', 'sha256=0350152f')),
        ("wrong patch source", expected.replace('/971c1eb1b5f0adec', '/071c1eb1b5f0adec')),
        ("wrong release digest", expected.replace('sha512=release-source', 'sha512=another-source')),
        ("changed build", expected.replace('"make" "all"', '"make" "other"'))):
        ensure(cc.installed(altered) == cc.installed(expected), "the package versions are unchanged")
        ensure(not cc.matches_oracle_snapshot(altered, expected), f"{label} cannot claim the frozen producer")
    unpatched = expected[:expected.index('package "rocq-certirocq"')]
    recipe = expected[expected.index('package "rocq-certirocq"'):]
    for malformed in (unpatched, expected + recipe, expected[:-2], expected + '"unterminated'):
        try:
            cc.matches_oracle_snapshot(malformed, expected)
        except ValueError:
            pass
        else:
            raise AssertionError("missing, duplicate or malformed package recipe accepted")
    metadata = recipe.split("{", 1)[1].rsplit("}", 1)[0]
    version = "0.9.1+9.1"
    without_version = metadata.replace(f'  version: "{version}"\n', "")
    for actual in (without_version, metadata.replace("version:", "version :"),
                   f'name : "rocq-certirocq"\n{metadata}'):
        ensure(cc.matches_installed_oracle(actual, expected, version),
               "last-installed metadata may omit or consistently retain its name/version")
    for label, actual in (
        ("approved overlay with unpatched installation", without_version.replace(
            '  patches: ["hd-val-971c1eb.patch"]\n', "")),
        ("another installed patch", without_version.replace('sha256=f350152f', 'sha256=0350152f')),
        ("another installed version", metadata.replace(version, "0.9.1+9.2")),
        ("another installed name", f'name: "another-package"\n{without_version}'),
        ("duplicate version", f'version: "{version}"\n{metadata}'),
        ("conflicting duplicate name", f'name: "rocq-certirocq"\nname: "another"\n{metadata}'),
        ("conflicting exported version", without_version),
        ("missing installed metadata", ""),
        ("malformed installed metadata", without_version + '"unterminated'),
        ("unbalanced installed metadata", without_version + "]")):
        try:
            target = expected.replace(version, "0.9.1+9.2") if label == "conflicting exported version" else expected
            accepted = cc.matches_installed_oracle(actual, target, version)
        except ValueError:
            accepted = False
        ensure(not accepted, f"{label} cannot claim the installed frozen producer")


def cases() -> list[Case]:
    return [Case("source-owned-component-wrappers", _population_and_wrappers),
            Case("component-coordinate-and-shape-refusals", _every_coordinate_and_shape),
            Case("declared-switch-and-prover-release", _declared_switch_and_prover_release),
            Case("frozen-oracle-source-and-patch-provenance", _frozen_oracle_provenance)]
