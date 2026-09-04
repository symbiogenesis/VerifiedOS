# SPDX-License-Identifier: Apache-2.0
"""The elaboration seam: an authored source standing for an imported one, and the
diff that tells an authored replacement from a finding.

Two mechanisms, and both are held here because neither can be held by a run. The
elaboration reads two gitlinks, one of which no checkout of this repository has
initialized, so the file list is composed against a synthetic manifest and the diff
is decided over the two inventories as sets. That is the whole of what each decides:
composition is a text transform over a manifest, and the partition is set algebra over
two module-kind sets and two attribution maps.

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

from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import provenance
from vos.cli import rtl

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


def cases() -> list[Case]:
    return [
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
