# SPDX-License-Identifier: Apache-2.0
"""Guard semantic staging against source drift and partial or invented output."""

import json
import re
from dataclasses import replace
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import rtl_width as width
from vos.corpus import find_root

_TEXT = "// upstream notice\npackage p; old old endpackage\n"
_NOTICE = "// Modified by VerifiedOS test\n"
_PIN = "a" * 40
_SOURCE = width.Source("core/p.sv", width.digest(_TEXT),
                       width.digest(_NOTICE + _TEXT.replace("old", "new")),
                       (width.Edit("old", "new", 2),))


def _refused(source: width.Source, text: str = _TEXT) -> None:
    try:
        width.transform(text, source, _NOTICE)
    except ValueError:
        return
    raise AssertionError("drifting transform accepted")


def _exact_edits_retain_notices() -> None:
    actual = width.transform(_TEXT, _SOURCE, _NOTICE)
    ensure(actual == _NOTICE + _TEXT.replace("old", "new"), "only named edits apply")
    ensure("// upstream notice" in actual, "upstream notice survives staging")


def _identity_and_match_guards() -> None:
    _refused(_SOURCE, _TEXT + "// drift\n")
    _refused(replace(_SOURCE, edits=(width.Edit("old", "new", 1),)))
    _refused(replace(_SOURCE, edits=(width.Edit("missing", "new", 1),)))
    _refused(replace(_SOURCE, output_sha256="0" * 64))
    _refused(replace(_SOURCE, edits=(width.Edit("", "new", 1),)))


def _registry() -> str:
    return json.dumps({"schema": "vos.rtl-width-transforms/1", "pin": _PIN,
                       "notice": _NOTICE, "sources": [{"path": _SOURCE.path,
                       "source_sha256": _SOURCE.source_sha256,
                       "output_sha256": _SOURCE.output_sha256,
                       "edits": [{"old": "old", "new": "new", "count": 2}]}]})


def _staging_requires_one_member_and_exact_pin() -> None:
    with sandbox_tree({width.REGISTRY: _registry(), f"{width.CORE}/core/p.sv": _TEXT}) as root:
        source = root / width.CORE / "core/p.sv"
        work = root / "out"
        with patch.object(width.subprocess, "run", return_value=CompletedProcess([], 0, _PIN, "")):
            for lines in ((), (str(source), str(source))):
                try:
                    width.stage(root, lines, work)
                except ValueError:
                    pass
                else:
                    raise AssertionError("missing or duplicated member accepted")
            ensure(not work.exists(), "refusal precedes every staged write")
            result = width.stage(root, ("unrelated.sv", str(source)), work)
            ensure(result[0] == "unrelated.sv" and Path(result[1]).is_file(),
                   "only the declared member is replaced")
            ensure((work / "scalar-width/core/p.diff").is_file(), "exact source diff retained")
            ensure((work / "scalar-width/receipt.json").is_file(), "identities retained")
        with patch.object(width.subprocess, "run", return_value=CompletedProcess([], 0, "b" * 40, "")):
            try:
                width.stage(root, (str(source),), work)
            except ValueError:
                pass
            else:
                raise AssertionError("wrong checkout pin accepted")


def _registry_rejects_unsafe_and_duplicate_sources() -> None:
    for path in ("../escape", "core/../../escape", "core\\p.sv"):
        data = json.loads(_registry())
        data["sources"][0]["path"] = path
        with sandbox_tree({width.REGISTRY: json.dumps(data)}) as root:
            try:
                width.load(root)
            except ValueError:
                pass
            else:
                raise AssertionError("unsafe source accepted")
    data = json.loads(_registry())
    data["sources"] *= 2
    with sandbox_tree({width.REGISTRY: json.dumps(data)}) as root:
        try:
            width.load(root)
        except ValueError:
            pass
        else:
            raise AssertionError("duplicate source accepted")


# The imported names the frozen format has no member for. A staged output that
# still carries one would compile the datapath against a format the model does
# not state, which is the failure the transform route exists to make visible.
_RETIRED = ("cap_meta_data_t", "get_cap_reg_meta_data", "cap_tval2_t", "cap_report_perms_t",
            "hperms_and_uperms_to_report_perms", "report_perms_to_hperms",
            "legalize_arch_perms", "get_cap_reg_flags", "set_cap_reg_flags",
            "CAP_TAG_VIOLATION", "CAP_SEAL_VIOLATION", "CAP_PERM_VIOLATION",
            "CAP_BOUNDS_VIOLATION", "CAP_INVALID_ADDRESS_VIOLATION",
            "CAP_INSTR_FETCH_FAULT", "CAP_DATA_ACCESS_FAULT", "CAP_JUMP_BRANCH_FAULT",
            "REG_ROOT_CAP", "cap_flags_t", "REG_ROOT", "clr_elevate", "clr_cap_level")

# The operations the profile's instruction surface does not carry and the
# imported decoder did: the two mode instructions, the mode-switch pair,
# capability reconstruction, the subset test and the representable-alignment
# mask (model/model/extensions/CHERI/cheri_insts.sail).
_EXCLUDED_OPS = ("GCMODE", "SCMODE", "MODESW_CAP", "MODESW_INT", "CBLD", "SCSS", "CRAM")

# Where a qualified name an edit writes has to be declared. The adapter exports
# the format package, so a name it reaches through that export counts as its own.
_PACKAGE_FILE = {"cva6_cheri_pkg": ("rtl/vos_cva6_cheri_pkg.sv", "rtl/vos_cheri_pkg.sv"),
                 "vos_cheri_pkg": ("rtl/vos_cheri_pkg.sv",),
                 "vos_scalar_width_pkg": ("rtl/vos_scalar_width_pkg.sv",)}

_QUALIFIED = re.compile(r"\b(cva6_cheri_pkg|vos_cheri_pkg|vos_scalar_width_pkg)::(\w+)")

# A bare `SENTRY_CAP` is retired and the edge pair is not, so the retired-name
# search has to see the whole identifier rather than a prefix of one.
_WORD = re.compile(r"\w+")

# The imported capability record's members that `vos_cheri_pkg::capability_t`
# does not declare. A staged output reading one of them names a field of a
# format the model does not state, which the elaborator cannot report while it
# is still stopping at an unresolved type or constant name, so the registry's
# own edits are held against the frozen field list here instead. The member
# form is matched rather than the bare word, so `.address` is not `.addr` and
# an `int_mode_o` port is not the deleted `.int_mode` field.
_ABSENT_MEMBER = re.compile(
    r"\.(addr|hperms|uperms|flags|res_lo|res_hi|EF|int_mode|permit_cap|cap_level"
    r"|permit_store_level|permit_elevate_level|fault_type|fault_cause|wpri)\b")


def _checked_in_registry_loads_with_exact_identities() -> None:
    pin, notice, sources = width.load(find_root())
    ensure(len(pin) == 40 and sources != (), "the checked-in registry names a pin and sources")
    ensure(notice.startswith("// Modified by VerifiedOS"), "the modification notice is carried")
    for source in sources:
        ensure(source.source_sha256 != source.output_sha256,
               f"{source.path}: a transform that changes nothing is not a transform")
        ensure(all(edit.old != edit.new for edit in source.edits),
               f"{source.path}: a replacement that rewrites its match to itself is not one")
        # Two rows sharing a match text make the ordered application decide which
        # count is checked against what, so each row's matches are distinct.
        olds = [edit.old for edit in source.edits]
        ensure(len(set(olds)) == len(olds),
               f"{source.path}: two replacements name the same match text")


def _no_edit_reintroduces_a_retired_name() -> None:
    _, _, sources = width.load(find_root())
    for source in sources:
        for edit in source.edits:
            words = set(_WORD.findall(edit.new))
            found = sorted(name for name in (*_RETIRED, "SENTRY_CAP") if name in words)
            ensure(not found,
                   f"{source.path}: a staged output reintroduces {', '.join(found)}")


def _no_edit_reads_an_absent_member() -> None:
    _, _, sources = width.load(find_root())
    for source in sources:
        for edit in source.edits:
            found = sorted(set(_ABSENT_MEMBER.findall(edit.new)))
            ensure(not found,
                   f"{source.path}: a staged output reads .{', .'.join(found)}, "
                   "which the frozen capability record does not declare")


def _every_frozen_name_an_edit_uses_is_declared() -> None:
    root = find_root()
    text = {rel: (root / rel).read_text(encoding="utf-8")
            for rels in _PACKAGE_FILE.values() for rel in rels}
    _, _, sources = width.load(root)
    used = 0
    for source in sources:
        for edit in source.edits:
            for package, name in _QUALIFIED.findall(edit.new):
                used += 1
                ensure(any(name in set(_WORD.findall(text[rel]))
                           for rel in _PACKAGE_FILE[package]),
                       f"{source.path}: {package}::{name} is declared by no authored source")
    ensure(used > 0, "the registry reaches the authored packages by name")


def _excluded_operations_decode_as_illegal() -> None:
    """Each excluded operation loses its decode row, and no edit names it again."""
    _, _, sources = width.load(find_root())
    rows = {source.path: source for source in sources}
    decoder = rows.get("core/decoder.sv")
    if decoder is None:
        raise AssertionError("the decoder is staged")
    for op in _EXCLUDED_OPS:
        named = f"ariane_pkg::{op}"
        ensure(any(f"instruction_o.op = {named};" in edit.old for edit in decoder.edits),
               f"core/decoder.sv: no edit removes the decode row of {op}")
        for source in sources:
            ensure(all(named not in edit.new for edit in source.edits),
                   f"{source.path}: a staged output names the excluded {op}")


def _reset_grants_follow_the_model() -> None:
    """c1, c2 and c3 take the data, seal and unseal roots, every other register null."""
    _, _, sources = width.load(find_root())
    text = "".join(edit.new for source in sources
                   if source.path == "core/include/ariane_pkg.sv" for edit in source.edits)
    grants = re.search(r"REG_RESET_FILE\s*=\s*CheriPresent\s*\?\s*\{\{28\{REG_NULL\}\},\s*"
                       r"cva6_cheri_pkg::REG_ROOT_UNSEAL_CAP,\s*cva6_cheri_pkg::REG_ROOT_SEAL_CAP,"
                       r"\s*cva6_cheri_pkg::REG_ROOT_DATA_CAP,\s*REG_NULL\}", text)
    ensure(grants is not None, "the reset file grants c3, c2 and c1 in ext_reset's order")
    iro = "".join(edit.new for source in sources
                  if source.path == "core/issue_read_operands.sv" for edit in source.edits)
    ensure("ariane_pkg::REG_RESET_FILE" in iro, "the register file takes the reset grants")


def cases() -> list[Case]:
    return [Case(fn.__name__.lstrip("_"), fn) for fn in (
        _exact_edits_retain_notices, _identity_and_match_guards,
        _staging_requires_one_member_and_exact_pin, _registry_rejects_unsafe_and_duplicate_sources,
        _checked_in_registry_loads_with_exact_identities, _no_edit_reintroduces_a_retired_name,
        _no_edit_reads_an_absent_member, _every_frozen_name_an_edit_uses_is_declared,
        _excluded_operations_decode_as_illegal, _reset_grants_follow_the_model,
    )]
