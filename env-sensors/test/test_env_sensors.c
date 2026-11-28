// SPDX-License-Identifier: Apache-2.0
#include "vos_env_sensors.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_es_sensor make_base_sensor(uint32_t sid,
                                             uint32_t family,
                                             uint32_t resource_id,
                                             uint32_t site_id,
                                             uint32_t island_mask,
                                             uint32_t rot_self_fault,
                                             uint32_t always_on,
                                             uint32_t ref_res,
                                             uint32_t health_obs)
{
    struct vos_es_sensor s;
    memset(&s, 0, sizeof(s));
    s.sensor_id = sid;
    s.family = family;
    s.resource_id = resource_id;
    s.site_id = site_id;
    s.affected_island_mask = island_mask;
    s.rot_self_fault = rot_self_fault;
    s.always_on = always_on;
    s.enable_constant = 1u;
    s.has_pending = 0u;
    s.has_owner = 1u;
    s.has_evidence_tuple = 1u;
    s.retired_artifact = 0u;
    s.sw_writable_threshold = 0u;
    s.sw_writable_disable = 0u;
    s.dynamic_calibration = 0u;
    s.adds_isa_or_csr = 0u;
    s.opp_table_bound = 1u;
    s.ref_resource_id = ref_res;
    s.health_observer_id = health_obs;
    s.uses_only_guarded_liveness = 0u;

    s.supply.voltage_min_uv = 750000u;
    s.supply.voltage_max_uv = 850000u;
    s.supply.hysteresis_uv = 15000u;

    s.clock.period_min_ps = 900u;
    s.clock.period_max_ps = 1100u;
    s.clock.high_min_ps = 400u;
    s.clock.high_max_ps = 600u;
    s.clock.low_min_ps = 400u;
    s.clock.low_max_ps = 600u;
    s.clock.duty_min_permille = 400u;
    s.clock.duty_max_permille = 600u;
    s.clock.missing_edge_max_ps = 1500u;
    s.clock.observer_clock_id = 21u;
    s.clock.is_rot_slow_clock = 0u;
    s.clock.adaptive_ref = 0u;

    s.timing.slack_min_ps = 120u;
    s.timing.correspondence_qualified = 1u;
    s.timing.fixed_public_excitation = 1u;
    s.timing.samples_operand = 0u;

    s.optical.photocurrent_trip_na = 500u;
    s.optical.dark_current_max_na = 40u;
    s.optical.site_pitch_um = 50u;
    s.optical.max_site_pitch_um = 60u;
    s.optical.occludes_backside = 0u;
    return s;
}

static void build_valid_system(struct vos_es_topology *topo,
                               struct vos_es_inventory *inv)
{
    memset(topo, 0, sizeof(*topo));
    memset(inv, 0, sizeof(*inv));

    const uint32_t all_islands = (1u << 0) | (1u << 1) | (1u << 2) | (1u << 3) | (1u << 4);
    topo->has_rot = 1u;
    topo->has_s0 = 1u;
    topo->has_s1 = 1u;
    topo->active_island_mask = all_islands;

    topo->rail_count = 2u;
    topo->rails[0].rail_id = 10u;
    topo->rails[0].reaches_rot = 1u;
    topo->rails[0].island_mask = all_islands;
    topo->rails[0].site_count = 1u;
    topo->rails[0].site_ids[0] = 100u;

    topo->rails[1].rail_id = 11u;
    topo->rails[1].parent_rail_id = 10u;
    topo->rails[1].is_leaf = 1u;
    topo->rails[1].reaches_rot = 0u;
    topo->rails[1].island_mask = (1u << 2);
    topo->rails[1].site_count = 1u;
    topo->rails[1].site_ids[0] = 101u;

    topo->clock_count = 3u;
    topo->clocks[0].clock_id = 20u;
    topo->clocks[0].is_rot_slow_clock = 1u;
    topo->clocks[0].reaches_rot = 1u;
    topo->clocks[0].island_mask = (1u << 0);
    topo->clocks[0].site_count = 1u;
    topo->clocks[0].site_ids[0] = 200u;

    topo->clocks[1].clock_id = 21u;
    topo->clocks[1].reaches_rot = 1u;
    topo->clocks[1].island_mask = all_islands;
    topo->clocks[1].site_count = 1u;
    topo->clocks[1].site_ids[0] = 201u;

    topo->clocks[2].clock_id = 22u;
    topo->clocks[2].parent_clock_id = 21u;
    topo->clocks[2].is_leaf = 1u;
    topo->clocks[2].reaches_rot = 0u;
    topo->clocks[2].island_mask = (1u << 2);
    topo->clocks[2].site_count = 1u;
    topo->clocks[2].site_ids[0] = 202u;

    topo->datapath_count = 6u;
    topo->datapaths[0] = (struct vos_es_datapath_spec){ 30u, VOS_ES_BLK_ROT, 0u, 1u };
    topo->datapaths[1] = (struct vos_es_datapath_spec){ 31u, VOS_ES_BLK_S0, 1u, 0u };
    topo->datapaths[2] = (struct vos_es_datapath_spec){ 32u, VOS_ES_BLK_S1, 1u, 0u };
    topo->datapaths[3] = (struct vos_es_datapath_spec){ 33u, VOS_ES_BLK_CORE_C, 2u, 0u };
    topo->datapaths[4] = (struct vos_es_datapath_spec){ 34u, VOS_ES_BLK_CORE_V, 3u, 0u };
    topo->datapaths[5] = (struct vos_es_datapath_spec){ 35u, VOS_ES_BLK_CORE_M, 4u, 0u };

    topo->region_count = 2u;
    topo->regions[0] = (struct vos_es_region_spec){ 40u, 1u, (1u << 0), 60u, 1u, 0u };
    topo->regions[1] = (struct vos_es_region_spec){
        41u, 0u, (1u << 1) | (1u << 2) | (1u << 3) | (1u << 4), 60u, 1u, 0u
    };

    inv->sensor_count = 13u;
    inv->sensors[0] = make_base_sensor(1u, VOS_ES_FAM_SUPPLY, 10u, 100u, all_islands, 1u, 1u, 900u, 901u);
    inv->sensors[1] = make_base_sensor(2u, VOS_ES_FAM_SUPPLY, 11u, 101u, (1u << 2), 0u, 0u, 900u, 1u);
    inv->sensors[1].dep_count = 1u;
    inv->sensors[1].dep_sensor_ids[0] = 1u;

    inv->sensors[2] = make_base_sensor(3u, VOS_ES_FAM_CLOCK, 20u, 200u, (1u << 0), 1u, 1u, 902u, 1u);
    inv->sensors[2].clock.period_min_ps = 9000u;
    inv->sensors[2].clock.period_max_ps = 11000u;
    inv->sensors[2].clock.high_min_ps = 4000u;
    inv->sensors[2].clock.high_max_ps = 6000u;
    inv->sensors[2].clock.low_min_ps = 4000u;
    inv->sensors[2].clock.low_max_ps = 6000u;
    inv->sensors[2].clock.missing_edge_max_ps = 15000u;
    inv->sensors[2].clock.is_rot_slow_clock = 1u;
    inv->sensors[2].clock.observer_clock_id = 21u;
    inv->sensors[2].dep_count = 1u;
    inv->sensors[2].dep_sensor_ids[0] = 1u;

    inv->sensors[3] = make_base_sensor(4u, VOS_ES_FAM_CLOCK, 21u, 201u, all_islands, 1u, 1u, 902u, 1u);
    inv->sensors[3].clock.observer_clock_id = 20u;
    inv->sensors[3].dep_count = 1u;
    inv->sensors[3].dep_sensor_ids[0] = 1u;

    inv->sensors[4] = make_base_sensor(5u, VOS_ES_FAM_CLOCK, 22u, 202u, (1u << 2), 0u, 0u, 902u, 4u);
    inv->sensors[4].dep_count = 1u;
    inv->sensors[4].dep_sensor_ids[0] = 4u;

    inv->sensors[5] = make_base_sensor(6u, VOS_ES_FAM_TIMING, 30u, 300u, (1u << 0), 1u, 1u, 903u, 1u);
    inv->sensors[6] = make_base_sensor(7u, VOS_ES_FAM_TIMING, 31u, 301u, (1u << 1), 0u, 0u, 903u, 1u);
    inv->sensors[7] = make_base_sensor(8u, VOS_ES_FAM_TIMING, 32u, 302u, (1u << 1), 0u, 0u, 903u, 1u);
    inv->sensors[8] = make_base_sensor(9u, VOS_ES_FAM_TIMING, 33u, 303u, (1u << 2), 0u, 0u, 903u, 2u);
    inv->sensors[9] = make_base_sensor(10u, VOS_ES_FAM_TIMING, 34u, 304u, (1u << 3), 0u, 0u, 903u, 1u);
    inv->sensors[10] = make_base_sensor(11u, VOS_ES_FAM_TIMING, 35u, 305u, (1u << 4), 0u, 0u, 903u, 1u);

    inv->sensors[11] = make_base_sensor(12u, VOS_ES_FAM_OPTICAL, 40u, 400u, (1u << 0), 1u, 1u, 904u, 1u);
    inv->sensors[12] = make_base_sensor(
        13u, VOS_ES_FAM_OPTICAL, 41u, 401u, (1u << 1) | (1u << 2) | (1u << 3) | (1u << 4), 0u, 1u, 904u, 1u);
}

static struct vos_es_sample make_inband_sample(uint32_t sid)
{
    struct vos_es_sample smp;
    memset(&smp, 0, sizeof(smp));
    smp.sensor_id = sid;
    smp.voltage_uv = 760000u;
    if (sid == 3u) {
        smp.period_ps = 10000u;
        smp.high_ps = 5000u;
        smp.low_ps = 5000u;
        smp.edge_gap_ps = 10500u;
    } else {
        smp.period_ps = 1050u;
        smp.high_ps = 520u;
        smp.low_ps = 530u;
        smp.edge_gap_ps = 1100u;
    }
    smp.slack_ps = 130u;
    smp.photocurrent_na = 420u;
    smp.sw_operand_value = 0x12345678ULL;
    return smp;
}

int main(void)
{
    struct vos_es_topology topo;
    struct vos_es_inventory inv;
    build_valid_system(&topo, &inv);

    /* 1. Positive topology validation and controller initialization. */
    CHECK(vos_es_validate_topology(&topo, &inv) == VOS_ES_OK, "valid topology rejected");
    struct vos_es_controller ctrl;
    CHECK(vos_es_controller_init(&ctrl, &topo, &inv) == VOS_ES_OK, "controller init failed");

    /* 2. Negative in-band controls + operand independence + legal table-off state. */
    struct vos_es_sample samples[13];
    for (uint32_t i = 0u; i < 13u; ++i) {
        samples[i] = make_inband_sample(inv.sensors[i].sensor_id);
    }
    samples[8].physically_inactive = 1u;
    samples[8].table_off_authorized = 1u;
    samples[8].consumer_reset_isolated = 1u;

    const struct vos_es_env_context live_env = { 1u, 1u, 1u, 0u, 0u };
    CHECK(vos_es_evaluate_step(&ctrl, samples, 13u, &live_env) == VOS_ES_OK,
          "inband and legal table-off tripped");

    samples[1].sw_operand_value = 0xCAFEBABEULL;
    CHECK(vos_es_evaluate_step(&ctrl, samples, 13u, &live_env) == VOS_ES_OK,
          "operand change caused false trip");
    CHECK(vos_es_can_release_island(&ctrl, 2u, 1u, 1u, 1u) == VOS_ES_OK,
          "healthy island release blocked");

    /* 3. Island-only supply excursion: RoT latch + freeze + ack refusal + firmware record. */
    struct vos_es_controller island_ctrl = ctrl;
    struct vos_es_sample droop = make_inband_sample(2u);
    droop.voltage_uv = 700000u;
    const struct vos_es_env_context masked_env = { 1u, 1u, 1u, 1u, 1u };
    CHECK(vos_es_evaluate_step(&island_ctrl, &droop, 1u, &masked_env) == VOS_ES_ERR_TRIP_LATCHED,
          "island supply droop did not latch");
    CHECK(island_ctrl.rot_latch == 1u && island_ctrl.rot_watchdog_bite == 0u,
          "island trip wrong latch/bite");
    CHECK(vos_es_acknowledge_transport(&island_ctrl, (1u << 2)) == VOS_ES_ERR_TRIP_LATCHED &&
              island_ctrl.rot_latch == 1u,
          "transport ack cleared latch");
    CHECK(vos_es_can_release_island(&island_ctrl, 2u, 1u, 1u, 1u) == VOS_ES_ERR_TRIP_LATCHED,
          "frozen island released");

    struct vos_es_attested_event ev;
    CHECK(vos_es_firmware_consume_event(&ctrl, &ev) == VOS_ES_ERR_NO_HW_STOP,
          "firmware consumed without hw stop");
    CHECK(vos_es_firmware_consume_event(&island_ctrl, &ev) == VOS_ES_OK &&
              ev.known_trip == 1u &&
              ev.trip_class == VOS_ES_TRIP_SUPPLY_EXCURSION &&
              ev.recurrent_count == 1u,
          "attested island event mismatch");

    /* 4. RoT self-fault with dead CPU, dead main clock, and dead mailbox -> immediate bite. */
    struct vos_es_controller rot_ctrl = ctrl;
    struct vos_es_sample slow_stop = make_inband_sample(3u);
    slow_stop.clock_stopped = 1u;
    const struct vos_es_env_context dead_env = { 0u, 0u, 0u, 1u, 1u };
    CHECK(vos_es_evaluate_step(&rot_ctrl, &slow_stop, 1u, &dead_env) == VOS_ES_ERR_ROT_BITE &&
              rot_ctrl.rot_watchdog_bite == 1u && rot_ctrl.reset_hold == 1u,
          "rot self-fault did not bite");

    /* 5. Disabling sensor fault latches failure rather than disarming. */
    struct vos_es_controller fault_ctrl = ctrl;
    struct vos_es_sample dis = make_inband_sample(13u);
    dis.sensor_disabled = 1u;
    CHECK(vos_es_evaluate_step(&fault_ctrl, &dis, 1u, &live_env) == VOS_ES_ERR_TRIP_LATCHED &&
              fault_ctrl.last_trip_class == VOS_ES_TRIP_SENSOR_FAULT,
          "disabled sensor disarmed");

    /* 6. Unexpected deactivation while consumer is active trips. */
    struct vos_es_controller deact_ctrl = ctrl;
    struct vos_es_sample bad_off = make_inband_sample(9u);
    bad_off.physically_inactive = 1u;
    bad_off.table_off_authorized = 1u;
    bad_off.consumer_reset_isolated = 0u;
    CHECK(vos_es_evaluate_step(&deact_ctrl, &bad_off, 1u, &live_env) == VOS_ES_ERR_TRIP_LATCHED &&
              deact_ctrl.last_trip_class == VOS_ES_TRIP_UNEXPECTED_DEACTIVATION,
          "unexpected deactivation accepted");

    /* 7. Power loss holds reset until boundary healthy AND reset table recovery complete. */
    struct vos_es_controller pwr_ctrl = ctrl;
    CHECK(vos_es_power_loss(&pwr_ctrl) == VOS_ES_ERR_RESET_HELD && pwr_ctrl.reset_hold == 1u,
          "power loss did not hold reset");
    CHECK(vos_es_recover_reset(&pwr_ctrl, 1u, 0u) == VOS_ES_ERR_RESET_HELD,
          "release before reset table recovery");
    CHECK(vos_es_can_release_island(&pwr_ctrl, 2u, 1u, 1u, 1u) == VOS_ES_ERR_RESET_HELD,
          "island released during reset hold");
    CHECK(vos_es_firmware_consume_event(&pwr_ctrl, &ev) == VOS_ES_OK &&
              ev.known_trip == 0u &&
              ev.trip_class == VOS_ES_TRIP_UNKNOWN_RESET_OR_POWER_LOSS &&
              ev.lost_accounting_interval == 1u,
          "power loss event mismatch");
    CHECK(vos_es_recover_reset(&pwr_ctrl, 1u, 1u) == VOS_ES_OK && pwr_ctrl.reset_hold == 0u,
          "valid recovery failed");

    /* 8. Negative validation controls. */
    struct vos_es_inventory inv_pend = inv;
    inv_pend.sensors[0].has_pending = 1u;
    CHECK(vos_es_validate_topology(&topo, &inv_pend) == VOS_ES_ERR_PENDING_FIELD,
          "pending field accepted");

    struct vos_es_inventory inv_sw = inv;
    inv_sw.sensors[0].sw_writable_threshold = 1u;
    CHECK(vos_es_validate_topology(&topo, &inv_sw) == VOS_ES_ERR_MUTABLE_POLICY,
          "sw writable threshold accepted");

    struct vos_es_inventory inv_duty = inv;
    inv_duty.sensors[3].clock.duty_min_permille = 800u;
    inv_duty.sensors[3].clock.duty_max_permille = 900u;
    CHECK(vos_es_validate_topology(&topo, &inv_duty) == VOS_ES_ERR_INVALID_BANDS,
          "inconsistent clock duty accepted");

    struct vos_es_inventory inv_occ = inv;
    inv_occ.sensors[11].optical.occludes_backside = 1u;
    CHECK(vos_es_validate_topology(&topo, &inv_occ) == VOS_ES_ERR_BACKSIDE_OCCLUSION,
          "backside occlusion accepted");

    struct vos_es_inventory inv_cyc = inv;
    inv_cyc.sensors[0].dep_count = 1u;
    inv_cyc.sensors[0].dep_sensor_ids[0] = 2u;
    CHECK(vos_es_validate_topology(&topo, &inv_cyc) == VOS_ES_ERR_DEPENDENCY_CYCLE,
          "dependency cycle accepted");

    struct vos_es_inventory inv_self = inv;
    inv_self.sensors[2].clock.observer_clock_id = 20u;
    CHECK(vos_es_validate_topology(&topo, &inv_self) == VOS_ES_ERR_SELF_OBSERVATION,
          "rot slow clock self-observation accepted");

    struct vos_es_topology topo_nos1 = topo;
    topo_nos1.has_s1 = 0u;
    CHECK(vos_es_validate_topology(&topo_nos1, &inv) == VOS_ES_ERR_MISSING_BLOCK,
          "missing s1 accepted");

    struct vos_es_inventory inv_nocov = inv;
    inv_nocov.sensors[4].site_id = 999u;
    CHECK(vos_es_validate_topology(&topo, &inv_nocov) == VOS_ES_ERR_UNCOVERED_CLOCK,
          "uncovered clock leaf accepted");

    struct vos_es_inventory inv_pitch = inv;
    inv_pitch.sensors[12].optical.site_pitch_um = 65u;
    inv_pitch.sensors[12].optical.max_site_pitch_um = 70u;
    CHECK(vos_es_validate_topology(&topo, &inv_pitch) == VOS_ES_ERR_PITCH_VIOLATION,
          "optical pitch violation accepted");

    puts("env_sensors_test: ok");
    return 0;
}
