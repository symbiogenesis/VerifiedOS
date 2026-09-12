# SPDX-License-Identifier: Apache-2.0
"""Independent value, byte conservation, malformed lifetime and cost checks."""

import copy
from dataclasses import replace

from tests.harness import Case, ensure
from vos import static_memory as sm
from vos import static_memory_transform as t


def bounded_equivalence_and_receipt_are_replayable() -> None:
    first, second = t.transformation_report("test"), t.transformation_report("test")
    ensure(first == second, "receipt depends on hidden randomness or time")
    ensure(not first["errors"], "bounded service variants disagree")
    ensure(first["equivalence"]["checked_executions"] > 1000,
           "bounded and generated comparisons did not run")
    ensure(not first["service_contract"]["product_admission_evidence"], "target claim entered receipt")
    ensure(all(value is None for value in first["unknown"].values()), "unknown target cost invented")


def every_byte_has_exactly_one_charge() -> None:
    for variant in t.VARIANTS:
        plan = t.layout(t.emit_program(variant, 13, 5))
        case = sm.parse_case(plan["case"])
        ensure(not sm.check_placement(case, sm.standing_placement(case)), "invalid plan")
        for snapshot in plan["snapshots"]:
            tick = snapshot["tick"]
            charged = 0
            for address in range(plan["reserved_span"]):
                occupants = [obj for obj in case.objects if obj.start <= tick < obj.reuse
                             and obj.base <= address < obj.base + obj.size]
                ensure(len(occupants) <= 1, "a byte belongs to simultaneous objects")
                charged += bool(occupants)
            ensure(sum(snapshot["charges"].values()) == plan["reserved_span"],
                   "ledger double charges or hides physical backing")
            ensure(charged == plan["reserved_span"] - snapshot["charges"]["idle"],
                   "ledger occupancy disagrees with byte enumeration")
        for resource in plan["resources"]:
            ensure(resource["size"] == resource["payload"] + resource["padding"]
                   + resource["descriptor"], "descriptor or tail padding omitted")
        ensure(plan["charged_peak"] == max(plan["reserved_span"] - s["charges"]["idle"]
                                           for s in plan["snapshots"]), "load bound mismatch")


def counters_and_addresses_do_not_depend_on_frame_values() -> None:
    for variant in t.VARIANTS:
        program = t.emit_program(variant, 13, 5)
        first = t.execute(program, bytes(13))
        second = t.execute(program, bytes([255] * 13))
        ensure(first["counts"] == second["counts"], "secret data changes modeled schedule")
        ensure(first["all_released_and_zero"] and second["all_released_and_zero"],
               "zeroization missed data, padding or descriptors")
        resources = t.layout(program)["resources"]
        expected = 2 * (t.WORKSPACE_BYTES + sum(row["size"] for row in resources))
        ensure(first["counts"]["zeroization_writes"] == expected,
               "entry or retirement erasure is uncharged")
        ensure(first["counts"]["descriptor_writes"] == len(resources) * t.DESCRIPTOR_BYTES,
               "descriptor binding writes omitted")


def independent_reference_detects_a_functional_mutant() -> None:
    original = t.emit_program("phased-cache", 3)
    mutant = replace(original, instructions=tuple(
        replace(ins, op="copy") if ins.op == "xor" else ins for ins in original.instructions))
    findings = t.equivalence_findings(mutant, [bytes([0, 1, 255])])
    ensure(any("output differs" in finding for finding in findings), "value mutant survived")


def inactive_alias_and_narrowing_mutants_are_rejected() -> None:
    original = t.emit_program("phased-cache", 3)
    code = list(original.instructions)
    first_map = next(index for index, ins in enumerate(code) if ins.op == "map")
    mutants = [replace(original, instructions=(
        *code[:first_map], t.Instruction("retire", "input"), *code[first_map:])),
        replace(original, instructions=tuple(
            replace(ins, index=3) if index == first_map else ins for index, ins in enumerate(code)))]
    for mutant in mutants:
        try:
            t.execute(mutant, bytes(3))
        except ValueError:
            pass
        else:
            raise AssertionError("inactive alias or out-of-bounds view accepted")


def independent_placement_checker_rejects_early_reuse() -> None:
    raw = copy.deepcopy(t.layout(t.emit_program("lexical-cache", 16))["case"])
    raw["objects"][1]["base"] = raw["objects"][0]["base"]
    case = sm.parse_case(raw)
    ensure(any("overlap" in finding for finding in
               sm.check_placement(case, sm.standing_placement(case))), "collision was accepted")


def negative_results_and_tradeoffs_remain_visible() -> None:
    rows = {variant: (t.layout(t.emit_program(variant, 64)),
                     t.execute(t.emit_program(variant, 64), bytes(64))["counts"])
            for variant in t.VARIANTS}
    ensure(rows["phased-cache"][0]["reserved_span"] < rows["lexical-cache"][0]["reserved_span"],
           "phase retention comparison disappeared")
    ensure(rows["chunked-cache"][0]["reserved_span"] > rows["phased-cache"][0]["reserved_span"],
           "chunk descriptors or sink staging were discounted")
    ensure(rows["early-input-release"][0]["reserved_span"] > rows["phased-cache"][0]["reserved_span"],
           "earlier release was declared universally better")
    ensure(rows["fused-rematerialized"][1]["arithmetic_operations"]
           > rows["in-place-phased"][1]["arithmetic_operations"], "recomputation work disappeared")
    ensure(rows["fused-rematerialized"][1]["memory_traffic_bytes"]
           < rows["in-place-phased"][1]["memory_traffic_bytes"], "traffic ablation disappeared")
    ensure(rows["chunked-cache"][1]["staging_copies"] == 64, "contiguous sink copies omitted")


def malformed_bounds_refuse_without_silent_specialization() -> None:
    for length in (0, 65, True):
        try:
            t.emit_program("phased-cache", length)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid bound accepted")
    program = t.emit_program("in-place-phased", 3)
    try:
        t.execute(program, bytes(4))
    except ValueError:
        pass
    else:
        raise AssertionError("oversize frame entered the service")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        bounded_equivalence_and_receipt_are_replayable,
        every_byte_has_exactly_one_charge,
        counters_and_addresses_do_not_depend_on_frame_values,
        independent_reference_detects_a_functional_mutant,
        inactive_alias_and_narrowing_mutants_are_rejected,
        independent_placement_checker_rejects_early_reuse,
        negative_results_and_tradeoffs_remain_visible,
        malformed_bounds_refuse_without_silent_specialization,
    )]
