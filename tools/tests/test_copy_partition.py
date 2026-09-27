# SPDX-License-Identifier: Apache-2.0
"""Copy confinement harness shape; executed source-bound evidence is separate."""

from tests.harness import TOOLS, Case, ensure
from vos import asm, copy_partition


def bounded_fragments() -> None:
    layout = copy_partition.layout()
    ensure(layout["stack_offset"] + layout["stack_bytes"] == layout["owned_bytes"],
           "copy stack escapes its exclusively owned span")
    ensure(layout["stack_offset"] % layout["stack_bytes"] == 0,
           "copy stack has inexact power-of-two bounds")
    stubs = "\n".join(f"{name}:\n li x10, 1\n ret" for name in (
        "vos_copy_target_layout", "vos_copy_target_ring_bytes", "vos_copy_init_generation_slots",
        "vos_copy_submit_snapshot", "vos_copy_take_snapshot"))
    for defect in ("none", "tail-not-cleared", "saved-not-cleared", "resident-not-cleared",
                   "asr-entry", "stale-generation"):
        emitted = copy_partition.source(TOOLS.parent, ".text\n" + stubs, defect)
        assembler = asm.Assembler(emitted, defect, data_base=0x80200000)
        assembler.assemble()
        symbols = assembler.symbols
        p = copy_partition.PREFIX
        ensure(symbols[p + "_code"] % layout["code_bytes"] == 0,
               "compartment code bounds are not exact")
        ensure(symbols[p + "_code_end"] - symbols[p + "_code"] <= layout["code_bytes"],
               "compartment code exceeds its grant")
        ensure(symbols[p + "_owned"] % layout["owned_bytes"] == 0,
               "owned allocation bounds are not exact")
        ensure(not any(copy_partition.observations([], symbols, 1).values()),
               "empty trace supplied copy confinement evidence")
    for prefix, base in (("not a label", 20), ("valid", 5), ("valid", 31)):
        try:
            copy_partition.clear_span(prefix, base)
        except ValueError:
            continue
        raise AssertionError("invalid clear fragment admitted")


def cases() -> list[Case]:
    return [Case("copy partition bounds and missing-evidence refusal", bounded_fragments)]
