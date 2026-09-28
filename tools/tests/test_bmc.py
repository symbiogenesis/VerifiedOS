# SPDX-License-Identifier: Apache-2.0
"""The bounded model-checking smoke's plan, held against the dialect it is scoped by.

Nothing here runs a formal tool, and nothing could: riscv-formal and SymbiYosys are
not pinned. What these cases decide is the plan's own consistency, which is the part
that can drift before the gate ever runs: the instruction scope is read out of the
generated dialect table, every constructor of the classified files is classified, a
constructor the model gains or loses is reported rather than silently dropped, and a
model owed in riscv-formal's place is owed for a form the scope covers.
"""

from dataclasses import replace

from tests.harness import Case, ensure
from vos import bmc, dialect


def _scope_is_the_integer_computational_forms() -> None:
    covered = set(bmc.scope())
    for name in ("add", "addi", "addiw", "addw", "lui", "slli", "sraiw", "mul", "mulw",
                 "div", "remuw", "andn", "sh1add.uw", "rori", "bexti", "clmul", "pack",
                 "brev8", "xperm8", "czero.eqz"):
        ensure(name in covered, f"`{name}` is an integer computational form and in scope")
    for name in ("lw", "sd", "beq", "auipcc", "cjal", "cjalr", "csrrw", "ecall", "mret",
                 "fence", "lc", "sc", "cmove", "amoadd.w"):
        ensure(name not in covered,
               f"`{name}` is a form riscv-formal's model cannot judge here and is excluded")
    ensure("clmulr" not in covered,
           "`clmulr` is `Zbc` alone, which the dialect does not decode (R-15-048a)")


def _classification_is_closed() -> None:
    wrong = bmc.findings()
    ensure(not wrong, f"every constructor of the classified files is classified, got {wrong}")


def _owed_models_are_for_forms_in_scope() -> None:
    covered, owed = set(bmc.scope()), set(bmc.MODELS_OWED)
    ensure(owed <= covered, f"a model is owed only for a form in scope, got "
                            f"{sorted(owed - covered)}")
    for name in ("div", "divw", "rem", "remw"):
        ensure(name in owed, f"riscv-formal's `{name}` divides unsigned outside its "
                             "alternative-operations mode, so a model is owed for it")
    for name in ("divu", "divuw", "remu", "remuw"):
        ensure(name not in owed, f"`{name}` is unsigned, as riscv-formal's model computes it")
    for name in ("czero.eqz", "czero.nez"):
        ensure(name in owed, f"riscv-formal carries no `{name}` model, so one is owed")
    lost = {name: row for name, row in dialect.TABLE.items() if row.ctor != "ZICOND_RTYPE"}
    ensure(any("czero.eqz" in f for f in bmc.findings(lost)),
           "a model owed for a form the scope no longer covers is reported")


def _a_new_constructor_is_a_finding() -> None:
    add = dialect.TABLE["add"]
    gained = {**dialect.TABLE, "frob": replace(add, ctor="FROB")}
    ensure(any("FROB" in f for f in bmc.findings(gained)),
           "a base constructor nobody classified is reported")
    lost = {name: row for name, row in dialect.TABLE.items() if row.ctor != "MULW"}
    ensure(any("MULW" in f for f in bmc.findings(lost)),
           "a scope constructor no row carries is reported as a rule selecting nothing")
    ensure("mulw" not in bmc.scope(lost), "and the scope follows the table")


def _depths_admit_a_cover() -> None:
    depths = {check.name: check.depth for check in bmc.CHECKS}
    ensure("cover" in depths and depths["cover"] >= depths["insn"],
           "the cover check reaches at least the instruction depth, which is what makes "
           "an instruction verdict non-vacuous")
    ensure(len(depths) == len(bmc.CHECKS), "each check kind is declared once")


def _only_liveness_assumes_fairness() -> None:
    assumes = {check.name: check.assumes for check in bmc.CHECKS}
    ensure("fairness" in assumes.get("liveness", ""),
           "liveness states the fairness assumption it needs, since an unconstrained "
           "memory that never answers keeps any instruction from retiring")
    others = sorted(name for name, what in assumes.items() if what and name != "liveness")
    ensure(not others,
           f"the safety checks hold under unconstrained responses and assume nothing, "
           f"got assumptions on {others}")


def cases() -> list[Case]:
    return [
        Case("scope-is-the-integer-computational-forms",
             _scope_is_the_integer_computational_forms),
        Case("classification-is-closed", _classification_is_closed),
        Case("owed-models-are-for-forms-in-scope", _owed_models_are_for_forms_in_scope),
        Case("a-new-constructor-is-a-finding", _a_new_constructor_is_a_finding),
        Case("depths-admit-a-cover", _depths_admit_a_cover),
        Case("only-liveness-assumes-fairness", _only_liveness_assumes_fairness),
    ]
