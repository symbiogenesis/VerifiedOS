# SPDX-License-Identifier: Apache-2.0
"""Schema and semantic validation tests for composition reset/power sequence tables."""

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from tests.harness import Case, sandbox_tree
from vos import reset_table

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = reset_table.SCHEMA_PATH


def _valid_table() -> dict[str, Any]:
    """Build a complete admitted composition table matching ResetTable.v/MemoryPlan.v/DischargeSequence.v."""
    return {
        "schema": 1,
        "table_id": "composed-laptop-v1",
        "modes": [
            {"id": "cold", "role": "cold"},
            {"id": "active", "role": "normal"},
            {"id": "standby", "role": "standby"},
            {"id": "locked", "role": "lock"},
        ],
        "islands": [
            {"id": "rot", "role": "rot"},
            {"id": "shell", "role": "shell"},
            {"id": "inference", "role": "inference"},
        ],
        "ahead_islands": ["shell"],
        "inference_island": "inference",
        "optional_sockets": [
            {
                "id": "mod_sock0",
                "island_id": "inference",
                "replacement_mode": "cold",
                "initial_state": "isolated",
            }
        ],
        "regions": [
            {
                "id": "reg_shell_code",
                "class": "first_class",
                "kind": "code",
                "base": 0,
                "length": 1024,
                "from_image": True,
                "cap_store_granted": False,
                "arena_label": "first_class",
            },
            {
                "id": "reg_arenas",
                "class": "second_class",
                "kind": "interpreter_object_arenas",
                "base": 2048,
                "length": 256,
                "from_image": False,
                "cap_store_granted": False,
                "arena_label": "session_derived",
            },
            {
                "id": "reg_weights",
                "class": "second_class",
                "kind": "model_weights",
                "base": 2304,
                "length": 512,
                "from_image": True,
                "cap_store_granted": False,
                "arena_label": "image_derived",
            },
            {
                "id": "reg_payload",
                "class": "second_class",
                "kind": "application_payload",
                "base": 2912,
                "length": 1024,
                "from_image": True,
                "cap_store_granted": False,
                "arena_label": "image_derived",
            },
        ],
        "domains": [
            {
                "id": "dom_shell",
                "island_id": "shell",
                "class": "first_class",
                "retention_label": "first_class",
                "arena": {"id": "arena_shell", "lo": 0, "len": 1024, "arena_label": "first_class"},
                "region_ids": ["reg_shell_code"],
                "phases": [0],
            },
            {
                "id": "dom_arenas",
                "island_id": "inference",
                "class": "second_class",
                "retention_label": "session_derived",
                "arena": {"id": "arena_sess", "lo": 2048, "len": 256, "arena_label": "session_derived"},
                "region_ids": ["reg_arenas"],
                "phases": [0, 1],
            },
            {
                "id": "dom_weights",
                "island_id": "inference",
                "class": "second_class",
                "retention_label": "image_derived",
                "arena": {"id": "arena_weights", "lo": 2304, "len": 512, "arena_label": "image_derived"},
                "region_ids": ["reg_weights"],
                "phases": [0, 1],
            },
            {
                "id": "dom_payload",
                "island_id": "inference",
                "class": "second_class",
                "retention_label": "image_derived",
                "arena": {"id": "arena_payload", "lo": 2912, "len": 1024, "arena_label": "image_derived"},
                "region_ids": ["reg_payload"],
                "phases": [0, 1],
            },
        ],
        "island_resident": {
            "cold": {"rot": True, "shell": False, "inference": False},
            "active": {"rot": True, "shell": True, "inference": True},
            "standby": {"rot": True, "shell": True, "inference": False},
            "locked": {"rot": True, "shell": True, "inference": False},
        },
        "power_vector": {
            "cold": {
                "dom_shell": "OFF",
                "dom_arenas": "OFF",
                "dom_weights": "OFF",
                "dom_payload": "OFF",
            },
            "active": {
                "dom_shell": "ON",
                "dom_arenas": "ON",
                "dom_weights": "ON",
                "dom_payload": "ON",
            },
            "standby": {
                "dom_shell": "ON",
                "dom_arenas": "OFF",
                "dom_weights": "RETAINED",
                "dom_payload": "RETAINED",
            },
            "locked": {
                "dom_shell": "ON",
                "dom_arenas": "OFF",
                "dom_weights": "RETAINED",
                "dom_payload": "OFF",
            },
        },
        "off_image_extents": [
            {
                "id": "ext_payload_exec",
                "domain_id": "dom_payload",
                "kind": "executable",
                "filled_by_loader": True,
                "verified": True,
                "digest_ref": "sha256:payload-exec-root",
            },
            {
                "id": "ext_payload_data",
                "domain_id": "dom_payload",
                "kind": "data",
                "filled_by_loader": True,
                "verified": True,
                "digest_ref": "sha256:payload-data-root",
            },
        ],
        "steps": [
            {"op": "rot_rail_up", "ready_signal": "ROT_RAIL_OK", "watchdog_bound_sym": "WD_ROT"},
            {"op": "entropy_tests_begin", "ready_signal": "TRNG_START_ACK", "watchdog_bound_sym": "WD_TRNG"},
            {"op": "clock_spine_lock", "ready_signal": "PLL_LOCKED", "watchdog_bound_sym": "WD_PLL"},
            {"op": "memory_controller_up", "ready_signal": "MC_READY", "watchdog_bound_sym": "WD_MC"},
            {"op": "domain_ready", "domain_id": "dom_shell", "ready_signal": "DOM0_RDY", "watchdog_bound_sym": "WD_DOM"},
            {"op": "domain_complete", "domain_id": "dom_shell", "ready_signal": "DOM0_DONE", "watchdog_bound_sym": "WD_DOM"},
            {"op": "entropy_verdict_extended", "ready_signal": "PCR_EXT_OK", "watchdog_bound_sym": "WD_TRNG"},
            {"op": "draws_entropy", "ready_signal": "DRBG_SEED_OK", "watchdog_bound_sym": "WD_TRNG"},
            {"op": "island_release", "island_id": "shell", "ready_signal": "ISL_SHELL_REL", "watchdog_bound_sym": "WD_REL"},
            {"op": "domain_ready", "domain_id": "dom_arenas", "ready_signal": "DOM1_RDY", "watchdog_bound_sym": "WD_DOM"},
            {"op": "domain_complete", "domain_id": "dom_arenas", "ready_signal": "DOM1_DONE", "watchdog_bound_sym": "WD_DOM"},
            {"op": "domain_ready", "domain_id": "dom_payload", "ready_signal": "DOM3_RDY", "watchdog_bound_sym": "WD_DOM"},
            {"op": "domain_complete", "domain_id": "dom_payload", "ready_signal": "DOM3_DONE", "watchdog_bound_sym": "WD_DOM"},
            {"op": "loader_fill", "extent_id": "ext_payload_exec", "ready_signal": "FILL_EXEC_OK", "watchdog_bound_sym": "WD_LOAD"},
            {"op": "extent_verified", "extent_id": "ext_payload_exec", "ready_signal": "VER_EXEC_OK", "watchdog_bound_sym": "WD_HASH"},
            {"op": "loader_fill", "extent_id": "ext_payload_data", "ready_signal": "FILL_DATA_OK", "watchdog_bound_sym": "WD_LOAD"},
            {"op": "extent_verified", "extent_id": "ext_payload_data", "ready_signal": "VER_DATA_OK", "watchdog_bound_sym": "WD_HASH"},
            {"op": "domain_ready", "domain_id": "dom_weights", "ready_signal": "DOM2_RDY", "watchdog_bound_sym": "WD_DOM"},
            {"op": "domain_complete", "domain_id": "dom_weights", "ready_signal": "DOM2_DONE", "watchdog_bound_sym": "WD_DOM"},
            {"op": "island_release", "island_id": "inference", "ready_signal": "ISL_INF_REL", "watchdog_bound_sym": "WD_REL"},
        ],
        "entry_points": [9],
        "suffix_entries": [
            {
                "id": "suf_mode_exit",
                "kind": "mode_exit",
                "entry_index": 9,
                "domains": ["dom_arenas"],
                "sockets": [],
                "rider_steps": [
                    {"op": "requesters_held"},
                    {"op": "tag_discharge_confirmed", "domain_id": "dom_arenas"},
                    {"op": "requester_addressable", "domain_id": "dom_arenas"},
                    {"op": "data_sanitization_confirmed", "domain_id": "dom_arenas"},
                    {"op": "measured_execution", "domain_id": "dom_arenas"},
                ],
                "dependencies": [[0, 1], [1, 2], [2, 3], [3, 4]],
            },
            {
                "id": "suf_unlock_wake_retained",
                "kind": "unlock_wake",
                "entry_index": 9,
                "domains": ["dom_weights"],
                "sockets": [],
                "rider_steps": [
                    {"op": "requesters_held"},
                    {"op": "image_pass", "domain_id": "dom_weights"},
                    {"op": "image_verdict", "domain_id": "dom_weights"},
                    {"op": "tag_discharge_confirmed", "domain_id": "dom_weights"},
                    {"op": "requester_addressable", "domain_id": "dom_weights"},
                    {"op": "data_sanitization_confirmed", "domain_id": "dom_weights"},
                    {"op": "measured_execution", "domain_id": "dom_weights"},
                ],
                "dependencies": [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6]],
            },
            {
                "id": "suf_socket_power",
                "kind": "socket_power",
                "entry_index": None,
                "domains": ["dom_weights"],
                "sockets": ["mod_sock0"],
                "rider_steps": [
                    {"op": "requesters_held"},
                    {"op": "socket_isolated", "socket_id": "mod_sock0"},
                    {"op": "socket_reset", "socket_id": "mod_sock0"},
                    {"op": "tag_discharge_confirmed", "domain_id": "dom_weights"},
                    {"op": "requester_addressable", "domain_id": "dom_weights"},
                    {"op": "data_sanitization_confirmed", "domain_id": "dom_weights"},
                    {"op": "measured_execution", "domain_id": "dom_weights"},
                ],
                "dependencies": [[1, 2], [2, 4]],
            },
            {
                "id": "suf_socket_isolation",
                "kind": "socket_isolation",
                "entry_index": None,
                "domains": [],
                "sockets": ["mod_sock0"],
                "rider_steps": [
                    {"op": "socket_quiesced", "socket_id": "mod_sock0"},
                    {"op": "epoch_invalidated", "socket_id": "mod_sock0"},
                    {"op": "socket_isolated", "socket_id": "mod_sock0"},
                ],
                "dependencies": [[0, 1], [1, 2]],
            },
        ],
        "latency_table": {
            "ceiling_status": "proposed",
            "domain_terms": {
                "dom_shell": {
                    "rail_discharge_dwell_sym": "T_DWELL_SHELL",
                    "rail_discharge_dwell_cycles": 50,
                    "reverify_latency_sym": "T_REV_SHELL",
                    "reverify_latency_cycles": 0,
                    "refill_latency_sym": "T_REFILL_SHELL",
                    "refill_latency_cycles": 200,
                    "retained": False,
                },
                "dom_arenas": {
                    "rail_discharge_dwell_sym": "T_DWELL_ARENAS",
                    "rail_discharge_dwell_cycles": 80,
                    "reverify_latency_sym": "T_REV_ARENAS",
                    "reverify_latency_cycles": 0,
                    "refill_latency_sym": "T_REFILL_ARENAS",
                    "refill_latency_cycles": 300,
                    "retained": False,
                },
                "dom_weights": {
                    "rail_discharge_dwell_sym": "T_DWELL_WEIGHTS",
                    "rail_discharge_dwell_cycles": 60,
                    "reverify_latency_sym": "T_REV_WEIGHTS",
                    "reverify_latency_cycles": 120,
                    "refill_latency_sym": "T_REFILL_WEIGHTS",
                    "refill_latency_cycles": 500,
                    "retained": True,
                },
                "dom_payload": {
                    "rail_discharge_dwell_sym": "T_DWELL_PAYLOAD",
                    "rail_discharge_dwell_cycles": 70,
                    "reverify_latency_sym": "T_REV_PAYLOAD",
                    "reverify_latency_cycles": 140,
                    "refill_latency_sym": "T_REFILL_PAYLOAD",
                    "refill_latency_cycles": 600,
                    "retained": False,
                },
            },
            "release_points": [
                {
                    "id": "rp_wake",
                    "role": "wake_to_interactive",
                    "island_id": "shell",
                    "domains": ["dom_shell"],
                    "entropy_budget_sym": "T_TRNG_WAKE",
                    "entropy_budget_cycles": 0,
                    "sig_verify_sym": "T_SIG_WAKE",
                    "sig_verify_cycles": 45,
                    "restore_sym": "T_RESTORE_WAKE",
                    "restore_cycles": 35,
                    "stated_total_cycles": 330,
                    "ceiling_cycles": 1000,
                    "ceiling_ref": "DP-6",
                },
                {
                    "id": "rp_cold_shell",
                    "role": "cold_boot_to_interactive",
                    "island_id": "shell",
                    "domains": ["dom_shell"],
                    "entropy_budget_sym": "T_TRNG_COLD",
                    "entropy_budget_cycles": 100,
                    "sig_verify_sym": "T_SIG_COLD",
                    "sig_verify_cycles": 45,
                    "restore_sym": "T_RESTORE_COLD",
                    "restore_cycles": 35,
                    "stated_total_cycles": 430,
                    "ceiling_cycles": 2000,
                    "ceiling_ref": "DP-7",
                },
                {
                    "id": "rp_inference",
                    "role": "inference_ready",
                    "island_id": "inference",
                    "domains": ["dom_shell", "dom_arenas", "dom_weights", "dom_payload"],
                    "entropy_budget_sym": "T_TRNG_INF",
                    "entropy_budget_cycles": 100,
                    "sig_verify_sym": "T_SIG_INF",
                    "sig_verify_cycles": 45,
                    "restore_sym": "T_RESTORE_INF",
                    "restore_cycles": 35,
                    "stated_total_cycles": 1660,
                    "ceiling_cycles": 3000,
                    "ceiling_ref": "inference_ceiling",
                },
            ],
        },
    }


def _step_idx(table: dict[str, Any], op: str, **fields: str) -> int:
    for idx, step in enumerate(table["steps"]):
        if step["op"] == op and all(step.get(k) == v for k, v in fields.items()):
            return idx
    raise AssertionError(f"missing step {op} {fields}")


def _swap_steps(table: dict[str, Any], i: int, j: int) -> dict[str, Any]:
    mutated = copy.deepcopy(table)
    mutated["steps"][i], mutated["steps"][j] = mutated["steps"][j], mutated["steps"][i]
    return mutated


class ResetTableTests(unittest.TestCase):
    def test_valid_composed_table_passes(self) -> None:
        table = _valid_table()
        self.assertEqual(reset_table.validate_reset_table(table, schema_path=ROOT / SCHEMA), table)

    def test_session_confirmation_ahead_of_staging_is_admitted(self) -> None:
        table = _valid_table()
        # Move dom_arenas (session_derived) ready+complete before shell island_release.
        rdy_idx = _step_idx(table, "domain_ready", domain_id="dom_arenas")
        cmp_idx = _step_idx(table, "domain_complete", domain_id="dom_arenas")
        rdy_step = table["steps"][rdy_idx]
        cmp_step = table["steps"][cmp_idx]
        # Remove from original location and place before shell island_release (at index 8),
        # dropping the entry point at 9 (reading cold path alone, like ResetTable.v session_first_table).
        del table["steps"][cmp_idx]
        del table["steps"][rdy_idx]
        rel_idx = _step_idx(table, "island_release", island_id="shell")
        table["steps"][rel_idx:rel_idx] = [rdy_step, cmp_step]
        table["entry_points"] = []
        table["suffix_entries"][0]["entry_index"] = None
        table["suffix_entries"][1]["entry_index"] = None
        reset_table.validate_reset_table(table, schema_path=ROOT / SCHEMA)

    def test_table_without_optional_inference_island_passes(self) -> None:
        table = _valid_table()
        table["inference_island"] = None
        table["optional_sockets"] = []
        table["suffix_entries"] = [se for se in table["suffix_entries"] if not se["sockets"]]
        table["latency_table"]["release_points"] = [
            rp for rp in table["latency_table"]["release_points"] if rp["role"] != "inference_ready"
        ]
        table["latency_table"]["release_points"][1]["domains"] = [
            "dom_shell", "dom_arenas", "dom_weights", "dom_payload"
        ]
        table["latency_table"]["release_points"][1]["stated_total_cycles"] = 1660
        reset_table.validate_reset_table(table, schema_path=ROOT / SCHEMA)

    def test_schema_violations_and_duplicate_json_key_rejected(self) -> None:
        valid = _valid_table()
        for bad in (
            None,
            [],
            {**valid, "extra": 1},
            {**valid, "schema": True},
            {**valid, "schema": 1.0},
            {**valid, "table_id": "InvalidUpper"},
            {**valid, "ahead_islands": []},
        ):
            with self.assertRaises(reset_table.ResetTableError):
                reset_table.validate_reset_table(bad, schema_path=ROOT / SCHEMA)

        for key in valid:
            missing = copy.deepcopy(valid)
            del missing[key]
            with self.assertRaises(reset_table.ResetTableError):
                reset_table.validate_reset_table(missing, schema_path=ROOT / SCHEMA)

        raw = json.dumps(valid)
        dup = raw.replace('"schema": 1', '"schema": 1, "schema": 1', 1)
        with sandbox_tree({"table.json": dup, str(SCHEMA): (ROOT / SCHEMA).read_text(encoding="utf-8")}) as tmp:
            with self.assertRaisesRegex(reset_table.ResetTableError, "duplicate JSON key"):
                reset_table.load_reset_table(tmp / "table.json", schema_path=tmp / SCHEMA)

    def test_rejects_session_derived_retained_and_residency_violations(self) -> None:
        retained_non_res = _valid_table()
        retained_non_res["power_vector"]["standby"]["dom_arenas"] = "RETAINED"
        with self.assertRaisesRegex(reset_table.ResetTableError, "RETAINED"):
            reset_table.validate_reset_table(retained_non_res, schema_path=ROOT / SCHEMA)

        retained_res = _valid_table()
        retained_res["power_vector"]["active"]["dom_arenas"] = "RETAINED"
        with self.assertRaisesRegex(reset_table.ResetTableError, "RETAINED"):
            reset_table.validate_reset_table(retained_res, schema_path=ROOT / SCHEMA)

        off_when_res = _valid_table()
        off_when_res["power_vector"]["active"]["dom_arenas"] = "OFF"
        with self.assertRaisesRegex(reset_table.ResetTableError, "must be ON"):
            reset_table.validate_reset_table(off_when_res, schema_path=ROOT / SCHEMA)

    def test_rejects_mismatched_arena_labels_and_unheld_regions(self) -> None:
        mismatch_arena = _valid_table()
        mismatch_arena["domains"][2]["arena"]["arena_label"] = "session_derived"
        with self.assertRaisesRegex(reset_table.ResetTableError, "mismatched arena label"):
            reset_table.validate_reset_table(mismatch_arena, schema_path=ROOT / SCHEMA)

        mismatch_reg = _valid_table()
        mismatch_reg["regions"][2]["arena_label"] = "session_derived"
        with self.assertRaisesRegex(reset_table.ResetTableError, "mismatches domain"):
            reset_table.validate_reset_table(mismatch_reg, schema_path=ROOT / SCHEMA)

        cap_store_weights = _valid_table()
        cap_store_weights["regions"][2]["cap_store_granted"] = True
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-247t label mismatch"):
            reset_table.validate_reset_table(cap_store_weights, schema_path=ROOT / SCHEMA)

        kv_cache_mislabelled = _valid_table()
        kv_cache_mislabelled["regions"][3]["from_image"] = False
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-247t label mismatch"):
            reset_table.validate_reset_table(kv_cache_mislabelled, schema_path=ROOT / SCHEMA)

        unheld_region = _valid_table()
        unheld_region["domains"][1]["arena"]["lo"] = 9999
        with self.assertRaisesRegex(reset_table.ResetTableError, "does not meet region"):
            reset_table.validate_reset_table(unheld_region, schema_path=ROOT / SCHEMA)

    def test_rejects_early_island_release_staging_and_unreleased_island(self) -> None:
        base = _valid_table()
        idx_comp = _step_idx(base, "domain_complete", domain_id="dom_weights")
        idx_rel = _step_idx(base, "island_release", island_id="inference")
        early_rel = _swap_steps(base, idx_comp, idx_rel)
        with self.assertRaisesRegex(reset_table.ResetTableError, "early island release"):
            reset_table.validate_reset_table(early_rel, schema_path=ROOT / SCHEMA)

        late_entry = _valid_table()
        late_entry["entry_points"] = [9, 13]
        with self.assertRaisesRegex(reset_table.ResetTableError, "early island release"):
            reset_table.validate_reset_table(late_entry, schema_path=ROOT / SCHEMA)

        unreleased = _valid_table()
        unreleased["steps"] = [
            s for s in unreleased["steps"]
            if not (s["op"] == "island_release" and s.get("island_id") == "inference")
        ]
        with self.assertRaisesRegex(reset_table.ResetTableError, "never released"):
            reset_table.validate_reset_table(unreleased, schema_path=ROOT / SCHEMA)

        inf_first = _valid_table()
        idx_shell = _step_idx(inf_first, "island_release", island_id="shell")
        idx_inf = _step_idx(inf_first, "island_release", island_id="inference")
        inf_first["steps"][idx_shell], inf_first["steps"][idx_inf] = (
            inf_first["steps"][idx_inf], inf_first["steps"][idx_shell]
        )
        with self.assertRaisesRegex(reset_table.ResetTableError, "early island release|staging violation"):
            reset_table.validate_reset_table(inf_first, schema_path=ROOT / SCHEMA)

    def test_rejects_missing_or_late_entropy_verdict(self) -> None:
        base = _valid_table()
        idx_verdict = _step_idx(base, "entropy_verdict_extended")
        idx_draw = _step_idx(base, "draws_entropy")
        early_draw = _swap_steps(base, idx_verdict, idx_draw)
        with self.assertRaisesRegex(reset_table.ResetTableError, "entropy_verdict_extended must precede draws_entropy"):
            reset_table.validate_reset_table(early_draw, schema_path=ROOT / SCHEMA)

        idx_begin = _step_idx(base, "entropy_tests_begin")
        idx_pll = _step_idx(base, "clock_spine_lock")
        late_tests = _swap_steps(base, idx_begin, idx_pll)
        with self.assertRaisesRegex(reset_table.ResetTableError, "immediately follow rot_rail_up"):
            reset_table.validate_reset_table(late_tests, schema_path=ROOT / SCHEMA)

        verdict_before_mc = _swap_steps(base, _step_idx(base, "memory_controller_up"), idx_verdict)
        with self.assertRaisesRegex(reset_table.ResetTableError, "memory_controller_up"):
            reset_table.validate_reset_table(verdict_before_mc, schema_path=ROOT / SCHEMA)

        rel_before_verdict = _swap_steps(base, idx_verdict, _step_idx(base, "island_release", island_id="shell"))
        with self.assertRaisesRegex(reset_table.ResetTableError, "entropy_verdict_extended must precede"):
            reset_table.validate_reset_table(rel_before_verdict, schema_path=ROOT / SCHEMA)

    def test_rejects_r15_247d_rider_misordering_and_malformed_suffixes(self) -> None:
        skip_discharge = _valid_table()
        del skip_discharge["suffix_entries"][0]["rider_steps"][1]
        skip_discharge["suffix_entries"][0]["dependencies"] = []
        with self.assertRaisesRegex(reset_table.ResetTableError, "tag_discharge_confirmed"):
            reset_table.validate_reset_table(skip_discharge, schema_path=ROOT / SCHEMA)

        reordered_san = _valid_table()
        rs = reordered_san["suffix_entries"][0]["rider_steps"]
        rs[2], rs[3] = rs[3], rs[2]
        reordered_san["suffix_entries"][0]["dependencies"] = []
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-247d rider violation"):
            reset_table.validate_reset_table(reordered_san, schema_path=ROOT / SCHEMA)

        early_exec = _valid_table()
        rs2 = early_exec["suffix_entries"][0]["rider_steps"]
        rs2[3], rs2[4] = rs2[4], rs2[3]
        early_exec["suffix_entries"][0]["dependencies"] = []
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-247d rider violation"):
            reset_table.validate_reset_table(early_exec, schema_path=ROOT / SCHEMA)

        bad_dep = _valid_table()
        bad_dep["suffix_entries"][0]["dependencies"] = [[2, 1]]
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-198 dependency violation"):
            reset_table.validate_reset_table(bad_dep, schema_path=ROOT / SCHEMA)

        no_image_pass = _valid_table()
        no_image_pass["suffix_entries"][1]["rider_steps"] = [
            s for s in no_image_pass["suffix_entries"][1]["rider_steps"] if s["op"] != "image_pass"
        ]
        no_image_pass["suffix_entries"][1]["dependencies"] = []
        with self.assertRaisesRegex(reset_table.ResetTableError, "image_pass before image_verdict"):
            reset_table.validate_reset_table(no_image_pass, schema_path=ROOT / SCHEMA)

        unisolated_sock = _valid_table()
        unisolated_sock["suffix_entries"][2]["rider_steps"] = [
            s for s in unisolated_sock["suffix_entries"][2]["rider_steps"] if s["op"] != "socket_isolated"
        ]
        unisolated_sock["suffix_entries"][2]["dependencies"] = []
        with self.assertRaisesRegex(reset_table.ResetTableError, "socket_isolated"):
            reset_table.validate_reset_table(unisolated_sock, schema_path=ROOT / SCHEMA)

        uninvalidated_iso = _valid_table()
        uninvalidated_iso["suffix_entries"][3]["rider_steps"] = [
            s for s in uninvalidated_iso["suffix_entries"][3]["rider_steps"] if s["op"] != "epoch_invalidated"
        ]
        uninvalidated_iso["suffix_entries"][3]["dependencies"] = []
        with self.assertRaisesRegex(reset_table.ResetTableError, "epoch_invalidated"):
            reset_table.validate_reset_table(uninvalidated_iso, schema_path=ROOT / SCHEMA)

        auto_recovery = _valid_table()
        auto_recovery["suffix_entries"][3]["rider_steps"].append({"op": "socket_reset", "socket_id": "mod_sock0"})
        with self.assertRaisesRegex(reset_table.ResetTableError, "autonomously reset"):
            reset_table.validate_reset_table(auto_recovery, schema_path=ROOT / SCHEMA)

    def test_rejects_unfilled_or_unverified_off_image_extents(self) -> None:
        unfilled_flag = _valid_table()
        unfilled_flag["off_image_extents"][0]["filled_by_loader"] = False
        with self.assertRaisesRegex(reset_table.ResetTableError, "unfilled"):
            reset_table.validate_reset_table(unfilled_flag, schema_path=ROOT / SCHEMA)

        unverified_flag = _valid_table()
        unverified_flag["off_image_extents"][1]["verified"] = False
        with self.assertRaisesRegex(reset_table.ResetTableError, "unverified"):
            reset_table.validate_reset_table(unverified_flag, schema_path=ROOT / SCHEMA)

        pre_san = _swap_steps(
            _valid_table(),
            _step_idx(_valid_table(), "domain_complete", domain_id="dom_payload"),
            _step_idx(_valid_table(), "loader_fill", extent_id="ext_payload_exec"),
        )
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-190b ordering violation"):
            reset_table.validate_reset_table(pre_san, schema_path=ROOT / SCHEMA)

        unverified_release = _valid_table()
        ver_idx = _step_idx(unverified_release, "extent_verified", extent_id="ext_payload_data")
        ver_step = unverified_release["steps"].pop(ver_idx)
        unverified_release["steps"].append(ver_step)
        with self.assertRaisesRegex(reset_table.ResetTableError, "R-15-190b ordering violation"):
            reset_table.validate_reset_table(unverified_release, schema_path=ROOT / SCHEMA)

    def test_rejects_latency_omissions_mismatches_and_overflows(self) -> None:
        missing_term = _valid_table()
        del missing_term["latency_table"]["domain_terms"]["dom_payload"]
        with self.assertRaisesRegex(reset_table.ResetTableError, "domain_terms must cover every declared domain"):
            reset_table.validate_reset_table(missing_term, schema_path=ROOT / SCHEMA)

        zero_dwell = _valid_table()
        zero_dwell["latency_table"]["domain_terms"]["dom_shell"]["rail_discharge_dwell_cycles"] = 0
        with self.assertRaisesRegex(reset_table.ResetTableError, "rail_discharge_dwell_cycles"):
            reset_table.validate_reset_table(zero_dwell, schema_path=ROOT / SCHEMA)

        zero_reverify = _valid_table()
        zero_reverify["latency_table"]["domain_terms"]["dom_weights"]["reverify_latency_cycles"] = 0
        with self.assertRaisesRegex(reset_table.ResetTableError, "reverify_latency_cycles"):
            reset_table.validate_reset_table(zero_reverify, schema_path=ROOT / SCHEMA)

        sum_mismatch = _valid_table()
        sum_mismatch["latency_table"]["release_points"][0]["stated_total_cycles"] = 100
        with self.assertRaisesRegex(reset_table.ResetTableError, "sum mismatch"):
            reset_table.validate_reset_table(sum_mismatch, schema_path=ROOT / SCHEMA)

        overflow = _valid_table()
        overflow["latency_table"]["release_points"][0]["ceiling_cycles"] = 200
        with self.assertRaisesRegex(reset_table.ResetTableError, "ceiling overflow"):
            reset_table.validate_reset_table(overflow, schema_path=ROOT / SCHEMA)

        omitted_inf = _valid_table()
        omitted_inf["latency_table"]["release_points"] = omitted_inf["latency_table"]["release_points"][:2]
        with self.assertRaisesRegex(reset_table.ResetTableError, "domains omitted"):
            reset_table.validate_reset_table(omitted_inf, schema_path=ROOT / SCHEMA)

        missing_inf_role = _valid_table()
        missing_inf_role["latency_table"]["release_points"] = missing_inf_role["latency_table"]["release_points"][:2]
        missing_inf_role["latency_table"]["release_points"][1]["domains"] = [
            "dom_shell", "dom_arenas", "dom_weights", "dom_payload"
        ]
        missing_inf_role["latency_table"]["release_points"][1]["stated_total_cycles"] = 1660
        with self.assertRaisesRegex(reset_table.ResetTableError, "inference_ready"):
            reset_table.validate_reset_table(missing_inf_role, schema_path=ROOT / SCHEMA)


def cases() -> list[Case]:
    checks = ResetTableTests()
    return [
        Case("valid-composed-table", checks.test_valid_composed_table_passes),
        Case("session-confirmation-ahead-of-staging", checks.test_session_confirmation_ahead_of_staging_is_admitted),
        Case("without-optional-inference-island", checks.test_table_without_optional_inference_island_passes),
        Case("schema-and-duplicate-json-key", checks.test_schema_violations_and_duplicate_json_key_rejected),
        Case("session-derived-retained-refused", checks.test_rejects_session_derived_retained_and_residency_violations),
        Case("mismatched-arena-labels-refused", checks.test_rejects_mismatched_arena_labels_and_unheld_regions),
        Case("early-island-release-and-staging-refused", checks.test_rejects_early_island_release_staging_and_unreleased_island),
        Case("missing-entropy-verdict-refused", checks.test_rejects_missing_or_late_entropy_verdict),
        Case("rider-misordering-and-suffix-refused", checks.test_rejects_r15_247d_rider_misordering_and_malformed_suffixes),
        Case("unfilled-off-image-extent-refused", checks.test_rejects_unfilled_or_unverified_off_image_extents),
        Case("latency-omissions-and-overflow-refused", checks.test_rejects_latency_omissions_mismatches_and_overflows),
    ]
