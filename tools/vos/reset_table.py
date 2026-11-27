# SPDX-License-Identifier: Apache-2.0
"""Schema and semantic validator for composition reset/power sequence tables.

Validates JSON composition tables against `interfaces/reset-table.schema.json`
using `vos.schema.validate` and `vos.jsonutil.unique_object`, and checks the
semantic obligations modeled in `ResetTable.v`, `MemoryPlan.v`, and
`DischargeSequence.v` (R-09-006a, R-09-006b, R-15-190b, R-15-198, R-15-198a,
R-15-228h, R-15-228i, R-15-247d, R-15-247t).
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from vos.jsonutil import unique_object
from vos.schema import validate

SCHEMA_PATH = Path("interfaces/reset-table.schema.json")
SESSION_KINDS = frozenset({"framebuffers", "media_buffers", "interpreter_object_arenas"})
RETAINED_REENTRY_KINDS = frozenset({"unlock_wake", "standby_exit", "install_switch"})


class ResetTableError(ValueError):
    """Raised when a reset/power sequence table violates schema or proof obligations."""


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / SCHEMA_PATH


def _unique_ids(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in items:
        ident = cast(str, item["id"])
        if ident in by_id:
            raise ResetTableError(f"duplicate {label} id: {ident}")
        by_id[ident] = item
    return by_id


def _first_index[T](items: list[T], predicate: Callable[[T], bool]) -> int | None:
    for idx, item in enumerate(items):
        if predicate(item):
            return idx
    return None


def _precedes[T](items: list[T], first_pred: Callable[[T], bool],
                 second_pred: Callable[[T], bool]) -> bool:
    first_idx = _first_index(items, first_pred)
    second_idx = _first_index(items, second_pred)
    return first_idx is not None and second_idx is not None and first_idx < second_idx


def _step_matches(step: dict[str, Any], op: str, *,
                  domain_id: str | None = None,
                  island_id: str | None = None,
                  extent_id: str | None = None,
                  socket_id: str | None = None) -> bool:
    if step.get("op") != op:
        return False
    if domain_id is not None and step.get("domain_id") != domain_id:
        return False
    if island_id is not None and step.get("island_id") != island_id:
        return False
    if extent_id is not None and step.get("extent_id") != extent_id:
        return False
    if socket_id is not None and step.get("socket_id") != socket_id:
        return False
    return True


def _validate_references_and_steps(
    data: dict[str, Any],
    modes_by_id: dict[str, dict[str, Any]],
    islands_by_id: dict[str, dict[str, Any]],
    sockets_by_id: dict[str, dict[str, Any]],
    regions_by_id: dict[str, dict[str, Any]],
    domains_by_id: dict[str, dict[str, Any]],
    extents_by_id: dict[str, dict[str, Any]],
) -> None:
    for ahead in cast(list[str], data["ahead_islands"]):
        if ahead not in islands_by_id:
            raise ResetTableError(f"ahead_islands names unknown island: {ahead}")
    inf_island = cast(str | None, data["inference_island"])
    if inf_island is not None:
        if inf_island not in islands_by_id:
            raise ResetTableError(f"inference_island names unknown island: {inf_island}")
        if inf_island in cast(list[str], data["ahead_islands"]):
            raise ResetTableError(f"inference_island {inf_island} cannot appear in ahead_islands")

    for socket in cast(list[dict[str, Any]], data["optional_sockets"]):
        if socket["island_id"] not in islands_by_id:
            raise ResetTableError(f"socket {socket['id']} binds unknown island {socket['island_id']}")

    for dom_id, dom in domains_by_id.items():
        if dom["island_id"] not in islands_by_id:
            raise ResetTableError(f"domain {dom_id} binds unknown island {dom['island_id']}")
        for reg_id in cast(list[str], dom["region_ids"]):
            if reg_id not in regions_by_id:
                raise ResetTableError(f"domain {dom_id} references unknown region {reg_id}")

    for ext_id, ext in extents_by_id.items():
        if ext["domain_id"] not in domains_by_id:
            raise ResetTableError(f"off_image_extent {ext_id} references unknown domain {ext['domain_id']}")

    island_res = cast(dict[str, dict[str, bool]], data["island_resident"])
    if set(island_res.keys()) != set(modes_by_id.keys()):
        raise ResetTableError("island_resident mode keys must match declared modes exactly")
    for mode_id, island_map in island_res.items():
        if set(island_map.keys()) != set(islands_by_id.keys()):
            raise ResetTableError(f"island_resident[{mode_id}] island keys must match declared islands")

    power_vec = cast(dict[str, dict[str, str]], data["power_vector"])
    if set(power_vec.keys()) != set(modes_by_id.keys()):
        raise ResetTableError("power_vector mode keys must match declared modes exactly")
    for mode_id, dom_map in power_vec.items():
        if set(dom_map.keys()) != set(domains_by_id.keys()):
            raise ResetTableError(f"power_vector[{mode_id}] domain keys must match declared domains")

    for idx, step in enumerate(cast(list[dict[str, Any]], data["steps"])):
        op = cast(str, step["op"])
        if op in {"domain_ready", "domain_complete", "image_pass", "image_verdict"}:
            dom_id = step.get("domain_id")
            if not isinstance(dom_id, str) or dom_id not in domains_by_id:
                raise ResetTableError(f"steps[{idx}] ({op}) requires valid domain_id")
        elif op == "island_release":
            isl_id = step.get("island_id")
            if not isinstance(isl_id, str) or isl_id not in islands_by_id:
                raise ResetTableError(f"steps[{idx}] (island_release) requires valid island_id")
        elif op in {"loader_fill", "extent_verified"}:
            ext_id = step.get("extent_id")
            if not isinstance(ext_id, str) or ext_id not in extents_by_id:
                raise ResetTableError(f"steps[{idx}] ({op}) requires valid extent_id")

    for se in cast(list[dict[str, Any]], data["suffix_entries"]):
        for dom_id in cast(list[str], se["domains"]):
            if dom_id not in domains_by_id:
                raise ResetTableError(f"suffix {se['id']} references unknown domain {dom_id}")
        for soc_id in cast(list[str], se["sockets"]):
            if soc_id not in sockets_by_id:
                raise ResetTableError(f"suffix {se['id']} references unknown socket {soc_id}")
        for step in cast(list[dict[str, Any]], se["rider_steps"]):
            op = cast(str, step["op"])
            if op in {"tag_discharge_confirmed", "requester_addressable", "data_sanitization_confirmed",
                      "measured_execution", "image_pass", "image_verdict"}:
                dom_id = step.get("domain_id")
                if not isinstance(dom_id, str) or dom_id not in domains_by_id:
                    raise ResetTableError(f"suffix {se['id']} step {op} requires valid domain_id")
            if op in {"socket_quiesced", "epoch_invalidated", "socket_isolated", "socket_reset"}:
                soc_id = step.get("socket_id")
                if not isinstance(soc_id, str) or soc_id not in sockets_by_id:
                    raise ResetTableError(f"suffix {se['id']} step {op} requires valid socket_id")


def _intervals_overlap(lo_a: int, len_a: int, lo_b: int, len_b: int) -> bool:
    return len_a > 0 and len_b > 0 and lo_a < lo_b + len_b and lo_b < lo_a + len_a


def _validate_labels_and_power_vector(
    data: dict[str, Any],
    regions_by_id: dict[str, dict[str, Any]],
    domains_by_id: dict[str, dict[str, Any]],
) -> None:
    held_by_any: set[str] = set()
    for dom_id, dom in domains_by_id.items():
        arena = cast(dict[str, Any], dom["arena"])
        arena_lo = cast(int, arena["lo"])
        arena_len = cast(int, arena["len"])
        arena_label = cast(str, arena["arena_label"])
        declared_label = cast(str, dom["retention_label"])
        if arena_label != declared_label:
            raise ResetTableError(
                f"domain {dom_id} has mismatched arena label {arena_label!r} vs {declared_label!r}")

        held_regions: list[dict[str, Any]] = []
        declared_rids = cast(list[str], dom["region_ids"])
        for reg_id in declared_rids:
            reg = regions_by_id[reg_id]
            reg_base = cast(int, reg["base"])
            reg_len = cast(int, reg["length"])
            if not _intervals_overlap(arena_lo, arena_len, reg_base, reg_len):
                raise ResetTableError(
                    f"domain {dom_id} arena [{arena_lo}, {arena_lo + arena_len}) does not meet region {reg_id}")
            if reg["arena_label"] != arena_label:
                raise ResetTableError(
                    f"region {reg_id} arena_label {reg['arena_label']!r} mismatches domain {dom_id} arena_label {arena_label!r}")
            held_regions.append(reg)
            held_by_any.add(reg_id)

        for reg_id, reg in regions_by_id.items():
            if _intervals_overlap(arena_lo, arena_len, cast(int, reg["base"]), cast(int, reg["length"])):
                if reg_id not in declared_rids:
                    raise ResetTableError(
                        f"domain {dom_id} arena overlaps undeclared region {reg_id}")

        has_second_class = any(reg["class"] == "second_class" for reg in held_regions)
        if dom["class"] == "second_class" or has_second_class:
            if not held_regions:
                raise ResetTableError(f"second-class domain {dom_id} holds no regions")
            if declared_label == "first_class":
                raise ResetTableError(f"second-class domain {dom_id} cannot declare first_class label")
            tainted = any(
                reg["kind"] in SESSION_KINDS or not reg["from_image"] or reg["cap_store_granted"]
                for reg in held_regions
            )
            derived = "session_derived" if tainted else "image_derived"
            if declared_label != derived:
                raise ResetTableError(
                    f"R-15-247t label mismatch on domain {dom_id}: declared {declared_label!r}, derived {derived!r}")
            if not dom["phases"]:
                raise ResetTableError(f"second-class domain {dom_id} must declare at least one discharge phase")
        else:
            if declared_label != "first_class":
                raise ResetTableError(f"first-class domain {dom_id} must declare first_class label")

    for reg_id, reg in regions_by_id.items():
        if reg["class"] == "second_class" and reg_id not in held_by_any:
            raise ResetTableError(f"R-15-247t holdings coverage failure: second-class region {reg_id} held by no domain")

    island_res = cast(dict[str, dict[str, bool]], data["island_resident"])
    power_vec = cast(dict[str, dict[str, str]], data["power_vector"])
    for mode_id, dom_map in power_vec.items():
        for dom_id, pstate in dom_map.items():
            dom = domains_by_id[dom_id]
            resident = island_res[mode_id][cast(str, dom["island_id"])]
            if dom["retention_label"] == "session_derived":
                if pstate == "RETAINED":
                    raise ResetTableError(
                        f"R-15-247t violation: session-derived domain {dom_id} cannot be RETAINED in mode {mode_id}")
                expected = "ON" if resident else "OFF"
                if pstate != expected:
                    raise ResetTableError(
                        f"R-15-247t violation: session-derived domain {dom_id} in mode {mode_id} must be {expected}, got {pstate}")
            elif dom["retention_label"] == "image_derived":
                if resident and pstate != "ON":
                    raise ResetTableError(
                        f"image-derived domain {dom_id} must be ON when island is resident in mode {mode_id}")


def _validate_cold_walk_and_staging(
    data: dict[str, Any],
    domains_by_id: dict[str, dict[str, Any]],
) -> None:
    steps = cast(list[dict[str, Any]], data["steps"])
    entries = [0, *cast(list[int], data["entry_points"])]
    for entry in entries:
        if entry >= len(steps):
            raise ResetTableError(f"entry point {entry} out of range for {len(steps)} steps")
        suffix = steps[entry:]
        for step in suffix:
            if step["op"] != "island_release":
                continue
            isl_id = cast(str, step["island_id"])
            for dom_id, dom in domains_by_id.items():
                if dom["island_id"] != isl_id:
                    continue
                if not _precedes(suffix,
                                 lambda s, d=dom_id: _step_matches(s, "domain_ready", domain_id=d),
                                 lambda s, i=isl_id: _step_matches(s, "island_release", island_id=i)):
                    raise ResetTableError(
                        f"R-15-198a early island release: island {isl_id} released at entry {entry} before domain_ready({dom_id})")
                if not _precedes(suffix,
                                 lambda s, d=dom_id: _step_matches(s, "domain_complete", domain_id=d),
                                 lambda s, i=isl_id: _step_matches(s, "island_release", island_id=i)):
                    raise ResetTableError(
                        f"R-15-198a early island release: island {isl_id} released at entry {entry} before domain_complete({dom_id})")

    bound_islands = {cast(str, dom["island_id"]) for dom in domains_by_id.values()}
    for isl_id in sorted(bound_islands):
        if _first_index(steps, lambda s, i=isl_id: _step_matches(s, "island_release", island_id=i)) is None:
            raise ResetTableError(f"R-15-198a coverage failure: bound island {isl_id} is never released")

    ahead = cast(list[str], data["ahead_islands"])
    inf_island = cast(str | None, data["inference_island"])
    if inf_island is not None:
        for ahead_id in ahead:
            if not _precedes(steps,
                             lambda s, a=ahead_id: _step_matches(s, "island_release", island_id=a),
                             lambda s, n=inf_island: _step_matches(s, "island_release", island_id=n)):
                raise ResetTableError(
                    f"R-15-198a staging violation: ahead island {ahead_id} release must precede inference island {inf_island} release")
            for dom_id, dom in domains_by_id.items():
                if dom["island_id"] == inf_island and dom["retention_label"] == "image_derived":
                    if not _precedes(steps,
                                     lambda s, a=ahead_id: _step_matches(s, "island_release", island_id=a),
                                     lambda s, d=dom_id: _step_matches(s, "domain_complete", domain_id=d)):
                        raise ResetTableError(
                            f"R-15-198a staging violation: ahead island {ahead_id} release must precede fill completion of {dom_id}")


def _validate_entropy_order(data: dict[str, Any]) -> None:
    steps = cast(list[dict[str, Any]], data["steps"])
    rot_idx = _first_index(steps, lambda s: s["op"] == "rot_rail_up")
    if rot_idx is None or rot_idx + 1 >= len(steps) or steps[rot_idx + 1]["op"] != "entropy_tests_begin":
        raise ResetTableError("R-15-198a entropy violation: entropy_tests_begin must immediately follow rot_rail_up")
    if not (_precedes(steps, lambda s: s["op"] == "entropy_tests_begin", lambda s: s["op"] == "clock_spine_lock")
            and _precedes(steps, lambda s: s["op"] == "clock_spine_lock", lambda s: s["op"] == "entropy_verdict_extended")):
        raise ResetTableError("R-15-198a entropy violation: tests must run under clock_spine_lock before verdict")
    if not (_precedes(steps, lambda s: s["op"] == "entropy_tests_begin", lambda s: s["op"] == "memory_controller_up")
            and _precedes(steps, lambda s: s["op"] == "memory_controller_up", lambda s: s["op"] == "entropy_verdict_extended")):
        raise ResetTableError("R-15-198a entropy violation: tests must run under memory_controller_up before verdict")
    if _first_index(steps, lambda s: s["op"] == "draws_entropy") is not None:
        if not _precedes(steps, lambda s: s["op"] == "entropy_verdict_extended", lambda s: s["op"] == "draws_entropy"):
            raise ResetTableError("R-09-006a violation: entropy_verdict_extended must precede draws_entropy")
    for step in steps:
        if step["op"] == "island_release":
            isl_id = cast(str, step["island_id"])
            if not _precedes(steps, lambda s: s["op"] == "entropy_verdict_extended",
                             lambda s, i=isl_id: _step_matches(s, "island_release", island_id=i)):
                raise ResetTableError(
                    f"R-09-006a violation: entropy_verdict_extended must precede island_release({isl_id})")


def _validate_off_image_extents(
    data: dict[str, Any],
    domains_by_id: dict[str, dict[str, Any]],
) -> None:
    steps = cast(list[dict[str, Any]], data["steps"])
    for ext in cast(list[dict[str, Any]], data["off_image_extents"]):
        ext_id = cast(str, ext["id"])
        dom_id = cast(str, ext["domain_id"])
        dom = domains_by_id[dom_id]
        if dom["retention_label"] != "image_derived":
            raise ResetTableError(
                f"R-15-190b violation: OFF-image extent {ext_id} must belong to an image_derived domain, got {dom['retention_label']}")
        if not ext["filled_by_loader"]:
            raise ResetTableError(f"R-15-190b violation: OFF-image extent {ext_id} is unfilled by RoT loader")
        if not ext["verified"]:
            raise ResetTableError(f"R-15-190b violation: OFF-image extent {ext_id} is unverified")

        isl_id = cast(str, dom["island_id"])
        if not _precedes(steps,
                         lambda s, d=dom_id: _step_matches(s, "domain_complete", domain_id=d),
                         lambda s, e=ext_id: _step_matches(s, "loader_fill", extent_id=e)):
            raise ResetTableError(
                f"R-15-190b ordering violation: loader_fill({ext_id}) must follow domain_complete({dom_id})")
        if not _precedes(steps,
                         lambda s, e=ext_id: _step_matches(s, "loader_fill", extent_id=e),
                         lambda s, e=ext_id: _step_matches(s, "extent_verified", extent_id=e)):
            raise ResetTableError(
                f"R-15-190b ordering violation: extent_verified({ext_id}) must follow loader_fill({ext_id})")
        if not _precedes(steps,
                         lambda s, e=ext_id: _step_matches(s, "extent_verified", extent_id=e),
                         lambda s, i=isl_id: _step_matches(s, "island_release", island_id=i)):
            raise ResetTableError(
                f"R-15-190b ordering violation: extent_verified({ext_id}) must precede island_release({isl_id})")


def _validate_suffix_entries(
    data: dict[str, Any],
    domains_by_id: dict[str, dict[str, Any]],
) -> None:
    steps = cast(list[dict[str, Any]], data["steps"])
    power_vec = cast(dict[str, dict[str, str]], data["power_vector"])
    retained_modes = {
        mode["id"] for mode in cast(list[dict[str, Any]], data["modes"])
        if mode["role"] in {"standby", "lock", "sleep"}
    }

    for se in cast(list[dict[str, Any]], data["suffix_entries"]):
        se_id = cast(str, se["id"])
        kind = cast(str, se["kind"])
        entry_index = cast(int | None, se["entry_index"])
        if entry_index is not None and entry_index >= len(steps):
            raise ResetTableError(f"suffix {se_id} entry_index {entry_index} out of range")

        rsteps = cast(list[dict[str, Any]], se["rider_steps"])
        for dep_before, dep_after in cast(list[list[int]], se["dependencies"]):
            if dep_before >= len(rsteps) or dep_after >= len(rsteps) or dep_before >= dep_after:
                raise ResetTableError(
                    f"R-15-198 dependency violation in suffix {se_id}: invalid pair [{dep_before}, {dep_after}]")

        for dom_id in cast(list[str], se["domains"]):
            if not _precedes(rsteps,
                             lambda s: s["op"] == "requesters_held",
                             lambda s, d=dom_id: _step_matches(s, "tag_discharge_confirmed", domain_id=d)):
                raise ResetTableError(
                    f"R-15-247d rider violation in suffix {se_id}: requesters_held must precede tag_discharge_confirmed({dom_id})")
            if not _precedes(rsteps,
                             lambda s, d=dom_id: _step_matches(s, "tag_discharge_confirmed", domain_id=d),
                             lambda s, d=dom_id: _step_matches(s, "requester_addressable", domain_id=d)):
                raise ResetTableError(
                    f"R-15-247d rider violation in suffix {se_id}: tag_discharge_confirmed({dom_id}) must precede requester_addressable({dom_id})")
            if not _precedes(rsteps,
                             lambda s, d=dom_id: _step_matches(s, "requester_addressable", domain_id=d),
                             lambda s, d=dom_id: _step_matches(s, "data_sanitization_confirmed", domain_id=d)):
                raise ResetTableError(
                    f"R-15-247d rider violation in suffix {se_id}: requester_addressable({dom_id}) must precede data_sanitization_confirmed({dom_id})")
            if not _precedes(rsteps,
                             lambda s, d=dom_id: _step_matches(s, "data_sanitization_confirmed", domain_id=d),
                             lambda s, d=dom_id: _step_matches(s, "measured_execution", domain_id=d)):
                raise ResetTableError(
                    f"R-15-247d rider violation in suffix {se_id}: data_sanitization_confirmed({dom_id}) must precede measured_execution({dom_id})")

            dom = domains_by_id[dom_id]
            is_retained_in_reentry = kind in RETAINED_REENTRY_KINDS and any(
                power_vec[m][dom_id] == "RETAINED" for m in retained_modes
            )
            if is_retained_in_reentry and dom["retention_label"] == "image_derived":
                if not _precedes(rsteps,
                                 lambda s, d=dom_id: _step_matches(s, "image_pass", domain_id=d),
                                 lambda s, d=dom_id: _step_matches(s, "image_verdict", domain_id=d)):
                    raise ResetTableError(
                        f"R-15-190b violation in suffix {se_id}: retained domain {dom_id} requires image_pass before image_verdict")
                if not _precedes(rsteps,
                                 lambda s, d=dom_id: _step_matches(s, "image_verdict", domain_id=d),
                                 lambda s, d=dom_id: _step_matches(s, "requester_addressable", domain_id=d)):
                    raise ResetTableError(
                        f"R-15-190b violation in suffix {se_id}: image_verdict({dom_id}) must precede requester_addressable({dom_id})")

        for soc_id in cast(list[str], se["sockets"]):
            if kind == "socket_power":
                if not _precedes(rsteps,
                                 lambda s, sid=soc_id: _step_matches(s, "socket_isolated", socket_id=sid),
                                 lambda s, sid=soc_id: _step_matches(s, "socket_reset", socket_id=sid)):
                    raise ResetTableError(
                        f"R-15-228i violation in suffix {se_id}: socket_isolated({soc_id}) must precede socket_reset({soc_id})")
            elif kind == "socket_isolation":
                if not _precedes(rsteps,
                                 lambda s, sid=soc_id: _step_matches(s, "epoch_invalidated", socket_id=sid),
                                 lambda s, sid=soc_id: _step_matches(s, "socket_isolated", socket_id=sid)):
                    raise ResetTableError(
                        f"R-15-228h violation in suffix {se_id}: epoch_invalidated({soc_id}) must precede socket_isolated({soc_id})")
                if _precedes(rsteps,
                             lambda s, sid=soc_id: _step_matches(s, "socket_isolated", socket_id=sid),
                             lambda s, sid=soc_id: _step_matches(s, "socket_reset", socket_id=sid)):
                    raise ResetTableError(
                        f"R-15-228i violation in suffix {se_id}: socket_isolation suffix cannot autonomously reset socket {soc_id}")


def _validate_latency_table(
    data: dict[str, Any],
    islands_by_id: dict[str, dict[str, Any]],
    domains_by_id: dict[str, dict[str, Any]],
) -> None:
    lat = cast(dict[str, Any], data["latency_table"])
    dom_terms = cast(dict[str, dict[str, Any]], lat["domain_terms"])
    if set(dom_terms.keys()) != set(domains_by_id.keys()):
        raise ResetTableError("R-09-006b violation: latency_table.domain_terms must cover every declared domain")

    for dom_id, terms in dom_terms.items():
        if cast(int, terms["rail_discharge_dwell_cycles"]) <= 0:
            raise ResetTableError(f"R-09-006b omission: domain {dom_id} missing positive rail_discharge_dwell_cycles")
        if terms["retained"]:
            if cast(int, terms["reverify_latency_cycles"]) <= 0:
                raise ResetTableError(f"R-09-006b omission: retained domain {dom_id} missing positive reverify_latency_cycles")
        else:
            if cast(int, terms["refill_latency_cycles"]) <= 0:
                raise ResetTableError(f"R-09-006b omission: OFF domain {dom_id} missing positive refill_latency_cycles")

    rps = cast(list[dict[str, Any]], lat["release_points"])
    covered_domains: set[str] = set()
    roles_seen: set[str] = set()
    for rp in rps:
        rp_id = cast(str, rp["id"])
        if rp["island_id"] not in islands_by_id:
            raise ResetTableError(f"release_point {rp_id} names unknown island {rp['island_id']}")
        if cast(int, rp["sig_verify_cycles"]) <= 0:
            raise ResetTableError(f"R-09-006b omission: release_point {rp_id} missing positive sig_verify_cycles")
        if rp["role"] == "cold_boot_to_interactive" and cast(int, rp["entropy_budget_cycles"]) <= 0:
            raise ResetTableError(f"R-09-006b omission: cold release_point {rp_id} missing positive entropy_budget_cycles")

        dom_sum = 0
        for dom_id in cast(list[str], rp["domains"]):
            if dom_id not in domains_by_id:
                raise ResetTableError(f"release_point {rp_id} names unknown domain {dom_id}")
            covered_domains.add(dom_id)
            terms = dom_terms[dom_id]
            dom_sum += cast(int, terms["rail_discharge_dwell_cycles"])
            dom_sum += cast(int, terms["reverify_latency_cycles"] if terms["retained"] else terms["refill_latency_cycles"])

        computed_total = (
            dom_sum
            + cast(int, rp["entropy_budget_cycles"])
            + cast(int, rp["sig_verify_cycles"])
            + cast(int, rp["restore_cycles"])
        )
        stated_total = cast(int, rp["stated_total_cycles"])
        ceiling = cast(int, rp["ceiling_cycles"])
        if stated_total != computed_total:
            raise ResetTableError(
                f"R-09-006b sum mismatch on release_point {rp_id}: stated {stated_total}, computed {computed_total}")
        if stated_total > ceiling:
            raise ResetTableError(
                f"R-09-006b ceiling overflow on release_point {rp_id}: {stated_total} > {ceiling}")
        roles_seen.add(cast(str, rp["role"]))

    missing_domains = set(domains_by_id.keys()) - covered_domains
    if missing_domains:
        raise ResetTableError(
            f"R-09-006b omission: domains omitted from latency release points: {sorted(missing_domains)}")
    if data["inference_island"] is not None and "inference_ready" not in roles_seen:
        raise ResetTableError(
            "R-09-006b omission: inference_island is composed without an inference_ready release point")


def validate_reset_table(value: object, *, schema_path: Path | None = None) -> dict[str, Any]:
    """Validate an already-decoded reset/power sequence table object."""
    resolved_schema = _default_schema_path() if schema_path is None else schema_path
    try:
        validate(resolved_schema, value)
    except ValueError as err:
        raise ResetTableError(str(err)) from err

    data = cast(dict[str, Any], value)
    modes_by_id = _unique_ids(cast(list[dict[str, Any]], data["modes"]), "mode")
    islands_by_id = _unique_ids(cast(list[dict[str, Any]], data["islands"]), "island")
    sockets_by_id = _unique_ids(cast(list[dict[str, Any]], data["optional_sockets"]), "socket")
    regions_by_id = _unique_ids(cast(list[dict[str, Any]], data["regions"]), "region")
    domains_by_id = _unique_ids(cast(list[dict[str, Any]], data["domains"]), "domain")
    extents_by_id = _unique_ids(cast(list[dict[str, Any]], data["off_image_extents"]), "off_image_extent")
    _unique_ids(cast(list[dict[str, Any]], data["suffix_entries"]), "suffix_entry")
    _unique_ids(cast(list[dict[str, Any]], data["latency_table"]["release_points"]), "release_point")

    _validate_references_and_steps(
        data, modes_by_id, islands_by_id, sockets_by_id,
        regions_by_id, domains_by_id, extents_by_id,
    )
    _validate_labels_and_power_vector(data, regions_by_id, domains_by_id)
    _validate_cold_walk_and_staging(data, domains_by_id)
    _validate_entropy_order(data)
    _validate_off_image_extents(data, domains_by_id)
    _validate_suffix_entries(data, domains_by_id)
    _validate_latency_table(data, islands_by_id, domains_by_id)
    return data


def load_reset_table(path: Path, *, schema_path: Path | None = None) -> dict[str, Any]:
    """Read JSON with duplicate-key rejection and run full reset-table validation."""
    try:
        raw_text = path.read_text(encoding="utf-8")
        decoded: object = json.loads(raw_text, object_pairs_hook=unique_object)
    except (OSError, ValueError) as err:
        raise ResetTableError(f"{path}: cannot decode JSON: {err}") from err
    return validate_reset_table(decoded, schema_path=schema_path)
