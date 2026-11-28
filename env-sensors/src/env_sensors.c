/* SPDX-License-Identifier: Apache-2.0 */
#include "vos_env_sensors.h"

#include <stddef.h>
#include <string.h>

static int find_sensor_index(const struct vos_es_inventory *inv, uint32_t sensor_id,
                             uint32_t *out_idx)
{
    for (uint32_t i = 0u; i < inv->sensor_count; ++i) {
        if (inv->sensors[i].sensor_id == sensor_id) {
            if (out_idx != NULL) {
                *out_idx = i;
            }
            return 1;
        }
    }
    return 0;
}

static enum vos_es_status validate_supply_cfg(const struct vos_es_supply_cfg *s)
{
    if (s->voltage_min_uv == 0u || s->voltage_min_uv >= s->voltage_max_uv ||
        s->hysteresis_uv == 0u ||
        s->hysteresis_uv >= (s->voltage_max_uv - s->voltage_min_uv)) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    return VOS_ES_OK;
}

static enum vos_es_status validate_clock_cfg(const struct vos_es_clock_cfg *c)
{
    if (c->adaptive_ref != 0u) {
        return VOS_ES_ERR_MUTABLE_POLICY;
    }
    if (c->period_min_ps == 0u || c->period_min_ps > c->period_max_ps ||
        c->high_min_ps == 0u || c->high_min_ps > c->high_max_ps ||
        c->low_min_ps == 0u || c->low_min_ps > c->low_max_ps ||
        c->high_max_ps >= c->period_max_ps || c->low_max_ps >= c->period_max_ps ||
        c->missing_edge_max_ps == 0u || c->observer_clock_id == 0u) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    if ((uint64_t)c->high_min_ps + (uint64_t)c->low_min_ps > (uint64_t)c->period_max_ps ||
        (uint64_t)c->period_min_ps > (uint64_t)c->high_max_ps + (uint64_t)c->low_max_ps) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    if (c->duty_min_permille == 0u || c->duty_min_permille > c->duty_max_permille ||
        c->duty_max_permille >= 1000u) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    if ((uint64_t)c->duty_min_permille * (uint64_t)c->period_min_ps >
            (uint64_t)c->high_max_ps * 1000ULL ||
        (uint64_t)c->high_min_ps * 1000ULL >
            (uint64_t)c->duty_max_permille * (uint64_t)c->period_max_ps) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    return VOS_ES_OK;
}

static enum vos_es_status validate_timing_cfg(const struct vos_es_timing_cfg *t)
{
    if (t->samples_operand != 0u || t->fixed_public_excitation == 0u) {
        return VOS_ES_ERR_MUTABLE_POLICY;
    }
    if (t->slack_min_ps == 0u || t->correspondence_qualified == 0u) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    return VOS_ES_OK;
}

static enum vos_es_status validate_optical_cfg(const struct vos_es_optical_cfg *o)
{
    if (o->occludes_backside != 0u) {
        return VOS_ES_ERR_BACKSIDE_OCCLUSION;
    }
    if (o->photocurrent_trip_na == 0u ||
        o->dark_current_max_na >= o->photocurrent_trip_na ||
        o->site_pitch_um == 0u ||
        o->site_pitch_um > o->max_site_pitch_um) {
        return VOS_ES_ERR_INVALID_BANDS;
    }
    return VOS_ES_OK;
}

enum vos_es_status vos_es_validate_sensor(const struct vos_es_sensor *sensor)
{
    if (sensor == NULL || sensor->sensor_id == 0u || sensor->resource_id == 0u ||
        sensor->dep_count > VOS_ES_MAX_DEPS) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    if (sensor->has_pending != 0u) {
        return VOS_ES_ERR_PENDING_FIELD;
    }
    if (sensor->has_owner == 0u || sensor->has_evidence_tuple == 0u ||
        sensor->retired_artifact != 0u || sensor->opp_table_bound == 0u) {
        return VOS_ES_ERR_RETIRED_OR_UNBOUND;
    }
    if (sensor->enable_constant == 0u || sensor->sw_writable_threshold != 0u ||
        sensor->sw_writable_disable != 0u || sensor->dynamic_calibration != 0u ||
        sensor->adds_isa_or_csr != 0u) {
        return VOS_ES_ERR_MUTABLE_POLICY;
    }

    switch (sensor->family) {
    case VOS_ES_FAM_SUPPLY:
        return validate_supply_cfg(&sensor->supply);
    case VOS_ES_FAM_CLOCK:
        return validate_clock_cfg(&sensor->clock);
    case VOS_ES_FAM_TIMING:
        return validate_timing_cfg(&sensor->timing);
    case VOS_ES_FAM_OPTICAL:
        return validate_optical_cfg(&sensor->optical);
    default:
        return VOS_ES_ERR_INVALID_ARG;
    }
}

enum vos_es_status vos_es_check_dependencies(const struct vos_es_inventory *inv)
{
    if (inv == NULL || inv->sensor_count == 0u || inv->sensor_count > VOS_ES_MAX_SENSORS) {
        return VOS_ES_ERR_INVALID_ARG;
    }

    for (uint32_t i = 0u; i < inv->sensor_count; ++i) {
        const struct vos_es_sensor *s = &inv->sensors[i];
        if (s->dep_count > VOS_ES_MAX_DEPS) {
            return VOS_ES_ERR_INVALID_ARG;
        }
        for (uint32_t j = i + 1u; j < inv->sensor_count; ++j) {
            if (inv->sensors[j].sensor_id == s->sensor_id) {
                return VOS_ES_ERR_INVALID_ARG;
            }
        }
        if (s->health_observer_id == s->sensor_id ||
            s->ref_resource_id == s->resource_id ||
            s->uses_only_guarded_liveness != 0u) {
            return VOS_ES_ERR_SELF_OBSERVATION;
        }
        if (s->family == VOS_ES_FAM_CLOCK && s->clock.is_rot_slow_clock != 0u &&
            s->clock.observer_clock_id == s->resource_id) {
            return VOS_ES_ERR_SELF_OBSERVATION;
        }
        for (uint32_t d = 0u; d < s->dep_count; ++d) {
            if (s->dep_sensor_ids[d] == s->sensor_id) {
                return VOS_ES_ERR_DEPENDENCY_CYCLE;
            }
            if (!find_sensor_index(inv, s->dep_sensor_ids[d], NULL)) {
                return VOS_ES_ERR_MISSING_DEPENDENCY;
            }
        }
    }

    /* Bounded iterative 3-color DFS (0 = unvisited, 1 = active, 2 = done). */
    uint8_t color[VOS_ES_MAX_SENSORS];
    uint32_t stack_idx[VOS_ES_MAX_SENSORS];
    uint32_t stack_edge[VOS_ES_MAX_SENSORS];
    memset(color, 0, sizeof(color));

    for (uint32_t start = 0u; start < inv->sensor_count; ++start) {
        if (color[start] != 0u) {
            continue;
        }
        uint32_t sp = 0u;
        color[start] = 1u;
        stack_idx[sp] = start;
        stack_edge[sp] = 0u;
        ++sp;

        while (sp > 0u) {
            const uint32_t cur = stack_idx[sp - 1u];
            const uint32_t edge = stack_edge[sp - 1u];
            const struct vos_es_sensor *cs = &inv->sensors[cur];
            if (edge < cs->dep_count) {
                stack_edge[sp - 1u] = edge + 1u;
                uint32_t nxt = 0u;
                (void)find_sensor_index(inv, cs->dep_sensor_ids[edge], &nxt);
                if (color[nxt] == 1u) {
                    return VOS_ES_ERR_DEPENDENCY_CYCLE;
                }
                if (color[nxt] == 0u) {
                    color[nxt] = 1u;
                    stack_idx[sp] = nxt;
                    stack_edge[sp] = 0u;
                    ++sp;
                }
            } else {
                color[cur] = 2u;
                --sp;
            }
        }
    }

    return VOS_ES_OK;
}

static int sensor_covers_rail_site(const struct vos_es_sensor *s,
                                   const struct vos_es_rail_spec *r,
                                   uint32_t site_id)
{
    return s->family == VOS_ES_FAM_SUPPLY &&
           s->resource_id == r->rail_id &&
           s->site_id == site_id &&
           (s->affected_island_mask & r->island_mask) == r->island_mask &&
           (r->reaches_rot == 0u || s->rot_self_fault != 0u);
}

static int sensor_covers_clock_site(const struct vos_es_sensor *s,
                                    const struct vos_es_clock_spec *c,
                                    uint32_t site_id)
{
    return s->family == VOS_ES_FAM_CLOCK &&
           s->resource_id == c->clock_id &&
           s->site_id == site_id &&
           (s->affected_island_mask & c->island_mask) == c->island_mask &&
           (c->reaches_rot == 0u || s->rot_self_fault != 0u) &&
           (c->is_rot_slow_clock == 0u || s->clock.is_rot_slow_clock != 0u);
}

static int sensor_covers_datapath(const struct vos_es_sensor *s,
                                  const struct vos_es_datapath_spec *d)
{
    const uint32_t bit = (d->island_id < VOS_ES_MAX_ISLANDS) ? (1u << d->island_id) : 0u;
    return s->family == VOS_ES_FAM_TIMING &&
           s->resource_id == d->datapath_id &&
           bit != 0u &&
           (s->affected_island_mask & bit) == bit &&
           (d->reaches_rot == 0u || s->rot_self_fault != 0u);
}

enum vos_es_status vos_es_validate_topology(const struct vos_es_topology *topo,
                                            const struct vos_es_inventory *inv)
{
    if (topo == NULL || inv == NULL) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    if (topo->rail_count == 0u || topo->rail_count > VOS_ES_MAX_RAILS ||
        topo->clock_count == 0u || topo->clock_count > VOS_ES_MAX_CLOCKS ||
        topo->datapath_count == 0u || topo->datapath_count > VOS_ES_MAX_DATAPATHS ||
        topo->region_count == 0u || topo->region_count > VOS_ES_MAX_REGIONS ||
        inv->sensor_count == 0u || inv->sensor_count > VOS_ES_MAX_SENSORS) {
        return VOS_ES_ERR_EMPTY_TOPOLOGY;
    }
    if (topo->has_rot == 0u || topo->has_s0 == 0u || topo->has_s1 == 0u) {
        return VOS_ES_ERR_MISSING_BLOCK;
    }

    uint32_t has_dp_rot = 0u;
    uint32_t has_dp_s0 = 0u;
    uint32_t has_dp_s1 = 0u;
    for (uint32_t i = 0u; i < topo->datapath_count; ++i) {
        if (topo->datapaths[i].block_class == VOS_ES_BLK_ROT) {
            has_dp_rot = 1u;
        } else if (topo->datapaths[i].block_class == VOS_ES_BLK_S0) {
            has_dp_s0 = 1u;
        } else if (topo->datapaths[i].block_class == VOS_ES_BLK_S1) {
            has_dp_s1 = 1u;
        }
    }
    if (has_dp_rot == 0u || has_dp_s0 == 0u || has_dp_s1 == 0u) {
        return VOS_ES_ERR_MISSING_BLOCK;
    }

    for (uint32_t i = 0u; i < inv->sensor_count; ++i) {
        const enum vos_es_status st = vos_es_validate_sensor(&inv->sensors[i]);
        if (st != VOS_ES_OK) {
            return st;
        }
    }

    const enum vos_es_status dep_st = vos_es_check_dependencies(inv);
    if (dep_st != VOS_ES_OK) {
        return dep_st;
    }

    for (uint32_t r = 0u; r < topo->rail_count; ++r) {
        const struct vos_es_rail_spec *rail = &topo->rails[r];
        if (rail->site_count == 0u || rail->site_count > VOS_ES_MAX_SITES_PER_NODE) {
            return VOS_ES_ERR_UNCOVERED_RAIL;
        }
        for (uint32_t si = 0u; si < rail->site_count; ++si) {
            int covered = 0;
            for (uint32_t k = 0u; k < inv->sensor_count; ++k) {
                if (sensor_covers_rail_site(&inv->sensors[k], rail, rail->site_ids[si])) {
                    covered = 1;
                    break;
                }
            }
            if (!covered) {
                return VOS_ES_ERR_UNCOVERED_RAIL;
            }
        }
    }

    for (uint32_t c = 0u; c < topo->clock_count; ++c) {
        const struct vos_es_clock_spec *clk = &topo->clocks[c];
        if (clk->site_count == 0u || clk->site_count > VOS_ES_MAX_SITES_PER_NODE) {
            return VOS_ES_ERR_UNCOVERED_CLOCK;
        }
        for (uint32_t si = 0u; si < clk->site_count; ++si) {
            int covered = 0;
            for (uint32_t k = 0u; k < inv->sensor_count; ++k) {
                if (sensor_covers_clock_site(&inv->sensors[k], clk, clk->site_ids[si])) {
                    covered = 1;
                    break;
                }
            }
            if (!covered) {
                return VOS_ES_ERR_UNCOVERED_CLOCK;
            }
        }
    }

    for (uint32_t d = 0u; d < topo->datapath_count; ++d) {
        const struct vos_es_datapath_spec *dp = &topo->datapaths[d];
        int covered = 0;
        for (uint32_t k = 0u; k < inv->sensor_count; ++k) {
            if (sensor_covers_datapath(&inv->sensors[k], dp)) {
                covered = 1;
                break;
            }
        }
        if (!covered) {
            return VOS_ES_ERR_UNCOVERED_DATAPATH;
        }
    }

    for (uint32_t reg = 0u; reg < topo->region_count; ++reg) {
        const struct vos_es_region_spec *lr = &topo->regions[reg];
        if (lr->occludes_backside != 0u) {
            return VOS_ES_ERR_BACKSIDE_OCCLUSION;
        }
        if (lr->gap_free == 0u || lr->declared_pitch_um == 0u) {
            return VOS_ES_ERR_UNCOVERED_REGION;
        }
        int covered = 0;
        int pitch_bad = 0;
        for (uint32_t k = 0u; k < inv->sensor_count; ++k) {
            const struct vos_es_sensor *s = &inv->sensors[k];
            if (s->family == VOS_ES_FAM_OPTICAL && s->resource_id == lr->region_id &&
                (s->affected_island_mask & lr->island_mask) == lr->island_mask &&
                (lr->reaches_rot == 0u || s->rot_self_fault != 0u)) {
                if (s->optical.site_pitch_um > lr->declared_pitch_um) {
                    pitch_bad = 1;
                } else {
                    covered = 1;
                    break;
                }
            }
        }
        if (!covered) {
            return pitch_bad ? VOS_ES_ERR_PITCH_VIOLATION : VOS_ES_ERR_UNCOVERED_REGION;
        }
    }

    return VOS_ES_OK;
}

enum vos_es_status vos_es_controller_init(struct vos_es_controller *ctrl,
                                          const struct vos_es_topology *topo,
                                          const struct vos_es_inventory *inv)
{
    if (ctrl == NULL) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    memset(ctrl, 0, sizeof(*ctrl));
    const enum vos_es_status st = vos_es_validate_topology(topo, inv);
    if (st != VOS_ES_OK) {
        return st;
    }
    ctrl->inventory_valid = 1u;
    ctrl->inventory = *inv;
    return VOS_ES_OK;
}

static enum vos_es_trip_class evaluate_one_sample(const struct vos_es_sensor *s,
                                                  const struct vos_es_sample *smp)
{
    (void)smp->sw_operand_value;
    if (smp->sensor_disabled != 0u || smp->corrupt_constants != 0u ||
        smp->open_or_stuck_line != 0u || smp->stopped_reference != 0u ||
        smp->broken_transducer != 0u || smp->health_timeout != 0u) {
        return VOS_ES_TRIP_SENSOR_FAULT;
    }
    if (smp->transition_overrun != 0u) {
        return VOS_ES_TRIP_UNEXPECTED_DEACTIVATION;
    }
    if (smp->physically_inactive != 0u) {
        if (s->always_on == 0u && smp->table_off_authorized != 0u &&
            smp->consumer_reset_isolated != 0u) {
            return VOS_ES_TRIP_NONE;
        }
        return VOS_ES_TRIP_UNEXPECTED_DEACTIVATION;
    }

    switch (s->family) {
    case VOS_ES_FAM_SUPPLY:
        if (smp->voltage_uv < s->supply.voltage_min_uv ||
            smp->voltage_uv > s->supply.voltage_max_uv) {
            return VOS_ES_TRIP_SUPPLY_EXCURSION;
        }
        return VOS_ES_TRIP_NONE;
    case VOS_ES_FAM_CLOCK:
        if (smp->clock_stopped != 0u ||
            smp->period_ps < s->clock.period_min_ps ||
            smp->period_ps > s->clock.period_max_ps ||
            smp->high_ps < s->clock.high_min_ps ||
            smp->high_ps > s->clock.high_max_ps ||
            smp->low_ps < s->clock.low_min_ps ||
            smp->low_ps > s->clock.low_max_ps ||
            smp->edge_gap_ps > s->clock.missing_edge_max_ps) {
            return VOS_ES_TRIP_CLOCK_EXCURSION;
        }
        return VOS_ES_TRIP_NONE;
    case VOS_ES_FAM_TIMING:
        if (smp->slack_ps < s->timing.slack_min_ps) {
            return VOS_ES_TRIP_TIMING_MARGIN;
        }
        return VOS_ES_TRIP_NONE;
    case VOS_ES_FAM_OPTICAL:
        if (smp->photocurrent_na > s->optical.photocurrent_trip_na) {
            return VOS_ES_TRIP_OPTICAL_ILLUMINATION;
        }
        return VOS_ES_TRIP_NONE;
    default:
        return VOS_ES_TRIP_SENSOR_FAULT;
    }
}

enum vos_es_status vos_es_evaluate_step(struct vos_es_controller *ctrl,
                                        const struct vos_es_sample *samples,
                                        uint32_t sample_count,
                                        const struct vos_es_env_context *env)
{
    if (ctrl == NULL || ctrl->inventory_valid == 0u || samples == NULL ||
        sample_count == 0u || env == NULL) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    /* Hardware fail-stop boundary ignores sw_mask_requested, rot_cpu_alive,
       main_spine_clock_alive, firmware_mailbox_ready, and transport_ack_requested. */
    (void)env;

    int tripped = 0;
    int rot_bite = 0;

    for (uint32_t i = 0u; i < sample_count; ++i) {
        uint32_t idx = 0u;
        if (!find_sensor_index(&ctrl->inventory, samples[i].sensor_id, &idx)) {
            ctrl->rot_latch = 1u;
            ctrl->rot_watchdog_bite = 1u;
            ctrl->reset_hold = 1u;
            ctrl->last_trip_class = VOS_ES_TRIP_SENSOR_FAULT;
            ctrl->pending_firmware_consume = 1u;
            return VOS_ES_ERR_ROT_BITE;
        }
        const struct vos_es_sensor *s = &ctrl->inventory.sensors[idx];
        const enum vos_es_trip_class tc = evaluate_one_sample(s, &samples[i]);
        if (tc != VOS_ES_TRIP_NONE) {
            tripped = 1;
            ctrl->rot_latch = 1u;
            ctrl->last_trip_class = (uint32_t)tc;
            ctrl->pending_firmware_consume = 1u;
            if (s->rot_self_fault != 0u) {
                rot_bite = 1;
                ctrl->rot_watchdog_bite = 1u;
                ctrl->reset_hold = 1u;
            } else {
                ctrl->frozen_island_mask |= s->affected_island_mask;
            }
        }
    }

    if (rot_bite || ctrl->rot_watchdog_bite != 0u) {
        return VOS_ES_ERR_ROT_BITE;
    }
    if (tripped) {
        return VOS_ES_ERR_TRIP_LATCHED;
    }
    return VOS_ES_OK;
}

enum vos_es_status vos_es_acknowledge_transport(struct vos_es_controller *ctrl,
                                                uint32_t island_mask)
{
    if (ctrl == NULL || ctrl->inventory_valid == 0u) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    (void)island_mask;
    /* Transport acknowledgement cannot clear rot_latch, watchdog bite, or frozen islands. */
    if (ctrl->rot_watchdog_bite != 0u) {
        return VOS_ES_ERR_ROT_BITE;
    }
    if (ctrl->rot_latch != 0u) {
        return VOS_ES_ERR_TRIP_LATCHED;
    }
    return VOS_ES_OK;
}

enum vos_es_status vos_es_power_loss(struct vos_es_controller *ctrl)
{
    if (ctrl == NULL || ctrl->inventory_valid == 0u) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    /* Unpowered latch is not claimed retained; hold reset and mark lost interval. */
    ctrl->rot_latch = 0u;
    ctrl->rot_watchdog_bite = 0u;
    ctrl->reset_hold = 1u;
    ctrl->last_trip_class = VOS_ES_TRIP_UNKNOWN_RESET_OR_POWER_LOSS;
    ctrl->pending_firmware_consume = 1u;
    ctrl->lost_accounting_interval = 1u;
    return VOS_ES_ERR_RESET_HELD;
}

enum vos_es_status vos_es_recover_reset(struct vos_es_controller *ctrl,
                                        uint32_t boundary_healthy,
                                        uint32_t reset_table_done)
{
    if (ctrl == NULL || ctrl->inventory_valid == 0u) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    if (boundary_healthy == 0u || reset_table_done == 0u || ctrl->rot_latch != 0u) {
        return VOS_ES_ERR_RESET_HELD;
    }
    ctrl->reset_hold = 0u;
    ctrl->rot_watchdog_bite = 0u;
    ctrl->frozen_island_mask = 0u;
    return VOS_ES_OK;
}

enum vos_es_status vos_es_can_release_island(const struct vos_es_controller *ctrl,
                                             uint32_t island_id,
                                             uint32_t constants_ok,
                                             uint32_t enable_ok,
                                             uint32_t health_ok)
{
    if (ctrl == NULL || ctrl->inventory_valid == 0u || island_id >= VOS_ES_MAX_ISLANDS) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    if (ctrl->reset_hold != 0u || ctrl->rot_watchdog_bite != 0u) {
        return VOS_ES_ERR_RESET_HELD;
    }
    if ((ctrl->frozen_island_mask & (1u << island_id)) != 0u) {
        return VOS_ES_ERR_TRIP_LATCHED;
    }
    if (constants_ok == 0u || enable_ok == 0u || health_ok == 0u) {
        return VOS_ES_ERR_RETIRED_OR_UNBOUND;
    }
    return VOS_ES_OK;
}

enum vos_es_status vos_es_firmware_consume_event(struct vos_es_controller *ctrl,
                                                 struct vos_es_attested_event *out_event)
{
    if (ctrl == NULL || ctrl->inventory_valid == 0u || out_event == NULL) {
        return VOS_ES_ERR_INVALID_ARG;
    }
    const uint32_t hw_stopped =
        (ctrl->rot_latch != 0u || ctrl->rot_watchdog_bite != 0u || ctrl->reset_hold != 0u) ? 1u : 0u;
    if (ctrl->pending_firmware_consume == 0u || hw_stopped == 0u) {
        return VOS_ES_ERR_NO_HW_STOP;
    }

    struct vos_es_attested_event rec;
    memset(&rec, 0, sizeof(rec));
    rec.trip_class = ctrl->last_trip_class;
    rec.known_trip = (ctrl->last_trip_class != VOS_ES_TRIP_NONE &&
                      ctrl->last_trip_class != VOS_ES_TRIP_UNKNOWN_RESET_OR_POWER_LOSS)
                         ? 1u
                         : 0u;
    ctrl->recurrent_containment_count += 1u;
    rec.recurrent_count = ctrl->recurrent_containment_count;
    rec.lost_accounting_interval = ctrl->lost_accounting_interval;

    if (ctrl->event_count < VOS_ES_MAX_ATTESTED_LOG) {
        ctrl->events[ctrl->event_count] = rec;
        ctrl->event_count += 1u;
    }
    ctrl->pending_firmware_consume = 0u;
    ctrl->lost_accounting_interval = 0u;
    *out_event = rec;
    return VOS_ES_OK;
}
