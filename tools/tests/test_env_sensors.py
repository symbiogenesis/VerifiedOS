# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracle and native C17 ASan/UBSan + Clang + mutation controls for env-sensors/."""

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
ES_DIR = ROOT / "env-sensors"
ES_H = ES_DIR / "include" / "vos_env_sensors.h"
ES_C = ES_DIR / "src" / "env_sensors.c"
ES_TEST_C = ES_DIR / "test" / "test_env_sensors.c"
ES_README = ES_DIR / "README.md"
PROOFS_V = ROOT / "proofs" / "EnvironmentalSensors.v"

FAM_SUPPLY = "SupplyWindow"
FAM_CLOCK = "ClockMonitor"
FAM_TIMING = "TimingReplica"
FAM_OPTICAL = "OpticalPhotocurrent"


@dataclass(frozen=True, slots=True)
class _OracleRail:
    rail_id: int
    reaches_rot: bool
    islands: tuple[int, ...]
    sites: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _OracleClock:
    clock_id: int
    is_rot_slow: bool
    reaches_rot: bool
    islands: tuple[int, ...]
    sites: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _OracleDatapath:
    dp_id: int
    block_class: str
    island_id: int
    reaches_rot: bool


@dataclass(frozen=True, slots=True)
class _OracleRegion:
    region_id: int
    reaches_rot: bool
    islands: tuple[int, ...]
    declared_pitch_um: int
    gap_free: bool
    occludes_backside: bool


@dataclass(frozen=True, slots=True)
class _OracleTopology:
    has_rot: bool
    has_s0: bool
    has_s1: bool
    rails: tuple[_OracleRail, ...]
    clocks: tuple[_OracleClock, ...]
    datapaths: tuple[_OracleDatapath, ...]
    regions: tuple[_OracleRegion, ...]


@dataclass(frozen=True, slots=True)
class _OracleSensor:
    sensor_id: int
    family: str
    resource_id: int
    site_id: int
    affected_islands: tuple[int, ...]
    rot_self_fault: bool
    always_on: bool
    ref_resource_id: int
    health_observer_id: int
    deps: tuple[int, ...] = ()
    enable_constant: bool = True
    has_pending: bool = False
    has_owner: bool = True
    has_evidence_tuple: bool = True
    retired_artifact: bool = False
    sw_writable_threshold: bool = False
    sw_writable_disable: bool = False
    dynamic_calibration: bool = False
    adds_isa_or_csr: bool = False
    opp_table_bound: bool = True
    uses_only_guarded_liveness: bool = False
    vmin_uv: int = 750000
    vmax_uv: int = 850000
    hyst_uv: int = 15000
    period_min_ps: int = 900
    period_max_ps: int = 1100
    high_min_ps: int = 400
    high_max_ps: int = 600
    low_min_ps: int = 400
    low_max_ps: int = 600
    duty_min_permille: int = 400
    duty_max_permille: int = 600
    missing_edge_max_ps: int = 1500
    observer_clock_id: int = 21
    is_rot_slow: bool = False
    adaptive_ref: bool = False
    slack_min_ps: int = 120
    correspondence_qualified: bool = True
    fixed_public_excitation: bool = True
    samples_operand: bool = False
    photocurrent_trip_na: int = 500
    dark_current_max_na: int = 40
    site_pitch_um: int = 50
    max_site_pitch_um: int = 60
    occludes_backside: bool = False


@dataclass(frozen=True, slots=True)
class _OracleSample:
    sensor_id: int
    sensor_disabled: bool = False
    corrupt_constants: bool = False
    open_or_stuck_line: bool = False
    stopped_reference: bool = False
    broken_transducer: bool = False
    health_timeout: bool = False
    table_off_authorized: bool = False
    consumer_reset_isolated: bool = False
    physically_inactive: bool = False
    transition_overrun: bool = False
    voltage_uv: int = 760000
    period_ps: int = 1050
    high_ps: int = 520
    low_ps: int = 530
    edge_gap_ps: int = 1100
    clock_stopped: bool = False
    slack_ps: int = 130
    photocurrent_na: int = 420
    sw_operand_value: int = 0


def _validate_sensor_oracle(s: _OracleSensor) -> str:
    if s.has_pending:
        return "PENDING_FIELD"
    if not (s.has_owner and s.has_evidence_tuple and not s.retired_artifact and s.opp_table_bound):
        return "RETIRED_OR_UNBOUND"
    if (
        not s.enable_constant
        or s.sw_writable_threshold
        or s.sw_writable_disable
        or s.dynamic_calibration
        or s.adds_isa_or_csr
    ):
        return "MUTABLE_POLICY"
    if s.family == FAM_SUPPLY:
        if not (0 < s.vmin_uv < s.vmax_uv and 0 < s.hyst_uv < (s.vmax_uv - s.vmin_uv)):
            return "INVALID_BANDS"
    elif s.family == FAM_CLOCK:
        if s.adaptive_ref:
            return "MUTABLE_POLICY"
        if not (
            0 < s.period_min_ps <= s.period_max_ps
            and 0 < s.high_min_ps <= s.high_max_ps
            and 0 < s.low_min_ps <= s.low_max_ps
            and s.high_max_ps < s.period_max_ps
            and s.low_max_ps < s.period_max_ps
            and s.high_min_ps + s.low_min_ps <= s.period_max_ps
            and s.period_min_ps <= s.high_max_ps + s.low_max_ps
            and 0 < s.duty_min_permille <= s.duty_max_permille < 1000
            and s.duty_min_permille * s.period_min_ps <= s.high_max_ps * 1000
            and s.high_min_ps * 1000 <= s.duty_max_permille * s.period_max_ps
            and s.missing_edge_max_ps > 0
            and s.observer_clock_id > 0
        ):
            return "INVALID_BANDS"
    elif s.family == FAM_TIMING:
        if s.samples_operand or not s.fixed_public_excitation:
            return "MUTABLE_POLICY"
        if s.slack_min_ps <= 0 or not s.correspondence_qualified:
            return "INVALID_BANDS"
    elif s.family == FAM_OPTICAL:
        if s.occludes_backside:
            return "BACKSIDE_OCCLUSION"
        if not (
            s.photocurrent_trip_na > 0
            and s.dark_current_max_na < s.photocurrent_trip_na
            and 0 < s.site_pitch_um <= s.max_site_pitch_um
        ):
            return "INVALID_BANDS"
    else:
        return "INVALID_ARG"
    return "OK"


def _check_dependencies_oracle(sensors: tuple[_OracleSensor, ...]) -> str:
    by_id = {s.sensor_id: s for s in sensors}
    if len(by_id) != len(sensors):
        return "INVALID_ARG"
    for s in sensors:
        if (
            s.health_observer_id == s.sensor_id
            or s.ref_resource_id == s.resource_id
            or s.uses_only_guarded_liveness
        ):
            return "SELF_OBSERVATION"
        if s.family == FAM_CLOCK and s.is_rot_slow and s.observer_clock_id == s.resource_id:
            return "SELF_OBSERVATION"
        for d in s.deps:
            if d == s.sensor_id:
                return "DEPENDENCY_CYCLE"
            if d not in by_id:
                return "MISSING_DEPENDENCY"
    state: dict[int, int] = {}

    def visit(sid: int) -> bool:
        st = state.get(sid, 0)
        if st == 1:
            return True
        if st == 2:
            return False
        state[sid] = 1
        for d in by_id[sid].deps:
            if visit(d):
                return True
        state[sid] = 2
        return False

    for s in sensors:
        if visit(s.sensor_id):
            return "DEPENDENCY_CYCLE"
    return "OK"


def _validate_topology_oracle(topo: _OracleTopology, sensors: tuple[_OracleSensor, ...]) -> str:
    if not (topo.rails and topo.clocks and topo.datapaths and topo.regions and sensors):
        return "EMPTY_TOPOLOGY"
    if not (topo.has_rot and topo.has_s0 and topo.has_s1):
        return "MISSING_BLOCK"
    classes = {dp.block_class for dp in topo.datapaths}
    if not {"RoT", "S0", "S1"}.issubset(classes):
        return "MISSING_BLOCK"
    for s in sensors:
        st = _validate_sensor_oracle(s)
        if st != "OK":
            return st
    dep_st = _check_dependencies_oracle(sensors)
    if dep_st != "OK":
        return dep_st
    for r in topo.rails:
        if not r.sites:
            return "UNCOVERED_RAIL"
        for site in r.sites:
            if not any(
                s.family == FAM_SUPPLY
                and s.resource_id == r.rail_id
                and s.site_id == site
                and set(r.islands).issubset(s.affected_islands)
                and (not r.reaches_rot or s.rot_self_fault)
                for s in sensors
            ):
                return "UNCOVERED_RAIL"
    for c in topo.clocks:
        if not c.sites:
            return "UNCOVERED_CLOCK"
        for site in c.sites:
            if not any(
                s.family == FAM_CLOCK
                and s.resource_id == c.clock_id
                and s.site_id == site
                and set(c.islands).issubset(s.affected_islands)
                and (not c.reaches_rot or s.rot_self_fault)
                and (not c.is_rot_slow or s.is_rot_slow)
                for s in sensors
            ):
                return "UNCOVERED_CLOCK"
    for d in topo.datapaths:
        if not any(
            s.family == FAM_TIMING
            and s.resource_id == d.dp_id
            and d.island_id in s.affected_islands
            and (not d.reaches_rot or s.rot_self_fault)
            for s in sensors
        ):
            return "UNCOVERED_DATAPATH"
    for lr in topo.regions:
        if lr.occludes_backside:
            return "BACKSIDE_OCCLUSION"
        if not lr.gap_free or lr.declared_pitch_um <= 0:
            return "UNCOVERED_REGION"
        matching = [
            s
            for s in sensors
            if s.family == FAM_OPTICAL
            and s.resource_id == lr.region_id
            and set(lr.islands).issubset(s.affected_islands)
            and (not lr.reaches_rot or s.rot_self_fault)
        ]
        if not matching:
            return "UNCOVERED_REGION"
        if not any(s.site_pitch_um <= lr.declared_pitch_um for s in matching):
            return "PITCH_VIOLATION"
    return "OK"


@dataclass(slots=True)
class _OracleController:
    topo: _OracleTopology
    sensors: tuple[_OracleSensor, ...]
    rot_latch: bool = False
    rot_watchdog_bite: bool = False
    reset_hold: bool = False
    frozen_islands: set[int] = field(default_factory=set)
    last_trip: str = "NONE"
    pending_consume: bool = False
    lost_interval: bool = False
    recurrent_count: int = 0
    events: list[tuple[bool, str, int, bool]] = field(default_factory=list)

    def evaluate_step(self, samples: tuple[_OracleSample, ...]) -> str:
        by_id = {s.sensor_id: s for s in self.sensors}
        tripped = False
        for smp in samples:
            s = by_id[smp.sensor_id]
            tc = "NONE"
            if (
                smp.sensor_disabled
                or smp.corrupt_constants
                or smp.open_or_stuck_line
                or smp.stopped_reference
                or smp.broken_transducer
                or smp.health_timeout
            ):
                tc = "SENSOR_FAULT"
            elif smp.transition_overrun:
                tc = "UNEXPECTED_DEACTIVATION"
            elif smp.physically_inactive:
                if not s.always_on and smp.table_off_authorized and smp.consumer_reset_isolated:
                    tc = "NONE"
                else:
                    tc = "UNEXPECTED_DEACTIVATION"
            elif s.family == FAM_SUPPLY:
                if not (s.vmin_uv <= smp.voltage_uv <= s.vmax_uv):
                    tc = "SUPPLY_EXCURSION"
            elif s.family == FAM_CLOCK:
                if (
                    smp.clock_stopped
                    or not (s.period_min_ps <= smp.period_ps <= s.period_max_ps)
                    or not (s.high_min_ps <= smp.high_ps <= s.high_max_ps)
                    or not (s.low_min_ps <= smp.low_ps <= s.low_max_ps)
                    or smp.edge_gap_ps > s.missing_edge_max_ps
                ):
                    tc = "CLOCK_EXCURSION"
            elif s.family == FAM_TIMING:
                if smp.slack_ps < s.slack_min_ps:
                    tc = "TIMING_MARGIN"
            elif s.family == FAM_OPTICAL and smp.photocurrent_na > s.photocurrent_trip_na:
                tc = "OPTICAL_ILLUMINATION"
            if tc != "NONE":
                tripped = True
                self.rot_latch = True
                self.last_trip = tc
                self.pending_consume = True
                if s.rot_self_fault:
                    self.rot_watchdog_bite = True
                    self.reset_hold = True
                else:
                    self.frozen_islands.update(s.affected_islands)
        if self.rot_watchdog_bite:
            return "ROT_BITE"
        if tripped:
            return "TRIP_LATCHED"
        return "OK"

    def ack_transport(self) -> str:
        if self.rot_watchdog_bite:
            return "ROT_BITE"
        if self.rot_latch:
            return "TRIP_LATCHED"
        return "OK"

    def power_loss(self) -> str:
        self.rot_latch = False
        self.rot_watchdog_bite = False
        self.reset_hold = True
        self.last_trip = "UNKNOWN_RESET_OR_POWER_LOSS"
        self.pending_consume = True
        self.lost_interval = True
        return "RESET_HELD"

    def recover_reset(self, healthy: bool, reset_table_done: bool) -> str:
        if not (healthy and reset_table_done and not self.rot_latch):
            return "RESET_HELD"
        self.reset_hold = False
        self.rot_watchdog_bite = False
        self.frozen_islands.clear()
        return "OK"

    def can_release_island(self, island_id: int) -> bool:
        return not (self.reset_hold or self.rot_watchdog_bite or island_id in self.frozen_islands)

    def firmware_consume(self) -> tuple[bool, str, int, bool] | None:
        if not (self.pending_consume and (self.rot_latch or self.rot_watchdog_bite or self.reset_hold)):
            return None
        known = self.last_trip not in ("NONE", "UNKNOWN_RESET_OR_POWER_LOSS")
        self.recurrent_count += 1
        rec = (known, self.last_trip, self.recurrent_count, self.lost_interval)
        self.events.append(rec)
        self.pending_consume = False
        self.lost_interval = False
        return rec


def _demo_system() -> tuple[_OracleTopology, tuple[_OracleSensor, ...]]:
    all_isl = (0, 1, 2, 3, 4)
    topo = _OracleTopology(
        has_rot=True,
        has_s0=True,
        has_s1=True,
        rails=(
            _OracleRail(10, True, all_isl, (100,)),
            _OracleRail(11, False, (2,), (101,)),
        ),
        clocks=(
            _OracleClock(20, True, True, (0,), (200,)),
            _OracleClock(21, False, True, all_isl, (201,)),
            _OracleClock(22, False, False, (2,), (202,)),
        ),
        datapaths=(
            _OracleDatapath(30, "RoT", 0, True),
            _OracleDatapath(31, "S0", 1, False),
            _OracleDatapath(32, "S1", 1, False),
            _OracleDatapath(33, "C", 2, False),
            _OracleDatapath(34, "V", 3, False),
            _OracleDatapath(35, "M", 4, False),
        ),
        regions=(
            _OracleRegion(40, True, (0,), 60, True, False),
            _OracleRegion(41, False, (1, 2, 3, 4), 60, True, False),
        ),
    )
    sensors = (
        _OracleSensor(1, FAM_SUPPLY, 10, 100, all_isl, True, True, 900, 901),
        _OracleSensor(2, FAM_SUPPLY, 11, 101, (2,), False, False, 900, 1, deps=(1,)),
        _OracleSensor(
            3,
            FAM_CLOCK,
            20,
            200,
            (0,),
            True,
            True,
            902,
            1,
            deps=(1,),
            period_min_ps=9000,
            period_max_ps=11000,
            high_min_ps=4000,
            high_max_ps=6000,
            low_min_ps=4000,
            low_max_ps=6000,
            missing_edge_max_ps=15000,
            observer_clock_id=21,
            is_rot_slow=True,
        ),
        _OracleSensor(4, FAM_CLOCK, 21, 201, all_isl, True, True, 902, 1, deps=(1,), observer_clock_id=20),
        _OracleSensor(5, FAM_CLOCK, 22, 202, (2,), False, False, 902, 4, deps=(4,)),
        _OracleSensor(6, FAM_TIMING, 30, 300, (0,), True, True, 903, 1),
        _OracleSensor(7, FAM_TIMING, 31, 301, (1,), False, False, 903, 1),
        _OracleSensor(8, FAM_TIMING, 32, 302, (1,), False, False, 903, 1),
        _OracleSensor(9, FAM_TIMING, 33, 303, (2,), False, False, 903, 2),
        _OracleSensor(10, FAM_TIMING, 34, 304, (3,), False, False, 903, 1),
        _OracleSensor(11, FAM_TIMING, 35, 305, (4,), False, False, 903, 1),
        _OracleSensor(12, FAM_OPTICAL, 40, 400, (0,), True, True, 904, 1),
        _OracleSensor(13, FAM_OPTICAL, 41, 401, (1, 2, 3, 4), False, True, 904, 1),
    )
    return topo, sensors


def _oracle_env_sensors() -> None:
    """Exercise positive composed topology, in-band controls, and all fail-stop refusal cases."""
    topo, sensors = _demo_system()
    ensure(_validate_topology_oracle(topo, sensors) == "OK", "demo system must validate")

    ctrl = _OracleController(topo, sensors)
    inband = tuple(
        _OracleSample(
            s.sensor_id,
            physically_inactive=(s.sensor_id == 9),
            table_off_authorized=(s.sensor_id == 9),
            consumer_reset_isolated=(s.sensor_id == 9),
            period_ps=(10000 if s.sensor_id == 3 else 1050),
            high_ps=(5000 if s.sensor_id == 3 else 520),
            low_ps=(5000 if s.sensor_id == 3 else 530),
            edge_gap_ps=(10500 if s.sensor_id == 3 else 1100),
            sw_operand_value=0x1234,
        )
        for s in sensors
    )
    ensure(ctrl.evaluate_step(inband) == "OK", "inband + legal table-off failed")
    ensure(ctrl.can_release_island(2), "healthy island release blocked")
    ensure(ctrl.firmware_consume() is None, "firmware consumed without hw stop")

    # Island trip -> persistent latch + freeze + ack refusal + attested class
    isl_ctrl = _OracleController(topo, sensors)
    ensure(isl_ctrl.evaluate_step((_OracleSample(2, voltage_uv=700000),)) == "TRIP_LATCHED",
           "island droop must latch")
    ensure(not isl_ctrl.rot_watchdog_bite and isl_ctrl.rot_latch, "island trip must not bite")
    ensure(isl_ctrl.ack_transport() == "TRIP_LATCHED" and isl_ctrl.rot_latch, "ack cleared latch")
    ensure(not isl_ctrl.can_release_island(2), "frozen island must not release")
    ensure(isl_ctrl.firmware_consume() == (True, "SUPPLY_EXCURSION", 1, False),
           "attested island trip mismatch")

    # RoT slow clock stop -> immediate bite
    rot_ctrl = _OracleController(topo, sensors)
    ensure(rot_ctrl.evaluate_step((_OracleSample(3, clock_stopped=True),)) == "ROT_BITE",
           "rot slow clock stop must bite")
    ensure(rot_ctrl.reset_hold, "rot bite must hold reset")

    # Disabling fault latches rather than disarming
    flt_ctrl = _OracleController(topo, sensors)
    ensure(flt_ctrl.evaluate_step((_OracleSample(13, sensor_disabled=True),)) == "TRIP_LATCHED",
           "disabled sensor must trip")
    ensure(flt_ctrl.last_trip == "SENSOR_FAULT", "disabled sensor wrong trip class")

    # Unexpected deactivation while active trips
    deact_ctrl = _OracleController(topo, sensors)
    ensure(
        deact_ctrl.evaluate_step((_OracleSample(9, physically_inactive=True, table_off_authorized=True),))
        == "TRIP_LATCHED",
        "deactivation without reset isolation must trip",
    )

    # Power loss + reset hold + gated recovery
    pwr_ctrl = _OracleController(topo, sensors)
    ensure(pwr_ctrl.power_loss() == "RESET_HELD" and pwr_ctrl.reset_hold, "power loss must hold reset")
    ensure(pwr_ctrl.recover_reset(True, False) == "RESET_HELD", "recovered before reset table done")
    ensure(not pwr_ctrl.can_release_island(2), "released during reset hold")
    ensure(pwr_ctrl.firmware_consume() == (False, "UNKNOWN_RESET_OR_POWER_LOSS", 1, True),
           "power loss attested event mismatch")
    ensure(pwr_ctrl.recover_reset(True, True) == "OK" and not pwr_ctrl.reset_hold,
           "valid reset recovery failed")

    # Adverse topology/configuration controls
    ensure(_validate_topology_oracle(replace(topo, has_s1=False), sensors) == "MISSING_BLOCK",
           "missing s1 accepted")
    ensure(_validate_topology_oracle(topo, (replace(sensors[0], has_pending=True), *sensors[1:])) == "PENDING_FIELD",
           "pending accepted")
    ensure(_validate_topology_oracle(topo, (replace(sensors[0], sw_writable_threshold=True), *sensors[1:])) == "MUTABLE_POLICY",
           "sw writable threshold accepted")
    ensure(
        _validate_topology_oracle(
            topo,
            (*sensors[:3], replace(sensors[3], duty_min_permille=800, duty_max_permille=900), *sensors[4:]),
        )
        == "INVALID_BANDS",
        "inconsistent duty accepted",
    )
    ensure(
        _validate_topology_oracle(
            topo, (*sensors[:11], replace(sensors[11], occludes_backside=True), sensors[12])
        )
        == "BACKSIDE_OCCLUSION",
        "backside occlusion accepted",
    )
    ensure(
        _validate_topology_oracle(topo, (replace(sensors[0], deps=(2,)), *sensors[1:])) == "DEPENDENCY_CYCLE",
        "dependency cycle accepted",
    )
    ensure(
        _validate_topology_oracle(
            topo, (sensors[0], sensors[1], replace(sensors[2], observer_clock_id=20), *sensors[3:])
        )
        == "SELF_OBSERVATION",
        "rot slow clock self-observation accepted",
    )
    ensure(
        _validate_topology_oracle(topo, (*sensors[:4], replace(sensors[4], site_id=999), *sensors[5:]))
        == "UNCOVERED_CLOCK",
        "uncovered clock leaf accepted",
    )
    ensure(
        _validate_topology_oracle(
            topo, (*sensors[:12], replace(sensors[12], site_pitch_um=65, max_site_pitch_um=70))
        )
        == "PITCH_VIOLATION",
        "pitch violation accepted",
    )


def _surface_and_proof_contract() -> None:
    """Verify SPDX headers, GC-free C17 surface, and EnvironmentalSensors.v proof contract."""
    for path in (ES_H, ES_C, ES_TEST_C, ES_README, PROOFS_V):
        ensure(path.is_file(), f"missing env-sensors artifact: {path}")

    for c_path in (ES_H, ES_C, ES_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        ensure(first_line == "/* SPDX-License-Identifier: Apache-2.0 */",
               f"missing /* SPDX */ header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden heap allocator {forbidden} in {c_path}")

    c_src = ES_C.read_text(encoding="utf-8")
    for fn in (
        "vos_es_validate_sensor",
        "vos_es_check_dependencies",
        "vos_es_validate_topology",
        "vos_es_controller_init",
        "vos_es_evaluate_step",
        "vos_es_acknowledge_transport",
        "vos_es_power_loss",
        "vos_es_recover_reset",
        "vos_es_can_release_island",
        "vos_es_firmware_consume_event",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure("(* SPDX-License-Identifier: Apache-2.0 *)" in v_src.splitlines()[0],
           "missing Rocq SPDX header")
    ensure("Require ProofSupport." in v_src, "EnvironmentalSensors.v must Require ProofSupport.")
    for sym in (
        "self_loop_refused_by_dependency_check",
        "rot_slow_clock_self_observation_refused",
        "empty_or_incomplete_topology_refused",
        "valid_inventory_covers_every_member_and_is_immutable",
        "island_trip_latches_rot_and_freezes_without_sw_or_ack",
        "rot_self_fault_bites_independently_of_cpu_clock_mailbox",
        "disabling_or_corrupt_sensor_latches_failure",
        "unexpected_deactivation_trips_while_authorized_off_requires_reset_isolation",
        "power_loss_holds_reset_until_healthy_and_reset_table_complete",
        "stimulus_independent_of_software_operands",
        "firmware_consume_requires_hw_stop_and_increments_rate",
        "positive_composed_topology_and_boundary_controls",
        "negative_refutations_all_rejected",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in EnvironmentalSensors.v")

    v_clean = strip_comments(v_src)
    for banned in (
        "Admitted", "admit", "Axiom", "Parameter", "Conjecture",
        "CoInductive", "CoFixpoint", "cofix", "Section", "Module Type",
    ):
        ensure(
            re.search(rf"\b{re.escape(banned)}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in EnvironmentalSensors.v",
        )
    for rec in re.findall(r"\bRecord\s+([A-Za-z_][A-Za-z0-9_']*)\b", v_clean):
        ensure(
            re.search(rf"\bDefinition\s+witness_{re.escape(rec)}\s*:\s*{re.escape(rec)}\b", v_clean)
            is not None,
            f"missing closed witness_{rec} in EnvironmentalSensors.v",
        )


def _supports_flags(compiler: str, flags: list[str], scratch: Path) -> bool:
    probe_c = scratch / "_probe.c"
    probe_bin = scratch / "_probe"
    probe_c.write_text("int main(void) { return 0; }\n", encoding="utf-8", newline="\n")
    built = subprocess.run(
        [compiler, *flags, str(probe_c), "-o", str(probe_bin)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if built.returncode != 0:
        return False
    ran = subprocess.run([str(probe_bin)], capture_output=True, text=True, timeout=30, check=False)
    return ran.returncode == 0


def _compile_and_link(compiler: str, flags: list[str], src_c: Path,
                      out_bin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            compiler,
            *flags,
            f"-I{ES_H.parent}",
            str(src_c),
            str(ES_TEST_C),
            "-o",
            str(out_bin),
        ],
        capture_output=True, text=True, timeout=60, check=False,
    )


def _mutants(source: str) -> list[tuple[str, str, str]]:
    def replaced(before: str, after: str, label: str) -> str:
        ensure(source.count(before) == 1, f"mutant anchor missing or non-unique ({label}): {before!r}")
        return source.replace(before, after, 1)

    return [
        (
            "allow-pending-field",
            replaced(
                "    if (sensor->has_pending != 0u) {\n"
                "        return VOS_ES_ERR_PENDING_FIELD;\n"
                "    }",
                "    if (0 && sensor->has_pending != 0u) {\n"
                "        return VOS_ES_ERR_PENDING_FIELD;\n"
                "    }",
                "allow-pending-field",
            ),
            "pending field accepted",
        ),
        (
            "allow-sw-writable-threshold",
            replaced(
                "    if (sensor->enable_constant == 0u || sensor->sw_writable_threshold != 0u ||\n"
                "        sensor->sw_writable_disable != 0u || sensor->dynamic_calibration != 0u ||\n"
                "        sensor->adds_isa_or_csr != 0u) {\n"
                "        return VOS_ES_ERR_MUTABLE_POLICY;\n"
                "    }",
                "    if (sensor->enable_constant == 0u ||\n"
                "        sensor->sw_writable_disable != 0u || sensor->dynamic_calibration != 0u ||\n"
                "        sensor->adds_isa_or_csr != 0u) {\n"
                "        return VOS_ES_ERR_MUTABLE_POLICY;\n"
                "    }",
                "allow-sw-writable-threshold",
            ),
            "sw writable threshold accepted",
        ),
        (
            "allow-inconsistent-clock-duty",
            replaced(
                "    if ((uint64_t)c->duty_min_permille * (uint64_t)c->period_min_ps >\n"
                "            (uint64_t)c->high_max_ps * 1000ULL ||\n"
                "        (uint64_t)c->high_min_ps * 1000ULL >\n"
                "            (uint64_t)c->duty_max_permille * (uint64_t)c->period_max_ps) {\n"
                "        return VOS_ES_ERR_INVALID_BANDS;\n"
                "    }",
                "    if (0 && ((uint64_t)c->duty_min_permille * (uint64_t)c->period_min_ps >\n"
                "              (uint64_t)c->high_max_ps * 1000ULL)) {\n"
                "        return VOS_ES_ERR_INVALID_BANDS;\n"
                "    }",
                "allow-inconsistent-clock-duty",
            ),
            "inconsistent clock duty accepted",
        ),
        (
            "allow-backside-occlusion",
            replaced(
                "    if (o->occludes_backside != 0u) {\n"
                "        return VOS_ES_ERR_BACKSIDE_OCCLUSION;\n"
                "    }",
                "    if (0 && o->occludes_backside != 0u) {\n"
                "        return VOS_ES_ERR_BACKSIDE_OCCLUSION;\n"
                "    }",
                "allow-backside-occlusion",
            ),
            "backside occlusion accepted",
        ),
        (
            "skip-dependency-cycle-check",
            replaced(
                "                if (color[nxt] == 1u) {\n"
                "                    return VOS_ES_ERR_DEPENDENCY_CYCLE;\n"
                "                }",
                "                if (0 && color[nxt] == 1u) {\n"
                "                    return VOS_ES_ERR_DEPENDENCY_CYCLE;\n"
                "                }",
                "skip-dependency-cycle-check",
            ),
            "dependency cycle accepted",
        ),
        (
            "allow-slow-clock-self-observation",
            replaced(
                "        if (s->family == VOS_ES_FAM_CLOCK && s->clock.is_rot_slow_clock != 0u &&\n"
                "            s->clock.observer_clock_id == s->resource_id) {\n"
                "            return VOS_ES_ERR_SELF_OBSERVATION;\n"
                "        }",
                "        if (0 && s->family == VOS_ES_FAM_CLOCK && s->clock.is_rot_slow_clock != 0u &&\n"
                "            s->clock.observer_clock_id == s->resource_id) {\n"
                "            return VOS_ES_ERR_SELF_OBSERVATION;\n"
                "        }",
                "allow-slow-clock-self-observation",
            ),
            "rot slow clock self-observation accepted",
        ),
        (
            "allow-missing-s1-block",
            replaced(
                "    if (topo->has_rot == 0u || topo->has_s0 == 0u || topo->has_s1 == 0u) {\n"
                "        return VOS_ES_ERR_MISSING_BLOCK;\n"
                "    }",
                "    if (topo->has_rot == 0u || topo->has_s0 == 0u) {\n"
                "        return VOS_ES_ERR_MISSING_BLOCK;\n"
                "    }",
                "allow-missing-s1-block",
            ),
            "missing s1 accepted",
        ),
        (
            "allow-uncovered-clock-leaf",
            replaced(
                "            if (!covered) {\n"
                "                return VOS_ES_ERR_UNCOVERED_CLOCK;\n"
                "            }",
                "            if (0 && !covered) {\n"
                "                return VOS_ES_ERR_UNCOVERED_CLOCK;\n"
                "            }",
                "allow-uncovered-clock-leaf",
            ),
            "uncovered clock leaf accepted",
        ),
        (
            "allow-optical-pitch-exceeded",
            replaced(
                "                if (s->optical.site_pitch_um > lr->declared_pitch_um) {\n"
                "                    pitch_bad = 1;\n"
                "                } else {\n"
                "                    covered = 1;\n"
                "                    break;\n"
                "                }",
                "                if (0 && s->optical.site_pitch_um > lr->declared_pitch_um) {\n"
                "                    pitch_bad = 1;\n"
                "                } else {\n"
                "                    covered = 1;\n"
                "                    break;\n"
                "                }",
                "allow-optical-pitch-exceeded",
            ),
            "optical pitch violation accepted",
        ),
        (
            "disarm-on-sensor-fault",
            replaced(
                "    if (smp->sensor_disabled != 0u || smp->corrupt_constants != 0u ||\n"
                "        smp->open_or_stuck_line != 0u || smp->stopped_reference != 0u ||\n"
                "        smp->broken_transducer != 0u || smp->health_timeout != 0u) {\n"
                "        return VOS_ES_TRIP_SENSOR_FAULT;\n"
                "    }",
                "    if (smp->corrupt_constants != 0u ||\n"
                "        smp->open_or_stuck_line != 0u || smp->stopped_reference != 0u ||\n"
                "        smp->broken_transducer != 0u || smp->health_timeout != 0u) {\n"
                "        return VOS_ES_TRIP_SENSOR_FAULT;\n"
                "    }",
                "disarm-on-sensor-fault",
            ),
            "disabled sensor disarmed",
        ),
        (
            "allow-unexpected-deactivation",
            replaced(
                "        if (s->always_on == 0u && smp->table_off_authorized != 0u &&\n"
                "            smp->consumer_reset_isolated != 0u) {\n"
                "            return VOS_ES_TRIP_NONE;\n"
                "        }",
                "        if (s->always_on == 0u && smp->table_off_authorized != 0u) {\n"
                "            return VOS_ES_TRIP_NONE;\n"
                "        }",
                "allow-unexpected-deactivation",
            ),
            "unexpected deactivation accepted",
        ),
        (
            "skip-rot-watchdog-bite",
            replaced(
                "            if (s->rot_self_fault != 0u) {\n"
                "                rot_bite = 1;\n"
                "                ctrl->rot_watchdog_bite = 1u;\n"
                "                ctrl->reset_hold = 1u;\n"
                "            } else {\n"
                "                ctrl->frozen_island_mask |= s->affected_island_mask;\n"
                "            }",
                "            if (0 && s->rot_self_fault != 0u) {\n"
                "                rot_bite = 1;\n"
                "                ctrl->rot_watchdog_bite = 1u;\n"
                "                ctrl->reset_hold = 1u;\n"
                "            } else {\n"
                "                ctrl->frozen_island_mask |= s->affected_island_mask;\n"
                "            }",
                "skip-rot-watchdog-bite",
            ),
            "rot self-fault did not bite",
        ),
        (
            "clear-latch-on-transport-ack",
            replaced(
                "    if (ctrl->rot_latch != 0u) {\n"
                "        return VOS_ES_ERR_TRIP_LATCHED;\n"
                "    }",
                "    ctrl->rot_latch = 0u;\n"
                "    ctrl->frozen_island_mask = 0u;",
                "clear-latch-on-transport-ack",
            ),
            "transport ack cleared latch",
        ),
        (
            "release-before-reset-recovery",
            replaced(
                "    if (boundary_healthy == 0u || reset_table_done == 0u || ctrl->rot_latch != 0u) {\n"
                "        return VOS_ES_ERR_RESET_HELD;\n"
                "    }",
                "    (void)reset_table_done;\n"
                "    if (boundary_healthy == 0u || ctrl->rot_latch != 0u) {\n"
                "        return VOS_ES_ERR_RESET_HELD;\n"
                "    }",
                "release-before-reset-recovery",
            ),
            "release before reset table recovery",
        ),
        (
            "consume-without-hw-stop",
            replaced(
                "    if (ctrl->pending_firmware_consume == 0u || hw_stopped == 0u) {\n"
                "        return VOS_ES_ERR_NO_HW_STOP;\n"
                "    }",
                "    if (0 && (ctrl->pending_firmware_consume == 0u || hw_stopped == 0u)) {\n"
                "        return VOS_ES_ERR_NO_HW_STOP;\n"
                "    }",
                "consume-without-hw-stop",
            ),
            "firmware consumed without hw stop",
        ),
    ]


def _native_c_and_mutation_controls() -> None:
    """Compile and run env-sensors C17 tests under Clang + GCC ASan/UBSan and kill all mutants."""
    if sys.platform == "win32":
        return

    clang = shutil.which("clang")
    gcc = shutil.which("gcc")
    ensure(clang is not None, "clang is required in Linux guest")
    ensure(gcc is not None, "gcc is required in Linux guest")
    if clang is None or gcc is None:
        return

    strict_flags = [
        "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes", "-pedantic",
    ]
    asan_flags = [*strict_flags, "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]

    work = toolenv.environment(ROOT, sys.platform).parent / "c-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="es-", dir=work) as td:
        tmp = Path(td)
        ensure(_supports_flags(gcc, asan_flags, tmp), "gcc ASan/UBSan runtime required")

        # 1. Strict Clang C17 build and run
        clang_bin = tmp / "test_es_clang"
        clang_built = _compile_and_link(clang, strict_flags, ES_C, clang_bin)
        ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
        clang_ran = subprocess.run(
            [str(clang_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(clang_ran.returncode == 0 and "env_sensors_test: ok" in clang_ran.stdout,
               f"clang test run failed: {clang_ran.stderr or clang_ran.stdout}")

        # 2. Strict GCC C17 + ASan/UBSan build and run
        gcc_bin = tmp / "test_es_gcc_san"
        gcc_built = _compile_and_link(gcc, asan_flags, ES_C, gcc_bin)
        ensure(gcc_built.returncode == 0, f"gcc ASan/UBSan build failed: {gcc_built.stderr}")
        gcc_ran = subprocess.run(
            [str(gcc_bin)], capture_output=True, text=True, timeout=60, check=False,
        )
        ensure(gcc_ran.returncode == 0 and "env_sensors_test: ok" in gcc_ran.stdout,
               f"gcc ASan/UBSan test run failed: {gcc_ran.stderr or gcc_ran.stdout}")

        # 3. Behavioral mutation controls under GCC ASan/UBSan
        source = ES_C.read_text(encoding="utf-8")
        mutants = _mutants(source)
        ensure(len(mutants) >= 12, f"expected >= 12 mutants, got {len(mutants)}")
        for label, mutated_source, expected_diag in mutants:
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(mutated_source, encoding="utf-8", newline="\n")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = _compile_and_link(gcc, asan_flags, mutant_c, mutant_bin)
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run(
                [str(mutant_bin)], capture_output=True, text=True, timeout=60, check=False,
            )
            ensure(
                m_ran.returncode != 0 and expected_diag in m_ran.stderr,
                f"mutant survived or missed expected diagnostic ({label}): {m_ran.stderr or m_ran.stdout}",
            )


def cases() -> list[Case]:
    return [
        Case("env_sensors_oracle", _oracle_env_sensors, lane="any"),
        Case("env_sensors_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("env_sensors_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
