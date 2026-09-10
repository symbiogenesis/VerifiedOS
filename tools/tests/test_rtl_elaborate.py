# SPDX-License-Identifier: Apache-2.0
"""The elaboration seam: an authored source standing for an imported one, and the
diff that tells an authored replacement from a finding.

Two mechanisms, and both are held here because neither can be held by a run. The
elaboration reads two gitlinks, one of which no checkout of this repository has
initialized, so the file list is composed against a synthetic manifest and the diff
is decided over the two inventories as sets. That is the whole of what each decides:
composition is a text transform over a manifest, and the partition is set algebra over
two module-kind sets and two attribution maps.

A row also places what its authored source requires, the imported manifest naming no
authored package: once, immediately ahead of it, refused by name when absent.

The one row the table carries today, the format adapter, is held here as well: that
the declaration itself composes against the synthetic manifest and attributes nothing,
that the adapter is in the standalone-lintable set too, that the file on disk declares
the imported package's name and no member of the delta's deletion rows, and that its
cause table is the two Sail files' it restates. Those last two read the tree rather
than a sandbox, because what they hold is the file the row stands in the imported
build.

Six edges carry the weight. An authored source stands at the *first* imported line it
replaces and the rest are dropped, so one authored file for a tree of imported ones is
one entry where the tree was. A declared substitution that reaches no line of the
manifest is a refusal rather than a file list one source short, because the two are
indistinguishable in the result and opposite in meaning. An imported source the manifest
names and the checkout does not carry is the third refusal, its line gone from the build
and the kinds it declared unreadable. A line dropped as unreached is not then available
to be substituted, which is the first refusal's sharpest case. A module kind is
attributed by what the SystemVerilog *declares*, so a comment carrying a module
declaration is not one. And a declared name is reduced the way a netlist name is, so the
two name spaces join rather than reporting one module as two findings.
"""

import json
import re
from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import provenance
from vos.cli import rtl
from vos.corpus import find_root

# A manifest in the imported core's own shape: a comment, a repository variable, an
# include directory, a tree this configuration does not reach, the configuration package
# left to the caller, and the sources a substitution stands in for.
_MANIFEST = """\
// Manifest for the CORE RTL model.
${CVA6_REPO_DIR}/vendor/pulp-platform/fpga-support/rtl/SyncDpRam.sv

+incdir+${CVA6_REPO_DIR}/core/include/

// Floating point unit
${CVA6_REPO_DIR}/core/cvfpu/src/fpnew_pkg.sv

${CVA6_REPO_DIR}/core/include/config_pkg.sv
${CVA6_REPO_DIR}/core/include/${TARGET_CFG}_config_pkg.sv
${CVA6_REPO_DIR}/core/cache_subsystem/wt_dcache.sv
${CVA6_REPO_DIR}/core/cache_subsystem/wt_dcache_mem.sv
${CVA6_REPO_DIR}/core/store_unit.sv
${CVA6_REPO_DIR}/core/include/cva6_cheri_pkg.sv
"""

_FLIST = f"{rtl.CORE}/{rtl.CORE_FLIST}"
_DCACHE = "core/cache_subsystem/wt_dcache.sv"
_DCACHE_MEM = "core/cache_subsystem/wt_dcache_mem.sv"
_FORMAT = "core/include/cva6_cheri_pkg.sv"

_SRAM = rtl.Substitution(imported=(_DCACHE, _DCACHE_MEM), authored="rtl/vos_sram.sv")

_TREE = {
    _FLIST: _MANIFEST,
    f"{rtl.CORE}/{_DCACHE}": "module wt_dcache ();\nendmodule\n",
    f"{rtl.CORE}/{_DCACHE_MEM}": "module wt_dcache_mem ();\nendmodule\n",
    "rtl/vos_sram.sv": "// module wt_dcache is what this replaces\n"
                       "module vos_sram ();\nendmodule\n",
    provenance.CONFIG: "package vos_c_class_config_pkg;\nendpackage\n",
}


def _compose(root: Path, *subs: rtl.Substitution) -> rtl.FileList:
    return rtl._file_list(root, root / provenance.CONFIG, subs)


def _substitution_placed_once_at_the_first_line() -> None:
    with sandbox_tree(_TREE) as root:
        files = _compose(root, _SRAM)
    authored = str(root / "rtl/vos_sram.sv")
    ensure(files.lines.count(authored) == 1,
           f"one authored source is one entry, got {files.lines.count(authored)}")
    ensure(not any(_DCACHE in line or _DCACHE_MEM in line for line in files.lines),
           f"both replaced imported sources are gone, got {files.lines!r}")
    # The manifest's own order decides where the replacement sits: after the
    # configuration package it followed and before the source that followed it.
    where = files.lines.index(authored)
    ensure(files.lines[where - 1].endswith("vos_c_class_config_pkg.sv"),
           f"the authored source sits at the first line it replaced, got "
           f"{files.lines[where - 1]!r}")
    ensure(files.lines[where + 1].endswith("store_unit.sv"),
           f"and the rest of the manifest follows it, got {files.lines[where + 1]!r}")
    ensure(files.taken == (_SRAM,), f"the substitution read back as {files.taken!r}")
    ensure(not files.refusals, f"a matched substitution refuses nothing, got "
                               f"{files.refusals!r}")


def _configuration_and_unreached_still_apply() -> None:
    with sandbox_tree(_TREE) as root:
        files = _compose(root, _SRAM)
    ensure(str(root / provenance.CONFIG) in files.lines,
           "the configuration package is still substituted at its own line")
    ensure(not any("cvfpu" in line for line in files.lines),
           f"the trees this configuration does not reach are still dropped, got "
           f"{files.lines!r}")
    ensure(not any(rtl.CORE_VAR in line for line in files.lines),
           f"the repository variable is still expanded, got {files.lines!r}")


def _empty_table_composes_the_manifest_alone() -> None:
    with sandbox_tree(_TREE) as root:
        files = _compose(root)
        with_sub = _compose(root, _SRAM)
    ensure(files.taken == () and files.unmatched == () and files.missing == (),
           "an empty declaration decides nothing about any substitution")
    ensure(any(_DCACHE in line for line in files.lines),
           "and leaves every imported source in the list it composed")
    ensure(len(files.lines) == len(with_sub.lines) + 1,
           f"two imported entries become one authored entry, {len(files.lines)} "
           f"against {len(with_sub.lines)}")


def _unmatched_declaration_is_a_refusal() -> None:
    absent = rtl.Substitution(imported=("core/nowhere.sv",),
                              authored="rtl/vos_sram.sv")
    with sandbox_tree(_TREE) as root:
        files = _compose(root, absent)
    ensure(files.taken == (), "a substitution matching no line has not been taken")
    ensure(files.unmatched == (("rtl/vos_sram.sv", "core/nowhere.sv"),),
           f"the unmatched declaration read back as {files.unmatched!r}")
    ensure(len(files.refusals) == 1 and files.refusals[0].startswith("FAIL"),
           f"an unmatched declaration is one refusal, got {files.refusals!r}")


def _partly_matched_declaration_is_a_refusal() -> None:
    # The edge a per-substitution verdict has to have: one of two imported sources
    # matched leaves the other in the build beside the authored replacement.
    partial = rtl.Substitution(imported=(_DCACHE, "core/nowhere.sv"),
                               authored="rtl/vos_sram.sv")
    with sandbox_tree(_TREE) as root:
        files = _compose(root, partial)
    ensure(files.taken == (),
           "a substitution one of whose sources missed has not been taken")
    ensure(files.unmatched == (("rtl/vos_sram.sv", "core/nowhere.sv"),),
           f"the missed source alone is unmatched, got {files.unmatched!r}")


def _unreached_line_cannot_be_substituted() -> None:
    # A line dropped as unreached is not available to stand in for, and the two ways of
    # losing a line read alike in the result: the refusal is what tells them apart.
    dropped = rtl.Substitution(imported=("core/cvfpu/src/fpnew_pkg.sv",),
                               authored="rtl/vos_sram.sv")
    with sandbox_tree(_TREE) as root:
        files = _compose(root, dropped)
    ensure(files.taken == () and len(files.unmatched) == 1,
           f"substituting for an unreached line refuses, got {files.unmatched!r}")


def _missing_authored_source_is_a_refusal() -> None:
    gone = rtl.Substitution(imported=(_DCACHE,), authored="rtl/vos_nothing.sv")
    with sandbox_tree(_TREE) as root:
        files = _compose(root, gone)
    ensure(files.missing == ("rtl/vos_nothing.sv",),
           f"an authored source not in the checkout read back as {files.missing!r}")
    ensure(len(files.refusals) == 1,
           f"and is one refusal rather than a silent entry, got {files.refusals!r}")


def _imported_source_the_checkout_lacks_is_a_refusal() -> None:
    # The third way a declaration can mean nothing, and the quiet one: the line matched,
    # so it is out of the build, and the file is not on disk, so the kinds it declared
    # are unreadable and the substitution's displacements would read as the parameters'
    # removals, which is the one mis-attribution the partition exists to prevent.
    ghost = rtl.Substitution(imported=("core/store_unit.sv",),
                             authored="rtl/vos_sram.sv")
    with sandbox_tree(_TREE) as root:
        files = _compose(root, ghost)
    ensure(files.unmatched == (),
           f"the declaration did reach a line of the manifest, got {files.unmatched!r}")
    ensure(files.absent == (("rtl/vos_sram.sv", "core/store_unit.sv"),),
           f"the unreadable imported source read back as {files.absent!r}")
    ensure(files.taken == (),
           "and the row is not one the diff attributes by, its displacements being "
           "unreadable")
    ensure(len(files.refusals) == 1 and files.refusals[0].startswith("FAIL"),
           f"which is one refusal rather than a silent skip, got {files.refusals!r}")


def _package_row_is_taken_and_attributes_nothing() -> None:
    # R1b's own first row: a package standing for a package. It is taken, and both
    # attribution maps are empty, so the partition says nothing about it at all.
    row = rtl.Substitution(imported=(_FORMAT,), authored="rtl/vos_format_pkg.sv")
    tree = dict(_TREE)
    tree[f"{rtl.CORE}/{_FORMAT}"] = "package cva6_cheri_pkg;\nendpackage\n"
    tree["rtl/vos_format_pkg.sv"] = "package vos_cheri_pkg;\nendpackage\n"
    with sandbox_tree(tree) as root:
        files = _compose(root, row)
        introduced, displaced = rtl._substitution_modules(root, files.taken)
    ensure(files.taken == (row,) and not files.refusals,
           f"the row is taken and refuses nothing, got {files.taken!r}")
    ensure(introduced == {} and displaced == {},
           f"and attributes nothing on either side, got {introduced!r} {displaced!r}")


def _declared_row_is_taken_and_attributes_nothing() -> None:
    # The row `SUBSTITUTIONS` itself carries, composed against the synthetic manifest
    # rather than a private copy of it, so a change to the declaration is a change
    # here: it is taken at the imported package's own line, refuses nothing, and
    # attributes nothing on either side, both files declaring a package and no module.
    tree = dict(_TREE)
    tree[f"{rtl.CORE}/{rtl.IMPORTED_FORMAT_PACKAGE}"] = "package cva6_cheri_pkg;\nendpackage\n"
    tree[rtl.FORMAT_PACKAGE] = "package vos_cheri_pkg;\nendpackage\n"
    tree[rtl.ADAPTER_PACKAGE] = ("package cva6_cheri_pkg;\n  import vos_cheri_pkg::*;\n"
                                 "endpackage\n")
    with sandbox_tree(tree) as root:
        files = _compose(root, *rtl.SUBSTITUTIONS)
        introduced, displaced = rtl._substitution_modules(root, files.taken)
    ensure(len(rtl.SUBSTITUTIONS) == 1,
           f"one row is declared today, the first seam's, got {rtl.SUBSTITUTIONS!r}")
    ensure(files.taken == rtl.SUBSTITUTIONS and not files.refusals,
           f"the declared row is taken and refuses nothing, got {files.taken!r} "
           f"{files.refusals!r}")
    ensure(introduced == {} and displaced == {},
           f"and attributes nothing on either side, got {introduced!r} {displaced!r}")
    authored = str(root / rtl.ADAPTER_PACKAGE)
    ensure(files.lines.count(authored) == 1
           and not any(rtl.IMPORTED_FORMAT_PACKAGE in line for line in files.lines),
           f"the adapter stands where the imported package did, got {files.lines!r}")
    where = files.lines.index(authored)
    ensure(files.lines[where - 1] == str(root / rtl.FORMAT_PACKAGE),
           f"with the format package it imports placed just ahead of it, got "
           f"{files.lines[where - 1]!r}")
    ensure(files.lines[where - 2].endswith("store_unit.sv"),
           f"at the imported package's own line of the manifest, got "
           f"{files.lines[where - 2]!r}")


def _required_source_is_placed_once_and_refused_when_absent() -> None:
    # The imported manifest names no authored package, so a row has to place what its
    # source imports: once, ahead of it, at the line it replaces, and two rows requiring
    # one package place it once. A required source not on disk is the same refusal an
    # absent authored source is, because the arm would compile without it either way.
    first = rtl.Substitution(imported=(_DCACHE,), authored="rtl/vos_sram.sv",
                             requires=("rtl/vos_fmt.sv",))
    second = rtl.Substitution(imported=(_FORMAT,), authored="rtl/vos_fmt_adapter.sv",
                              requires=("rtl/vos_fmt.sv",))
    tree = dict(_TREE)
    tree[f"{rtl.CORE}/{_FORMAT}"] = "package cva6_cheri_pkg;\nendpackage\n"
    tree["rtl/vos_fmt.sv"] = "package vos_fmt;\nendpackage\n"
    tree["rtl/vos_fmt_adapter.sv"] = "package cva6_cheri_pkg;\nendpackage\n"
    with sandbox_tree(tree) as root:
        files = _compose(root, first, second)
        alone = _compose(root, first)
    required = str(root / "rtl/vos_fmt.sv")
    ensure(files.taken == (first, second) and not files.refusals,
           f"both rows are taken, got {files.taken!r} {files.refusals!r}")
    ensure(files.lines.count(required) == 1,
           f"a source two rows require is placed once, got {files.lines.count(required)}")
    ensure(files.lines.index(required) + 1 == files.lines.index(str(root / "rtl/vos_sram.sv")),
           "immediately ahead of the first source that requires it")
    ensure(len(files.lines) == len(alone.lines),
           f"and the second row adds no entry for it, {len(files.lines)} against "
           f"{len(alone.lines)}")
    gone = rtl.Substitution(imported=(_DCACHE,), authored="rtl/vos_sram.sv",
                            requires=("rtl/vos_nowhere.sv",))
    with sandbox_tree(_TREE) as root:
        refused = _compose(root, gone)
    ensure(refused.missing == ("rtl/vos_nowhere.sv",) and len(refused.refusals) == 1,
           f"a required source not in the checkout is one refusal, got "
           f"{refused.missing!r} {refused.refusals!r}")


def _adapter_sits_in_both_declarations() -> None:
    # The lint gate reaches no substituted source in general, a source written to stand
    # in the imported datapath compiling against the imported packages; the adapter
    # imports the format package alone, so it is the one row that also lints alone.
    ensure(rtl.SUBSTITUTIONS[0].authored == rtl.ADAPTER_PACKAGE,
           f"the first row stands the adapter, got {rtl.SUBSTITUTIONS[0]!r}")
    ensure(rtl.ADAPTER_PACKAGE in rtl.AUTHORED,
           f"and the adapter is in the standalone-lintable set, got {rtl.AUTHORED!r}")
    ensure(rtl.AUTHORED.index(rtl.FORMAT_PACKAGE) < rtl.AUTHORED.index(rtl.ADAPTER_PACKAGE),
           "after the format package it imports")


# Every member the delta's §2.1 deletion rows name, plus the two the structure rows
# replace with a pair or a split: an adapter that grows one of these elaborates the
# datapath against the wrong format, which is the trap the delta's closing line names.
_DELETED: tuple[str, ...] = (
    "CAP_UPERMS_WIDTH", "CAP_UPERMS_SHIFT", "CAP_RSERV_HI_WIDTH", "CAP_RSERV_LO_WIDTH",
    "CAP_E_HALF_WIDTH", "CAP_GUEST_EXCEPTION", "CAP_INSTR_FETCH_FAULT",
    "CAP_DATA_ACCESS_FAULT", "CAP_JUMP_BRANCH_FAULT", "CAP_TAG_VIOLATION",
    "CAP_SEAL_VIOLATION", "CAP_PERM_VIOLATION", "CAP_INVALID_ADDRESS_VIOLATION",
    "CAP_BOUNDS_VIOLATION", "SENTRY_CAP", "REG_ROOT_CAP", "resw_lo_t", "resw_hi_t",
    "upermsw_t", "hmw_t", "hcmw_t", "hew_t", "cap_tval2_t", "fault_type", "fault_cause",
    "cap_hperms_t", "cap_report_perms_t", "cap_flags_t", "int_mode", "cap_fmt_t",
    "EMBEDDED_EXP", "IMPLIED_EXP", "cap_implied_exp_fmt_t", "cap_embedded_exp_fmt_t",
    "cap_cbounds_t", "cap_meta_data_t", "hperms", "uperms", "res_hi", "res_lo", "EF",
    "legalize_arch_perms", "get_cap_reg_flags", "set_cap_reg_flags",
    "is_offset_in_range", "bot3z", "add_b1000", "mask",
)


def _adapter_text() -> str:
    text = (find_root() / rtl.ADAPTER_PACKAGE).read_text(encoding="utf-8")
    return rtl.LINE_COMMENT_RE.sub("", rtl.BLOCK_COMMENT_RE.sub("", text))


def _adapter_carries_no_deleted_member() -> None:
    # Read from the tree rather than a sandbox, because what is held is the file the
    # row stands in the imported build. Comments go first, the header naming several
    # of these to say they are absent.
    bare = _adapter_text()
    ensure(re.search(r"^\s*package\s+cva6_cheri_pkg\s*;", bare, re.MULTILINE) is not None,
           "the adapter declares the imported package's own name")
    ensure(rtl._declared_modules(bare) == frozenset(),
           f"and no module, got {sorted(rtl._declared_modules(bare))!r}")
    imports = re.findall(r"\bimport\s+(\w+)::", bare)
    ensure(imports == ["vos_cheri_pkg"],
           f"it imports the format package and nothing else, got {imports!r}")
    hits = [name for name in _DELETED if re.search(rf"\b{re.escape(name)}\b", bare)]
    ensure(hits == [], f"a deletion-row member has grown back: {hits!r}")


def _cause_table_is_the_models() -> None:
    # Independently read the generated region's values; K-104 holds its bytes by
    # regeneration, and this comparison also checks what that generator emitted.
    root = find_root()
    causes = (root / "model/model/core/cap_causes.sail").read_text(encoding="utf-8")
    ext = (root / "model/model/core/types_ext.sail").read_text(encoding="utf-8")
    bare = _adapter_text()
    model = dict(re.findall(r"(CapEx_\w+)\s*=>\s*0b([01]+)", causes))
    ours = dict(re.findall(r"(CapEx_\w+)\s*=\s*\d+'b([01]+)", bare))
    ensure(len(model) == 11, f"the model states eleven cause codes, got {len(model)}")
    ensure(ours == model, f"the adapter's cause table is the model's, got {ours!r} "
                          f"against {model!r}")
    pcc_model = re.search(r"PCC_IDX\s*:\s*capreg_idx\s*=\s*0b([01]+)", causes)
    pcc_ours = re.search(r"PCC_IDX\s*=\s*\d+'b([01]+)", bare)
    ensure(pcc_model is not None and pcc_ours is not None
           and pcc_ours.group(1) == pcc_model.group(1),
           f"PCC reports as the model's index, got {pcc_ours!r} against {pcc_model!r}")
    exc_model = re.search(r"EXC_CHERI\s*<->\s*0b([01]+)", ext)
    exc_ours = re.search(r"CAP_EXCEPTION\s*=\s*(\d+)\s*;", bare)
    ensure(exc_model is not None and exc_ours is not None
           and int(exc_ours.group(1)) == int(exc_model.group(1), 2),
           f"the mcause code is the model's, got {exc_ours!r} against {exc_model!r}")


def _double_underscore_joins_one_name_space() -> None:
    # A declared name is reduced the way a netlist name is. Without that, a module whose
    # own name carries a double underscore joins to nothing and is reported at once as
    # inert and as unexplained: two findings out of one module, both false.
    declared = rtl._declared_modules("module vos_sram__bank ();\nendmodule\n")
    ensure(declared == frozenset({"vos_sram"}),
           f"the declared name reduces to its kind, got {sorted(declared)!r}")
    netlist = {rtl._kind("vos_sram__bank"), rtl._kind("vos_sram__bank__Vab12")}
    diff = rtl._diff(netlist, set(), dict.fromkeys(declared, "rtl/vos_sram.sv"), {})
    ensure(diff.introduced == ("vos_sram",) and diff.findings == 0,
           f"so the module is one introduction and no finding, got {diff!r}")


def _declared_modules_are_declarations() -> None:
    text = ("// module commented_out ();\n"
            "/* module blocked_out (); */\n"
            "package a_package;\nendpackage\n"
            "module vos_sram #(parameter int W = 8) ();\n"
            "endmodule\n"
            "  module vos_sram_bank ();\n"
            "  endmodule\n")
    found = rtl._declared_modules(text)
    ensure(found == frozenset({"vos_sram", "vos_sram_bank"}),
           f"the declarations read back as {sorted(found)!r}")


def _substitution_modules_read_both_sides() -> None:
    with sandbox_tree(_TREE) as root:
        introduced, displaced = rtl._substitution_modules(root, (_SRAM,))
    ensure(introduced == {"vos_sram": "rtl/vos_sram.sv"},
           f"the authored side read back as {introduced!r}")
    ensure(displaced == {"wt_dcache": _DCACHE, "wt_dcache_mem": _DCACHE_MEM},
           f"the imported side read back as {displaced!r}")


def _diff_names_an_authored_introduction() -> None:
    diff = rtl._diff({"cva6", "vos_sram"}, {"cva6", "wt_dcache"},
                     {"vos_sram": "rtl/vos_sram.sv"}, {"wt_dcache": _DCACHE})
    ensure(diff.introduced == ("vos_sram",),
           f"the authored addition is an introduction, got {diff.introduced!r}")
    ensure(diff.unexplained == (),
           f"and is not a finding, got {diff.unexplained!r}")
    ensure(diff.findings == 0, f"so the run has no finding, got {diff.findings}")


def _diff_still_fails_on_an_undeclared_addition() -> None:
    diff = rtl._diff({"cva6", "surprise"}, {"cva6"}, {}, {})
    ensure(diff.unexplained == ("surprise",),
           f"an addition no authored source declares is a finding, got "
           f"{diff.unexplained!r}")
    ensure(diff.findings == 1, f"and is counted, got {diff.findings}")


def _diff_keeps_the_parameters_removals_apart() -> None:
    diff = rtl._diff({"cva6", "vos_sram"}, {"cva6", "wt_dcache", "bht"},
                     {"vos_sram": "rtl/vos_sram.sv"}, {"wt_dcache": _DCACHE})
    ensure(diff.removed == ("bht",),
           f"only what no substitution accounts for is the parameters', got "
           f"{diff.removed!r}")
    ensure(diff.displaced == ("wt_dcache",),
           f"and what a replaced source declared is reported apart, got "
           f"{diff.displaced!r}")


def _diff_reports_an_authored_module_that_never_elaborated() -> None:
    diff = rtl._diff({"cva6"}, {"cva6"},
                     {"vos_sram": "rtl/vos_sram.sv"}, {})
    ensure(diff.inert == ("vos_sram",),
           f"an authored module in neither netlist is a finding, got {diff.inert!r}")
    ensure(diff.findings == 1, f"and is counted, got {diff.findings}")


def _drop_in_replacement_moves_nothing() -> None:
    # The commonest shape: an authored source declaring the name the imported one did.
    # Neither set moves, so the diff says nothing rather than saying it twice.
    diff = rtl._diff({"cva6", "store_unit"}, {"cva6", "store_unit"},
                     {"store_unit": "rtl/vos_store_unit.sv"},
                     {"store_unit": "core/store_unit.sv"})
    ensure(diff == rtl.Diff((), (), (), (), ()),
           f"a drop-in replacement partitions to nothing, got {diff!r}")


# Authored fixture in Verilator 5.052's NETLIST/modulesp schema. Two middle
# instances each contain two leaves, so four CELL declarations represent seven
# elaborated instances including the top. The two leaf specializations are one
# kind; package variables are declarations, but internal constant-pool nodes are not.
_JSON_INVENTORY = """{
  "type":"NETLIST", "modulesp":[
    {"type":"MODULE", "name":"top", "level":1, "stmtsp":[
      {"type":"VAR", "name":"signal"},
      {"type":"VARREF", "name":"signal"},
      {"type":"CELL", "name":"m0", "modName":"middle"},
      {"type":"CELL", "name":"m1", "modName":"middle"}]},
    {"type":"MODULE", "name":"middle", "level":2, "stmtsp":[
      {"type":"VAR", "name":"signal"},
      {"type":"BEGIN", "stmtsp":[
        {"type":"CELL", "name":"l0", "modName":"leaf__W1"},
        {"type":"CELL", "name":"l1", "modName":"leaf__W2"}]}]},
    {"type":"MODULE", "name":"leaf__W1", "level":3,
      "stmtsp":[{"type":"VAR", "name":"signal"}]},
    {"type":"MODULE", "name":"leaf__W2", "level":3,
      "stmtsp":[{"type":"VAR", "name":"signal"}]},
    {"type":"PACKAGE", "name":"config_pkg",
      "stmtsp":[{"type":"VAR", "name":"Width"}]}
  ], "miscsp":[{"type":"CONSTPOOL", "modulep":[
    {"type":"MODULE", "name":"@CONST-POOL@",
      "stmtsp":[{"type":"VAR", "name":"internal"}]}]}]
} """


def _json_inventory_preserves_hierarchy_and_declarations() -> None:
    with sandbox_tree({"inventory.json": _JSON_INVENTORY}) as root:
        actual = rtl._inventory(root / "inventory.json")
    ensure(actual == ({"top", "middle", "leaf"}, 7, 5),
           f"module kinds, expanded cells and declaration counts differ: {actual!r}")


def _json_inventory_rejects_unresolved_hierarchy() -> None:
    broken = _JSON_INVENTORY.replace('"modName":"leaf__W1"', '"modName":"missing"')
    with sandbox_tree({"inventory.json": broken}) as root:
        try:
            rtl._inventory(root / "inventory.json")
        except ValueError as error:
            ensure("unresolved module 'missing'" in str(error),
                   f"an unresolved cell should be named, got {error}")
        else:
            raise AssertionError("an unresolved instance yielded an incomplete cell count")


def _json_inventory_rejects_absent_netlist() -> None:
    with sandbox_tree({"inventory.json": "{}"}) as root:
        try:
            rtl._inventory(root / "inventory.json")
        except ValueError as error:
            ensure("NETLIST" in str(error), "the refusal should identify the missing AST")
        else:
            raise AssertionError("an absent netlist yielded an empty inventory")


def _json_inventory_validates_all_definitions() -> None:
    defects = (
        {"type": "MODULE", "level": 3},
        {"type": "MODULE", "name": "leaf__W1", "level": 3},
        {"type": "MODULE", "name": "orphan", "level": 3,
         "stmtsp": [{"type": "CELL", "modName": "missing"}]},
        {"type": "MODULE", "name": "orphan", "level": 3,
         "stmtsp": [{"type": "CELL", "modName": "orphan"}]},
        "malformed definition",
    )
    for defect in defects:
        tree = json.loads(_JSON_INVENTORY)
        tree["modulesp"].append(defect)
        with sandbox_tree({"inventory.json": json.dumps(tree)}) as root:
            try:
                rtl._inventory(root / "inventory.json")
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError(f"invalid module definition was silently accepted: {defect!r}")


def _ram_compatibility_is_shared_and_preserves_upstream() -> None:
    source = "// upstream notice\nmodule sram;\n.cfg_rsp_o( ),\n.cfg_rsp_o( )\nendmodule\n"
    tree = {**_TREE, rtl.RAM_PORT_SOURCE: source,
            _FLIST: _MANIFEST + "${CVA6_REPO_DIR}/common/local/util/sram.sv\n"}
    with sandbox_tree(tree) as root:
        for arm, files in (("baseline", _compose(root)), ("curated", _compose(root, _SRAM))):
            lines = rtl._stage_ram_compatibility(root, files, root / arm)
            staged = root / arm / "compatibility/cva6-sram.sv"
            ensure(str(staged) in lines, f"{arm} must compile the staged compatibility source")
            ensure(staged.read_text() == source.replace(".cfg_rsp_o(", ".cfg_o("),
                   "only the two named-port spellings may change")
        ensure((root / rtl.RAM_PORT_SOURCE).read_text() == source,
               "the upstream source must remain untouched")
        (root / rtl.RAM_PORT_SOURCE).write_text(source.replace(".cfg_rsp_o(", ".cfg_o(", 1))
        try:
            rtl._stage_ram_compatibility(root, _compose(root), root / "unexpected")
        except ValueError as error:
            ensure("expected 2" in str(error), "upstream interface drift must be reported")
        else:
            raise AssertionError("changed upstream interface silently entered the build")


def cases() -> list[Case]:
    return [
        Case("json-inventory-validates-all-definitions", _json_inventory_validates_all_definitions),
        Case("ram-compatibility-shared-and-upstream-preserved",
             _ram_compatibility_is_shared_and_preserves_upstream),
        Case("json-inventory-preserves-hierarchy-and-declarations",
             _json_inventory_preserves_hierarchy_and_declarations),
        Case("json-inventory-rejects-unresolved-hierarchy",
             _json_inventory_rejects_unresolved_hierarchy),
        Case("json-inventory-rejects-absent-netlist",
             _json_inventory_rejects_absent_netlist),
        Case("substitution-placed-once-at-the-first-line",
             _substitution_placed_once_at_the_first_line),
        Case("configuration-and-unreached-still-apply",
             _configuration_and_unreached_still_apply),
        Case("empty-table-composes-the-manifest-alone",
             _empty_table_composes_the_manifest_alone),
        Case("unmatched-declaration-is-a-refusal",
             _unmatched_declaration_is_a_refusal),
        Case("partly-matched-declaration-is-a-refusal",
             _partly_matched_declaration_is_a_refusal),
        Case("unreached-line-cannot-be-substituted",
             _unreached_line_cannot_be_substituted),
        Case("missing-authored-source-is-a-refusal",
             _missing_authored_source_is_a_refusal),
        Case("imported-source-the-checkout-lacks-is-a-refusal",
             _imported_source_the_checkout_lacks_is_a_refusal),
        Case("package-row-is-taken-and-attributes-nothing",
             _package_row_is_taken_and_attributes_nothing),
        Case("declared-row-is-taken-and-attributes-nothing",
             _declared_row_is_taken_and_attributes_nothing),
        Case("required-source-is-placed-once-and-refused-when-absent",
             _required_source_is_placed_once_and_refused_when_absent),
        Case("adapter-sits-in-both-declarations", _adapter_sits_in_both_declarations),
        Case("adapter-carries-no-deleted-member", _adapter_carries_no_deleted_member),
        Case("cause-table-is-the-models", _cause_table_is_the_models),
        Case("double-underscore-joins-one-name-space",
             _double_underscore_joins_one_name_space),
        Case("declared-modules-are-declarations", _declared_modules_are_declarations),
        Case("substitution-modules-read-both-sides",
             _substitution_modules_read_both_sides),
        Case("diff-names-an-authored-introduction",
             _diff_names_an_authored_introduction),
        Case("diff-still-fails-on-an-undeclared-addition",
             _diff_still_fails_on_an_undeclared_addition),
        Case("diff-keeps-the-parameters-removals-apart",
             _diff_keeps_the_parameters_removals_apart),
        Case("diff-reports-an-authored-module-that-never-elaborated",
             _diff_reports_an_authored_module_that_never_elaborated),
        Case("drop-in-replacement-moves-nothing", _drop_in_replacement_moves_nothing),
    ]
