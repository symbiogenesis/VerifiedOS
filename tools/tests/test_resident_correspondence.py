# SPDX-License-Identifier: Apache-2.0
"""Cross-OS C-to-Gallina correspondence campaign for `proofs/ResidentReads.v`."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast

from tests.harness import Case, ensure
from vos import env, proof_staging, toolenv
from vos.jsonutil import unique_object

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "storage" / "host" / "resident_reads_correspondence.c"
RESIDENT_SOURCE = ROOT / "storage" / "src" / "resident_reads.c"
SCALAR_SOURCE = ROOT / "storage" / "src" / "resident_scalar.c"

STRICT_ROCQ_FLAGS = (
    "-w",
    "+default,-abstract-large-number",
    "-set",
    "Default Goal Selector=!",
    "-disallow-sprop",
)

JSONObject = dict[str, object]


def _nat_list(values: list[int]) -> str:
    text = "nil"
    for value in reversed(values):
        text = f"(cons {value} {text})"
    return text


def _identity_term(identity: JSONObject) -> str:
    digest = cast("list[int]", identity["root_digest"])
    return (
        "{| owner := "
        + str(identity["owner"])
        + "; domain := "
        + str(identity["domain"])
        + "; object_id := "
        + str(identity["object_id"])
        + "; version := "
        + str(identity["version"])
        + "; root_kind := "
        + str(identity["root_kind"])
        + "; generation := "
        + str(identity["generation"])
        + "; root_digest := "
        + _nat_list(digest)
        + " |}"
    )


def _resident_term(backing: JSONObject) -> str:
    identity = cast("JSONObject", backing["resident_identity"])
    raw = cast("list[int]", backing["resident_bytes"])
    acc = "true" if bool(backing["accepting"]) else "false"
    return (
        "{| resident_identity := "
        + _identity_term(identity)
        + "; resident_bytes := "
        + _nat_list(raw)
        + "; accepting := "
        + acc
        + " |}"
    )


def _handle_term(handle: JSONObject) -> str:
    identity = cast("JSONObject", handle["handle_identity"])
    return (
        "{| token := "
        + str(handle["token"])
        + "; boot_epoch := "
        + str(handle["boot_epoch"])
        + "; holder := "
        + str(handle["holder"])
        + "; handle_identity := "
        + _identity_term(identity)
        + "; window_start := "
        + str(handle["window_start"])
        + "; window_length := "
        + str(handle["window_length"])
        + " |}"
    )


def _cell_term(cell: JSONObject) -> str:
    name = str(cell["name"])
    holder = int(cast("int", cell["holder"]))
    if name in ("CommonCounter", "CommonBacking"):
        return name
    if name == "CommonReservation":
        return f"(CommonReservation {max(0, holder)})"
    if name == "PrivateSequence":
        return f"(PrivateSequence {max(0, holder)})"
    if name == "PrivatePending":
        return f"(PrivatePending {max(0, holder)})"
    return f"(ResponsePublication {max(0, holder)})"


def _cell_list(cells: list[JSONObject]) -> str:
    text = "nil"
    for cell in reversed(cells):
        text = f"(cons {_cell_term(cell)} {text})"
    return text


def _verify_pairs(trace: JSONObject) -> list[tuple[list[int], list[int]]]:
    pairs: list[tuple[list[int], list[int]]] = []
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()

    def add_pair(payload: list[int], identity: JSONObject) -> None:
        digest = cast("list[int]", identity["root_digest"])
        key = (tuple(payload), tuple(digest))
        if key not in seen:
            seen.add(key)
            pairs.append((payload, digest))

    for camp in cast("list[JSONObject]", trace["single_slot"]):
        add_pair(cast("list[int]", camp["payload"]), cast("JSONObject", camp["identity"]))
    for camp in cast("list[JSONObject]", trace["two_slot"]):
        add_pair(cast("list[int]", camp["p1"]), cast("JSONObject", camp["id1"]))
        add_pair(cast("list[int]", camp["p2"]), cast("JSONObject", camp["id2"]))
        steps = cast("list[JSONObject]", camp["steps"])
        last_cur = cast("JSONObject", cast("JSONObject", steps[-1]["state"])["current_backing"])
        add_pair(
            cast("list[int]", last_cur["resident_bytes"]),
            cast("JSONObject", last_cur["resident_identity"]),
        )
    for camp in cast("list[JSONObject]", trace["scalar_retire"]):
        add_pair(cast("list[int]", camp["payload"]), cast("JSONObject", camp["identity"]))
    return pairs


def _single_slot_gallina(idx: int, camp: JSONObject) -> list[str]:
    prefix = f"ss_{idx}"
    gen0 = int(cast("int", camp["initial_generation"]))
    payload = cast("list[int]", camp["payload"])
    identity = cast("JSONObject", camp["identity"])
    steps = cast("list[JSONObject]", camp["steps"])
    by_op: dict[str, list[JSONObject]] = {}
    for st in steps:
        by_op.setdefault(str(st["op"]), []).append(st)

    admit0 = by_op["admit_h0"][0]
    admit1 = by_op["admit_h1"][0]
    reads = [st for st in steps if str(st["op"]) in ("read_h0", "read_h1")]
    comp5 = by_op["complete_h0_at5"][0]
    exp5 = by_op["begin_h1_expired_at5"][0]
    closed = by_op["close_h0"][0]
    readmitted = by_op["readmit_h0"][0]
    read_new = by_op["read_readmitted_h0"][0]
    crashed = by_op["crash"][0]

    ensure(len(reads) == 6, "expected 6 single-slot repeated reads")
    id_term = _identity_term(identity)
    res_term = _resident_term(
        {"resident_identity": identity, "resident_bytes": payload, "accepting": True}
    )
    lines: list[str] = [
        f"Definition {prefix}_id : Identity := {id_term}.",
        f"Definition {prefix}_res : Resident := {res_term}.",
        f"Definition {prefix}_init : State :=",
        f"  {{| common := {{| backing := Some {prefix}_res;",
        "      reservations := fun _ => None;",
        "      authority := fun _ => true;",
        "      next_token := 0; clock := 0; current_boot := 0;",
        f"      current_generation := {gen0}; common_counter := 0 |}};",
        "     sessions := fun _ => empty_session |}.",
        f"Definition {prefix}_adm0 := admit corr_bounds {prefix}_init 0 7 {prefix}_id 0 16.",
        f"Definition {prefix}_s1 := fst {prefix}_adm0.",
        f"Definition {prefix}_h0 := {_handle_term(cast('JSONObject', admit0['handle_out']))}.",
        f"Example {prefix}_c_admit0 : {prefix}_adm0 = ({prefix}_s1, Some {prefix}_h0).",
        "Proof. vm_compute; reflexivity. Qed.",
        f"Definition {prefix}_adm1 := admit corr_bounds {prefix}_s1 1 7 {prefix}_id 4 12.",
        f"Definition {prefix}_s2 := fst {prefix}_adm1.",
        f"Definition {prefix}_h1 := {_handle_term(cast('JSONObject', admit1['handle_out']))}.",
        f"Example {prefix}_c_admit1 : {prefix}_adm1 = ({prefix}_s2, Some {prefix}_h1).",
        "Proof. vm_compute; reflexivity. Qed.",
    ]

    prev_state = f"{prefix}_s2"
    for r_idx, step in enumerate(reads):
        cells = cast("list[JSONObject]", step["cells"])
        p_out = cast("list[int]", step["payload_out"])
        st_snap = cast("JSONObject", step["state"])
        sessions = cast("list[JSONObject]", st_snap["sessions"])
        holder = r_idx % 2
        h_var = f"{prefix}_h{holder}"
        len_val = 16 if holder == 0 else 12
        o_name = f"{prefix}_read_{r_idx}"
        lines.extend([
            f"Definition {o_name} := read_once corr_verify corr_bounds {prev_state} {h_var} 7 {prefix}_id 0 {len_val}.",
            f"Example {o_name}_payload : payload {o_name} = Some {_nat_list(p_out)} := eq_refl.",
            f"Example {o_name}_c_nocommon : forallb is_common {_cell_list(cells)} = false := eq_refl.",
            f"Example {o_name}_g_nocommon : no_common (journal {o_name}).",
            "Proof. apply read_no_common_writes. Qed.",
            f"Example {o_name}_seq0 : sequence (sessions (after {o_name}) 0) = {sessions[0]['sequence']} := eq_refl.",
            f"Example {o_name}_seq1 : sequence (sessions (after {o_name}) 1) = {sessions[1]['sequence']} := eq_refl.",
            f"Example {o_name}_tok : next_token (common (after {o_name})) = {st_snap['next_token']} := eq_refl.",
        ])
        prev_state = f"(after {o_name})"

    comp5_pay = cast("list[int]", comp5["payload_out"])
    exp5_st = cast("JSONObject", exp5["state"])
    closed_st = cast("JSONObject", closed["state"])
    h0_new_term = _handle_term(cast("JSONObject", readmitted["handle_out"]))
    read_new_pay = cast("list[int]", read_new["payload_out"])
    crash_st = cast("JSONObject", crashed["state"])
    crash_sessions = cast("list[JSONObject]", crash_st["sessions"])
    crash_back = _resident_term(cast("JSONObject", crash_st["backing"]))

    lines.extend([
        f"Definition {prefix}_at3 := at_clock {prev_state} 3.",
        f"Definition {prefix}_beg3 := begin_read corr_bounds {prefix}_at3 {prefix}_h0 7 {prefix}_id 2 8.",
        f"Example {prefix}_beg3_ok : accepted {prefix}_beg3 = true := eq_refl.",
        f"Definition {prefix}_ren3 := renew_reservation corr_bounds (begun_state {prefix}_beg3) {prefix}_h0 7 {prefix}_id.",
        f"Example {prefix}_ren3_ok : snd {prefix}_ren3 = true := eq_refl.",
        f"Definition {prefix}_at5 := at_clock (fst {prefix}_ren3) 5.",
        f"Definition {prefix}_comp5 := complete corr_verify {prefix}_at5 0 (sequence (sessions {prefix}_at5 0)).",
        f"Example {prefix}_comp5_pay : payload {prefix}_comp5 = Some {_nat_list(comp5_pay)} := eq_refl.",
        f"Definition {prefix}_exp5 := read_once corr_verify corr_bounds (after {prefix}_comp5) {prefix}_h1 7 {prefix}_id 0 4.",
        f"Example {prefix}_exp5_refuses : payload {prefix}_exp5 = None /\\ sequence (sessions (after {prefix}_exp5) 1) = {cast('list[JSONObject]', exp5_st['sessions'])[1]['sequence']}.",
        "Proof. vm_compute; split; reflexivity. Qed.",
        f"Definition {prefix}_closed := close_reservation (after {prefix}_exp5) {prefix}_h0.",
        f"Example {prefix}_closed_ok : snd {prefix}_closed = true /\\ reservations (common (fst {prefix}_closed)) 0 = None /\\ next_token (common (fst {prefix}_closed)) = {closed_st['next_token']}.",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        f"Definition {prefix}_readm := admit corr_bounds (fst {prefix}_closed) 0 7 {prefix}_id 0 16.",
        f"Definition {prefix}_h0_new := {h0_new_term}.",
        f"Example {prefix}_readm_ok : {prefix}_readm = (fst {prefix}_readm, Some {prefix}_h0_new) /\\ close_reservation (fst {prefix}_readm) {prefix}_h0 = (fst {prefix}_readm, false).",
        "Proof. vm_compute; split; reflexivity. Qed.",
        f"Definition {prefix}_read_new := read_once corr_verify corr_bounds (fst {prefix}_readm) {prefix}_h0_new 7 {prefix}_id 0 16.",
        f"Example {prefix}_read_new_pay : payload {prefix}_read_new = Some {_nat_list(read_new_pay)} := eq_refl.",
        f"Definition {prefix}_pre_crash := begun_state (begin_read corr_bounds (after {prefix}_read_new) {prefix}_h0_new 7 {prefix}_id 0 8).",
        f"Definition {prefix}_crashed := crash {prefix}_pre_crash.",
        f"Example {prefix}_crash_eq : current_boot (common {prefix}_crashed) = {crash_st['boot']} /\\ backing (common {prefix}_crashed) = Some {crash_back} /\\ reservations (common {prefix}_crashed) 0 = None /\\ reservations (common {prefix}_crashed) 1 = None /\\ pending (sessions {prefix}_crashed 0) = None /\\ pending (sessions {prefix}_crashed 1) = None /\\ sequence (sessions {prefix}_crashed 0) = {crash_sessions[0]['sequence']} /\\ sequence (sessions {prefix}_crashed 1) = {crash_sessions[1]['sequence']} /\\ payload (complete corr_verify {prefix}_crashed 0 1) = None /\\ admit corr_bounds {prefix}_crashed 0 7 {prefix}_id 0 16 = ({prefix}_crashed, None).",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        "",
    ])
    return lines


def _two_slot_gallina(idx: int, camp: JSONObject) -> list[str]:
    prefix = f"ts_{idx}"
    gen0 = int(cast("int", camp["initial_generation"]))
    p1 = cast("list[int]", camp["p1"])
    p2 = cast("list[int]", camp["p2"])
    p3 = cast("list[int]", camp["p3"])
    id1 = cast("JSONObject", camp["id1"])
    id2 = cast("JSONObject", camp["id2"])
    steps = cast("list[JSONObject]", camp["steps"])
    by_op = {str(st["op"]): st for st in steps}

    admit0 = by_op["admit_h0"]
    comp_pred = by_op["complete_pred_h0"]
    admit1 = by_op["admit_h1"]
    ret_no_bar = by_op["retire_pred_no_barrier"]
    ret_bar = by_op["retire_pred_barrier"]
    comp_cur = by_op["complete_cur_h1"]
    rep_v3 = by_op["replace_cow_v3"]
    crashed = by_op["crash"]

    rep_v3_cur = cast("JSONObject", cast("JSONObject", rep_v3["state"])["current_backing"])
    id3 = cast("JSONObject", rep_v3_cur["resident_identity"])
    crash_st = cast("JSONObject", crashed["state"])
    crash_cur = _resident_term(cast("JSONObject", crash_st["current_backing"]))
    crash_pred = _resident_term(cast("JSONObject", crash_st["predecessor_backing"]))
    crash_sessions = cast("list[JSONObject]", crash_st["sessions"])

    pred_expected = (
        f"Some {_nat_list(cast('list[int]', comp_pred['payload_out']))}"
        if comp_pred["ok"] else "None"
    )
    cur_expected = _nat_list(cast("list[int]", comp_cur["payload_out"]))

    return [
        f"Definition {prefix}_id1 : Identity := {_identity_term(id1)}.",
        f"Definition {prefix}_id2 : Identity := {_identity_term(id2)}.",
        f"Definition {prefix}_id3 : Identity := {_identity_term(id3)}.",
        f"Definition {prefix}_r1 : Resident := {_resident_term({'resident_identity': id1, 'resident_bytes': p1, 'accepting': True})}.",
        f"Definition {prefix}_r2 : Resident := {_resident_term({'resident_identity': id2, 'resident_bytes': p2, 'accepting': True})}.",
        f"Definition {prefix}_r3 : Resident := {_resident_term({'resident_identity': id3, 'resident_bytes': p3, 'accepting': True})}.",
        f"Definition {prefix}_init : TwoSlotState :=",
        "  {| ts_common := {| current_backing := None; predecessor_backing := None;",
        "     ts_reservations := fun _ => None; ts_authority := fun _ => true;",
        "     ts_next_token := 0; ts_clock := 0; ts_current_boot := 0;",
        f"     ts_current_generation := {gen0}; ts_common_counter := 0 |}};",
        "     ts_sessions := fun _ => empty_session |}.",
        f"Definition {prefix}_pub := ts_publish_initial corr_bounds {prefix}_init {prefix}_r1.",
        f"Definition {prefix}_s0 := fst {prefix}_pub.",
        f"Definition {prefix}_adm0 := ts_admit corr_bounds {prefix}_s0 0 7 {prefix}_id1 0 16.",
        f"Definition {prefix}_s1 := fst {prefix}_adm0.",
        f"Definition {prefix}_h0 := {_handle_term(cast('JSONObject', admit0['handle_out']))}.",
        f"Example {prefix}_c_admit0 : {prefix}_adm0 = ({prefix}_s1, Some {prefix}_h0).",
        "Proof. vm_compute; reflexivity. Qed.",
        f"Definition {prefix}_beg0 := ts_begin_read corr_bounds {prefix}_s1 {prefix}_h0 7 {prefix}_id1 0 16.",
        f"Definition {prefix}_s2 := ts_begun_state {prefix}_beg0.",
        f"Definition {prefix}_cow2 := ts_replace_cow corr_bounds {prefix}_s2 {prefix}_r2.",
        f"Definition {prefix}_s3 := fst {prefix}_cow2.",
        f"Example {prefix}_cow2_ok : snd {prefix}_cow2 = true /\\ current_backing (ts_common {prefix}_s3) = Some {prefix}_r2 /\\ predecessor_backing (ts_common {prefix}_s3) = Some {prefix}_r1.",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        f"Definition {prefix}_pred_done := ts_complete corr_verify {prefix}_s3 0 1.",
        f"Example {prefix}_pred_pay : ts_payload {prefix}_pred_done = {pred_expected} := eq_refl.",
        f"Example {prefix}_pred_nocommon : ts_common (ts_after {prefix}_pred_done) = ts_common {prefix}_s3 /\\ no_common (ts_journal {prefix}_pred_done).",
        f"Proof. split; [reflexivity|apply (proj1 (proj2 (proj2 (proj2 (ts_begin_and_complete_no_common_writes corr_verify corr_bounds {prefix}_s3 {prefix}_h0 0 7 {prefix}_id1 0 16 1)))))]. Qed.",
        f"Definition {prefix}_adm1 := ts_admit corr_bounds (ts_after {prefix}_pred_done) 1 7 {prefix}_id2 4 8.",
        f"Definition {prefix}_s5 := fst {prefix}_adm1.",
        f"Definition {prefix}_h1 := {_handle_term(cast('JSONObject', admit1['handle_out']))}.",
        f"Example {prefix}_c_admit1 : {prefix}_adm1 = ({prefix}_s5, Some {prefix}_h1).",
        "Proof. vm_compute; reflexivity. Qed.",
        f"Definition {prefix}_s6 := ts_begun_state (ts_begin_read corr_bounds {prefix}_s5 {prefix}_h1 7 {prefix}_id2 0 8).",
        f"Example {prefix}_v3_occupied_refuses : snd (ts_replace_cow corr_bounds {prefix}_s6 {prefix}_r3) = false := eq_refl.",
        f"Definition {prefix}_s7 := ts_retire_predecessor {prefix}_s6 false.",
        f"Example {prefix}_quarantine_ok : predecessor_backing (ts_common {prefix}_s7) = Some (close_resident {prefix}_r1) /\\ ts_reservations (ts_common {prefix}_s7) 0 = None /\\ snd (ts_replace_cow corr_bounds {prefix}_s7 {prefix}_r3) = false /\\ predecessor_backing (ts_common {prefix}_s7) = Some {_resident_term(cast('JSONObject', cast('JSONObject', ret_no_bar['state'])['predecessor_backing']))}.",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        f"Definition {prefix}_s8 := ts_retire_predecessor {prefix}_s7 true.",
        f"Example {prefix}_release_ok : predecessor_backing (ts_common {prefix}_s8) = None /\\ ts_current_generation (ts_common {prefix}_s8) = {cast('JSONObject', ret_bar['state'])['generation']}.",
        "Proof. vm_compute; split; reflexivity. Qed.",
        f"Definition {prefix}_cur_done := ts_complete corr_verify {prefix}_s8 1 1.",
        f"Example {prefix}_cur_pay : ts_payload {prefix}_cur_done = Some {cur_expected} := eq_refl.",
        f"Definition {prefix}_cow3 := ts_replace_cow corr_bounds (ts_after {prefix}_cur_done) {prefix}_r3.",
        f"Definition {prefix}_s10 := fst {prefix}_cow3.",
        f"Example {prefix}_cow3_ok : snd {prefix}_cow3 = true /\\ current_backing (ts_common {prefix}_s10) = Some {prefix}_r3 /\\ predecessor_backing (ts_common {prefix}_s10) = Some {prefix}_r2.",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        f"Definition {prefix}_crashed := ts_crash {prefix}_s10.",
        f"Example {prefix}_crash_eq : ts_current_boot (ts_common {prefix}_crashed) = {crash_st['boot']} /\\ current_backing (ts_common {prefix}_crashed) = Some {crash_cur} /\\ predecessor_backing (ts_common {prefix}_crashed) = Some {crash_pred} /\\ ts_reservations (ts_common {prefix}_crashed) 0 = None /\\ ts_reservations (ts_common {prefix}_crashed) 1 = None /\\ pending (ts_sessions {prefix}_crashed 0) = None /\\ pending (ts_sessions {prefix}_crashed 1) = None /\\ sequence (ts_sessions {prefix}_crashed 0) = {crash_sessions[0]['sequence']} /\\ sequence (ts_sessions {prefix}_crashed 1) = {crash_sessions[1]['sequence']}.",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        "",
    ]


def _scalar_gallina(idx: int, camp: JSONObject) -> list[str]:
    prefix = f"sc_{idx}"
    gen0 = int(cast("int", camp["initial_generation"]))
    payload = cast("list[int]", camp["payload"])
    identity = cast("JSONObject", camp["identity"])
    st = cast("JSONObject", camp["state"])
    cur_back = _resident_term(cast("JSONObject", st["current_backing"]))
    sessions = cast("list[JSONObject]", st["sessions"])
    return [
        f"Definition {prefix}_id : Identity := {_identity_term(identity)}.",
        f"Definition {prefix}_res : Resident := {_resident_term({'resident_identity': identity, 'resident_bytes': payload, 'accepting': True})}.",
        f"Definition {prefix}_init : TwoSlotState :=",
        "  {| ts_common := {| current_backing := None; predecessor_backing := None;",
        "     ts_reservations := fun _ => None; ts_authority := fun _ => true;",
        "     ts_next_token := 0; ts_clock := 0; ts_current_boot := 0;",
        f"     ts_current_generation := {gen0}; ts_common_counter := 0 |}};",
        "     ts_sessions := fun _ => empty_session |}.",
        f"Definition {prefix}_s0 := fst (ts_publish_initial corr_bounds {prefix}_init {prefix}_res).",
        f"Definition {prefix}_adm0 := ts_admit corr_bounds {prefix}_s0 0 7 {prefix}_id 0 16.",
        f"Definition {prefix}_adm1 := ts_admit corr_bounds (fst {prefix}_adm0) 1 7 {prefix}_id 4 12.",
        f"Definition {prefix}_h0 := {{| token := 1; boot_epoch := 0; holder := 0; handle_identity := {prefix}_id; window_start := 0; window_length := 16 |}}.",
        f"Definition {prefix}_h1 := {{| token := 2; boot_epoch := 0; holder := 1; handle_identity := {prefix}_id; window_start := 4; window_length := 12 |}}.",
        f"Definition {prefix}_s1 := ts_begun_state (ts_begin_read corr_bounds (fst {prefix}_adm1) {prefix}_h0 7 {prefix}_id 0 16).",
        f"Definition {prefix}_s2 := ts_begun_state (ts_begin_read corr_bounds {prefix}_s1 {prefix}_h1 7 {prefix}_id 0 12).",
        f"Definition {prefix}_s3 := ts_after (ts_complete corr_verify {prefix}_s2 0 1).",
        f"Definition {prefix}_s4 := ts_begun_state (ts_begin_read corr_bounds {prefix}_s3 {prefix}_h0 7 {prefix}_id 0 8).",
        f"Definition {prefix}_ret := ts_retire_owner {prefix}_s4 false.",
        f"Example {prefix}_ret_eq : current_backing (ts_common {prefix}_ret) = Some {cur_back} /\\ ts_reservations (ts_common {prefix}_ret) 0 = None /\\ ts_reservations (ts_common {prefix}_ret) 1 = None /\\ pending (ts_sessions {prefix}_ret 0) = None /\\ pending (ts_sessions {prefix}_ret 1) = None /\\ sequence (ts_sessions {prefix}_ret 0) = {sessions[0]['sequence']} /\\ sequence (ts_sessions {prefix}_ret 1) = {sessions[1]['sequence']}.",
        "Proof. vm_compute; repeat split; reflexivity. Qed.",
        "",
    ]


def _build_correspondence_module(trace: JSONObject) -> str:
    bounds = cast("JSONObject", trace["bounds"])
    pairs = _verify_pairs(trace)
    lines: list[str] = [
        "(* SPDX-License-Identifier: Apache-2.0 *)",
        "From Stdlib Require Import Bool List Arith.",
        "From VerifiedOS Require Import ResidentReads.",
        "",
        "Definition corr_bounds : Bounds := {|",
        f"  byte_bound := {bounds['byte_bound']};",
        f"  read_bound := {bounds['read_bound']};",
        f"  retention_bound := {bounds['retention_bound']};",
        f"  counter_bound := {bounds['counter_bound']} |}}.",
        "",
        "Example corr_bounds_valid : bounds_ok corr_bounds = true := eq_refl.",
        "",
        "Definition corr_verify (bytes digest : list nat) : bool :=",
    ]
    clauses: list[str] = []
    for payload, digest in pairs:
        clauses.append(
            "(if list_eq_dec Nat.eq_dec bytes "
            + _nat_list(payload)
            + " then if list_eq_dec Nat.eq_dec digest "
            + _nat_list(digest)
            + " then true else false else false)"
        )
    lines.append("  " + (" ||\n  ".join(clauses) if clauses else "false") + ".")
    lines.append("")

    for idx, camp in enumerate(cast("list[JSONObject]", trace["single_slot"])):
        lines.extend(_single_slot_gallina(idx, camp))
    for idx, camp in enumerate(cast("list[JSONObject]", trace["two_slot"])):
        lines.extend(_two_slot_gallina(idx, camp))
    for idx, camp in enumerate(cast("list[JSONObject]", trace["scalar_retire"])):
        lines.extend(_scalar_gallina(idx, camp))
    return "\n".join(lines) + "\n"


def _compiler(work_dir: Path) -> tuple[str, tuple[str, ...]]:
    with tempfile.TemporaryDirectory(prefix="probe-", dir=work_dir) as probe_dir:
        probe_c = Path(probe_dir) / "probe.c"
        probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        probe_out = Path(probe_dir) / "probe"
        for candidate in ("clang", "gcc", "cc"):
            found = shutil.which(candidate)
            if found is None:
                continue
            res = subprocess.run(
                [found, "-std=c17", "-fsanitize=address,undefined",
                 str(probe_c), "-o", str(probe_out)],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if res.returncode == 0:
                return found, ("-fsanitize=address,undefined",)
        for candidate in ("clang", "gcc", "cc"):
            found = shutil.which(candidate)
            if found is not None:
                return found, ()
    raise AssertionError("native C compiler required")


def _compile_harness(directory: Path, resident_src: Path | None = None,
                     scalar_src: Path | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    compiler, san_flags = _compiler(directory)
    binary = directory / "resident_corr"
    deps = [
        str(resident_src if resident_src is not None else RESIDENT_SOURCE),
        str(scalar_src if scalar_src is not None else SCALAR_SOURCE),
        str(ROOT / "storage" / "src" / "storage_publish.c"),
        str(ROOT / "storage" / "src" / "crypto_core.c"),
        str(ROOT / "storage" / "src" / "node_image.c"),
        str(ROOT / "storage" / "src" / "tree_image.c"),
        str(ROOT / "storage" / "src" / "tree_update.c"),
        str(ROOT / "kernel" / "src" / "effects.c"),
        str(ROOT / "kernel" / "src" / "context.c"),
        str(ROOT / "supervisor" / "src" / "supervisor.c"),
        str(ROOT / "supervisor" / "src" / "effects.c"),
        str(ROOT / "supervisor" / "src" / "manifest.c"),
        str(HARNESS),
    ]
    cmd = [
        compiler,
        "-std=c17",
        "-O1",
        "-Wall",
        "-Wextra",
        "-Wstrict-prototypes",
        "-Werror",
        "-pedantic",
        *san_flags,
        "-DVOS_HOST_MODEL",
        "-I" + str(ROOT / "storage" / "include"),
        "-I" + str(ROOT / "kernel" / "include"),
        "-I" + str(ROOT / "supervisor" / "include"),
        *deps,
        "-o",
        str(binary),
    ]
    built = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    ensure(built.returncode == 0, f"compile failure is not a mutant kill: {built.stderr}")
    return binary


def _run_trace(binary: Path) -> JSONObject:
    ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60, check=False)
    ensure(ran.returncode == 0, f"correspondence harness failed: {ran.stderr}")
    parsed = json.loads(ran.stdout, object_pairs_hook=unique_object)
    ensure(isinstance(parsed, dict), "trace root must be a JSON object")
    return cast("JSONObject", parsed)


def _python_oracle() -> None:
    sample_id: JSONObject = {
        "owner": 1, "domain": 7, "object_id": 1, "version": 1,
        "root_kind": "UserData", "generation": 2, "root_digest": [1] * 32,
    }
    sample_id2 = {**sample_id, "version": 2}
    sample_id3 = {**sample_id, "version": 3}
    p1 = list(range(16))
    p2 = list(range(16, 32))
    p3 = list(range(32, 48))
    h0: JSONObject = {
        "token": 1, "boot_epoch": 0, "holder": 0,
        "handle_identity": sample_id, "window_start": 0, "window_length": 16,
    }
    h1: JSONObject = {
        "token": 2, "boot_epoch": 0, "holder": 1,
        "handle_identity": sample_id, "window_start": 4, "window_length": 12,
    }
    h0_new: JSONObject = {**h0, "token": 3}
    res_true: JSONObject = {"resident_identity": sample_id, "resident_bytes": p1, "accepting": True}
    res_false: JSONObject = {"resident_identity": sample_id, "resident_bytes": p1, "accepting": False}
    ss_state: JSONObject = {
        "boot": 1, "generation": 2, "next_token": 3, "clock": 5, "grants": 0, "current": 0,
        "backing": res_false,
        "reservations": [None, None],
        "sessions": [{"sequence": 6, "pending": None}, {"sequence": 4, "pending": None}],
    }
    reads = [
        {"op": "read_h0" if i % 2 == 0 else "read_h1", "ok": True,
         "cells": [{"kind": 2, "name": "PrivateSequence", "holder": i % 2}],
         "payload_out": p1 if i % 2 == 0 else p1[4:16],
         "handle_out": None, "state": ss_state}
        for i in range(6)
    ]
    ss_steps = [
        {"op": "publish", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ss_state},
        {"op": "admit_h0", "ok": True, "cells": [], "payload_out": None, "handle_out": h0, "state": ss_state},
        {"op": "admit_h1", "ok": True, "cells": [], "payload_out": None, "handle_out": h1, "state": ss_state},
        *reads,
        {"op": "complete_h0_at5", "ok": True, "cells": [], "payload_out": p1[2:10], "handle_out": None, "state": ss_state},
        {"op": "begin_h1_expired_at5", "ok": False, "cells": [], "payload_out": None, "handle_out": None, "state": ss_state},
        {"op": "close_h0", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ss_state},
        {"op": "readmit_h0", "ok": True, "cells": [], "payload_out": None, "handle_out": h0_new, "state": ss_state},
        {"op": "read_readmitted_h0", "ok": True, "cells": [], "payload_out": p1, "handle_out": None, "state": ss_state},
        {"op": "crash", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ss_state},
    ]
    ts_cur3: JSONObject = {"resident_identity": sample_id3, "resident_bytes": p3, "accepting": True}
    ts_state_v3: JSONObject = {
        "boot": 1, "generation": 2, "next_token": 2, "clock": 1, "grants": 0, "current": 0,
        "current_backing": {"resident_identity": sample_id3, "resident_bytes": p3, "accepting": False},
        "predecessor_backing": {"resident_identity": sample_id2, "resident_bytes": p2, "accepting": False},
        "reservations": [None, None],
        "sessions": [{"sequence": 1, "pending": None}, {"sequence": 1, "pending": None}],
    }
    ts_state_quar: JSONObject = {**ts_state_v3, "predecessor_backing": res_false}
    ts_state_cur3: JSONObject = {**ts_state_v3, "current_backing": ts_cur3}
    ts_steps = [
        {"op": "admit_h0", "ok": True, "cells": [], "payload_out": None, "handle_out": h0, "state": ts_state_v3},
        {"op": "complete_pred_h0", "ok": True, "cells": [], "payload_out": p1, "handle_out": None, "state": ts_state_v3},
        {"op": "admit_h1", "ok": True, "cells": [], "payload_out": None, "handle_out": {**h1, "handle_identity": sample_id2, "window_start": 4, "window_length": 8}, "state": ts_state_v3},
        {"op": "retire_pred_no_barrier", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ts_state_quar},
        {"op": "retire_pred_barrier", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ts_state_quar},
        {"op": "complete_cur_h1", "ok": True, "cells": [], "payload_out": p2[4:12], "handle_out": None, "state": ts_state_quar},
        {"op": "replace_cow_v3", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ts_state_cur3},
        {"op": "crash", "ok": True, "cells": [], "payload_out": None, "handle_out": None, "state": ts_state_v3},
    ]
    sample_trace: JSONObject = {
        "bounds": {"byte_bound": 32, "read_bound": 16, "retention_bound": 4, "counter_bound": 30},
        "single_slot": [{"kind": "UserData", "initial_generation": 2, "identity": sample_id, "payload": p1, "steps": ss_steps}],
        "two_slot": [{"kind": "UserData", "initial_generation": 2, "p1": p1, "p2": p2, "p3": p3, "id1": sample_id, "id2": sample_id2, "steps": ts_steps}],
        "scalar_retire": [{"kind": "UserData", "initial_generation": 2, "identity": sample_id, "payload": p1, "state": {**ts_state_v3, "current_backing": res_true}}],
    }
    source = _build_correspondence_module(sample_trace)
    ensure("From VerifiedOS Require Import ResidentReads." in source, "missing ResidentReads import")
    ensure("Example ss_0_read_0_g_nocommon" in source and "Example ts_0_crash_eq" in source,
           "missing expected correspondence examples")
    ensure("Example sc_0_ret_eq" in source, "missing scalar correspondence example")
    # Duplicate JSON keys must be rejected by unique_object.
    rejected = False
    try:
        json.loads('{"a":1,"a":2}', object_pairs_hook=unique_object)
    except ValueError:
        rejected = True
    ensure(rejected, "unique_object did not reject duplicate JSON key")


def _native_c_and_mutants() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "resident-correspondence-tests"
    work.mkdir(parents=True, exist_ok=True)
    res_src = RESIDENT_SOURCE.read_text(encoding="utf-8")
    sca_src = SCALAR_SOURCE.read_text(encoding="utf-8")

    mutants: list[tuple[str, str, str, str, str]] = [
        ("resident", "common-counter",
         "    /* BEGIN_TRAFFIC: all persistent read stores are holder-private or output. */",
         "    /* BEGIN_TRAFFIC: all persistent read stores are holder-private or output. */\n"
         "    PUT(o, VOS_RESIDENT_COMMON, o->common.next_token, o->common.next_token + 1);\n"
         "    PUT(o, VOS_RESIDENT_COMMON, o->common.next_token, o->common.next_token - 1);",
         "common write during read traffic"),
        ("resident", "renew-without-budget",
         "if (r->renewed >= VOS_RESIDENT_RENEWALS || expires <= r->expires ||",
         "if (expires <= r->expires ||",
         "double renewal succeeded"),
        ("resident", "stale-close",
         "if (!r->live || domain != r->handle.identity.domain ||\n"
         "        !handle_equal(h, &r->handle)) return 0;",
         "if (!r->live || domain != r->handle.identity.domain ||\n"
         "        !identity_equal(&h->identity, &r->handle.identity)) return 0;",
         "stale handle accepted after close/readmit"),
        ("resident", "replace-occupied-backing",
         "!identity_ok(identity) || b->occupied ||",
         "!identity_ok(identity) ||",
         "third version accepted while predecessor occupied"),
        ("resident", "read-current-as-predecessor",
         "const struct vos_resident_backing *b = &o->common.backing[o->common.reservation[holder].backing];",
         "const struct vos_resident_backing *b = &o->common.backing[o->common.current];",
         "userdata predecessor failed after CoW replace"),
        ("resident", "release-predecessor-without-barrier",
         "    if (barrier_completed != 1) return 0;\n    release_backing(o, b);",
         "    release_backing(o, b);\n    if (barrier_completed != 1) return 0;",
         "third version accepted while predecessor quarantined"),
        ("resident", "crash-keeps-accepting",
         "    for (uint32_t slot = 0; slot < VOS_RESIDENT_BACKINGS; ++slot)\n"
         "        PUT(o, VOS_RESIDENT_COMMON, o->common.backing[slot].accepting, 0U);\n"
         "    PUT(o, VOS_RESIDENT_COMMON, o->common.grants, 0U);\n"
         "    PUT(o, VOS_RESIDENT_COMMON, o->common.boot, new_boot);",
         "    PUT(o, VOS_RESIDENT_COMMON, o->common.grants, 0U);\n"
         "    PUT(o, VOS_RESIDENT_COMMON, o->common.boot, new_boot);",
         "crash failed to close backing or preserve sequences"),
        ("scalar", "scalar-premature-reuse",
         "/* CONTAINED_ONLY: semantic completion never authorizes backing release. */",
         "(void)vos_resident_retire(o, 1);",
         "scalar retirement failed or released backing"),
    ]

    with tempfile.TemporaryDirectory(prefix="native-corr-", dir=work) as tmp:
        tmp_path = Path(tmp)
        pristine_bin = _compile_harness(tmp_path / "pristine")
        trace = _run_trace(pristine_bin)
        ensure(len(cast("list[object]", trace["single_slot"])) == 2 and
               len(cast("list[object]", trace["two_slot"])) == 2 and
               len(cast("list[object]", trace["scalar_retire"])) == 2,
               "expected both UserData and SystemImage campaigns")

        for kind, name, target, replacement, expected in mutants:
            base = res_src if kind == "resident" else sca_src
            ensure(base.count(target) == 1, f"mutant anchor must be unique for {name}")
            mut_dir = tmp_path / name
            mut_dir.mkdir(parents=True, exist_ok=True)
            mut_file = mut_dir / (RESIDENT_SOURCE.name if kind == "resident" else SCALAR_SOURCE.name)
            mut_file.write_text(base.replace(target, replacement, 1), encoding="utf-8", newline="\n")
            mut_bin = _compile_harness(
                mut_dir,
                resident_src=mut_file if kind == "resident" else None,
                scalar_src=mut_file if kind == "scalar" else None,
            )
            ran = subprocess.run([str(mut_bin)], capture_output=True, text=True, timeout=60, check=False)
            ensure(ran.returncode != 0 and expected in ran.stderr,
                   f"mutant {name} survived or missed oracle: {ran.stderr}")


def _gallina_correspondence() -> None:
    work = toolenv.environment(ROOT, sys.platform).parent / "resident-correspondence-tests"
    stage_dir = work / "gallina-stage"
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged = proof_staging.stage(ROOT, stage_dir, ("ResidentReads.v",))
    for artifact in staged.sources:
        vo = artifact.with_suffix(".vo")
        if not vo.is_file():
            done = subprocess.run(
                [*env.rocq_command(), "-q", "-Q", str(stage_dir), "VerifiedOS",
                 *STRICT_ROCQ_FLAGS, str(artifact)],
                cwd=stage_dir, capture_output=True, text=True, timeout=180, check=False,
            )
            ensure(done.returncode == 0, f"failed to compile staged {artifact.name}: {done.stderr}")

    with tempfile.TemporaryDirectory(prefix="rocq-corr-", dir=work) as tmp:
        temp = Path(tmp)
        binary = _compile_harness(temp)
        trace = _run_trace(binary)
        source = _build_correspondence_module(trace)
        comparison = temp / "ResidentReadsCorrespondence.v"
        comparison.write_text(source, encoding="utf-8", newline="")

        compiled = subprocess.run(
            [*env.rocq_command(), "-q", "-Q", str(stage_dir), "VerifiedOS",
             "-Q", str(temp), "VerifiedOS", *STRICT_ROCQ_FLAGS, str(comparison)],
            cwd=temp, capture_output=True, text=True, timeout=180, check=False,
        )
        ensure(compiled.returncode == 0,
               f"strict Rocq rejected ResidentReadsCorrespondence.v: {compiled.stderr}")

        checked = subprocess.run(
            [*env.rocqchk_command(), "-silent", "-o",
             "-R", str(stage_dir), "VerifiedOS",
             "-R", str(temp), "VerifiedOS",
             "VerifiedOS.ResidentReadsCorrespondence"],
            cwd=temp, capture_output=True, text=True, timeout=180, check=False,
        )
        ensure(checked.returncode == 0,
               f"rocqchk rejected ResidentReadsCorrespondence closure: {checked.stderr}")

        # Negative control: perturbing a C-observed byte must fail strict Rocq conversion.
        tampered = temp / "ResidentReadsTampered.v"
        needle = "ss_0_read_0_payload : payload ss_0_read_0 = Some (cons "
        idx = source.find(needle)
        ensure(idx != -1, "tampered negative control anchor missing")
        rest = source[idx + len(needle):]
        first_num_end = rest.find(" ")
        first_num = int(rest[:first_num_end])
        perturbed = (first_num + 1) % 256
        tampered_src = (
            source[:idx + len(needle)] + str(perturbed) + rest[first_num_end:]
        )
        ensure(tampered_src != source, "tampered negative control failed to perturb source")
        tampered.write_text(tampered_src, encoding="utf-8", newline="")
        bad = subprocess.run(
            [*env.rocq_command(), "-q", "-Q", str(stage_dir), "VerifiedOS",
             "-Q", str(temp), "VerifiedOS", *STRICT_ROCQ_FLAGS, str(tampered)],
            cwd=temp, capture_output=True, text=True, timeout=180, check=False,
        )
        ensure(bad.returncode != 0, "tampered C trace passed strict Rocq ResidentReads.v comparison")

    staged.validate(ROOT)


def cases() -> list[Case]:
    return [
        Case("ResidentReads.v Gallina correspondence oracle and serialization",
             _python_oracle, lane="any"),
        Case("compiled C resident correspondence trace and behavioral mutants",
             _native_c_and_mutants, lane="guest"),
        Case("compiled C-to-Gallina ResidentReads.v correspondence and rocqchk closure",
             _gallina_correspondence, lane="toolchain"),
    ]
