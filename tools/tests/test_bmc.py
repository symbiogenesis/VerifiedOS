# SPDX-License-Identifier: Apache-2.0
"""The bounded model-checking smoke's plan, held against the dialect it is scoped by.

Nothing here runs a formal tool, and nothing could: riscv-formal and SymbiYosys are
not pinned. What these cases decide is the plan's own consistency, which is the part
that can drift before the gate ever runs: the instruction scope is read out of the
generated dialect table, every base and M constructor is classified, and a
constructor the model gains or loses is reported rather than silently dropped.
"""

from dataclasses import replace

from tests.harness import Case, ensure
from vos import bmc, dialect


def _scope_is_the_integer_computational_forms() -> None:
    covered = set(bmc.scope())
    for name in ("add", "addi", "addiw", "addw", "lui", "slli", "sraiw", "mul", "mulw",
                 "div", "remuw"):
        ensure(name in covered, f"`{name}` is an integer computational form and in scope")
    for name in ("lw", "sd", "beq", "auipcc", "cjal", "cjalr", "csrrw", "ecall", "mret",
                 "fence", "lc", "sc", "cmove", "andn", "czero.eqz", "amoadd.w"):
        ensure(name not in covered,
               f"`{name}` is a form riscv-formal's model cannot judge here and is excluded")


def _classification_is_closed() -> None:
    wrong = bmc.findings()
    ensure(not wrong, f"every base and M constructor is classified, got {wrong}")


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


def cases() -> list[Case]:
    return [
        Case("scope-is-the-integer-computational-forms",
             _scope_is_the_integer_computational_forms),
        Case("classification-is-closed", _classification_is_closed),
        Case("a-new-constructor-is-a-finding", _a_new_constructor_is_a_finding),
        Case("depths-admit-a-cover", _depths_admit_a_cover),
    ]
