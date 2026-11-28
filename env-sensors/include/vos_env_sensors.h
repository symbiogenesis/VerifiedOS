// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_ENV_SENSORS_H
#define VOS_ENV_SENSORS_H

#include <stdint.h>

/*
 * Bounded, GC-free C17 environmental fault sensor validator and fail-stop
 * boundary controller for Q41a-i.
 * Reference specification: [EnvironmentalSensors.v](../../proofs/EnvironmentalSensors.v)
 * and [environmental-fault-sensors.md](../../docs/hardware/environmental-fault-sensors.md).
 */

enum {
    VOS_ES_MAX_SENSORS = 64u,
    VOS_ES_MAX_RAILS = 16u,
    VOS_ES_MAX_CLOCKS = 16u,
    VOS_ES_MAX_DATAPATHS = 16u,
    VOS_ES_MAX_REGIONS = 16u,
    VOS_ES_MAX_ISLANDS = 16u,
    VOS_ES_MAX_SITES_PER_NODE = 8u,
    VOS_ES_MAX_DEPS = 8u,
    VOS_ES_MAX_ATTESTED_LOG = 32u
};

enum vos_es_status {
    VOS_ES_OK = 0,
    VOS_ES_ERR_INVALID_ARG = -1,
    VOS_ES_ERR_EMPTY_TOPOLOGY = -2,
    VOS_ES_ERR_MISSING_BLOCK = -3,
    VOS_ES_ERR_UNCOVERED_RAIL = -4,
    VOS_ES_ERR_UNCOVERED_CLOCK = -5,
    VOS_ES_ERR_UNCOVERED_DATAPATH = -6,
    VOS_ES_ERR_UNCOVERED_REGION = -7,
    VOS_ES_ERR_DEPENDENCY_CYCLE = -8,
    VOS_ES_ERR_SELF_OBSERVATION = -9,
    VOS_ES_ERR_MISSING_DEPENDENCY = -10,
    VOS_ES_ERR_PENDING_FIELD = -11,
    VOS_ES_ERR_MUTABLE_POLICY = -12,
    VOS_ES_ERR_INVALID_BANDS = -13,
    VOS_ES_ERR_RETIRED_OR_UNBOUND = -14,
    VOS_ES_ERR_BACKSIDE_OCCLUSION = -15,
    VOS_ES_ERR_PITCH_VIOLATION = -16,
    VOS_ES_ERR_TRIP_LATCHED = -17,
    VOS_ES_ERR_ROT_BITE = -18,
    VOS_ES_ERR_RESET_HELD = -19,
    VOS_ES_ERR_NO_HW_STOP = -20
};

enum vos_es_family {
    VOS_ES_FAM_SUPPLY = 1u,
    VOS_ES_FAM_CLOCK = 2u,
    VOS_ES_FAM_TIMING = 3u,
    VOS_ES_FAM_OPTICAL = 4u
};

enum vos_es_block_class {
    VOS_ES_BLK_ROT = 1u,
    VOS_ES_BLK_S0 = 2u,
    VOS_ES_BLK_S1 = 3u,
    VOS_ES_BLK_CORE_C = 4u,
    VOS_ES_BLK_CORE_V = 5u,
    VOS_ES_BLK_CORE_M = 6u
};

enum vos_es_trip_class {
    VOS_ES_TRIP_NONE = 0u,
    VOS_ES_TRIP_SUPPLY_EXCURSION = 1u,
    VOS_ES_TRIP_CLOCK_EXCURSION = 2u,
    VOS_ES_TRIP_TIMING_MARGIN = 3u,
    VOS_ES_TRIP_OPTICAL_ILLUMINATION = 4u,
    VOS_ES_TRIP_SENSOR_FAULT = 5u,
    VOS_ES_TRIP_UNEXPECTED_DEACTIVATION = 6u,
    VOS_ES_TRIP_UNKNOWN_RESET_OR_POWER_LOSS = 7u
};

struct vos_es_rail_spec {
    uint32_t rail_id;
    uint32_t parent_rail_id;
    uint32_t is_leaf;
    uint32_t reaches_rot;
    uint32_t island_mask;
    uint32_t site_count;
    uint32_t site_ids[VOS_ES_MAX_SITES_PER_NODE];
};

struct vos_es_clock_spec {
    uint32_t clock_id;
    uint32_t parent_clock_id;
    uint32_t is_leaf;
    uint32_t is_rot_slow_clock;
    uint32_t reaches_rot;
    uint32_t island_mask;
    uint32_t site_count;
    uint32_t site_ids[VOS_ES_MAX_SITES_PER_NODE];
};

struct vos_es_datapath_spec {
    uint32_t datapath_id;
    uint32_t block_class;
    uint32_t island_id;
    uint32_t reaches_rot;
};

struct vos_es_region_spec {
    uint32_t region_id;
    uint32_t reaches_rot;
    uint32_t island_mask;
    uint32_t declared_pitch_um;
    uint32_t gap_free;
    uint32_t occludes_backside;
};

struct vos_es_topology {
    uint32_t has_rot;
    uint32_t has_s0;
    uint32_t has_s1;
    uint32_t active_island_mask;
    uint32_t rail_count;
    struct vos_es_rail_spec rails[VOS_ES_MAX_RAILS];
    uint32_t clock_count;
    struct vos_es_clock_spec clocks[VOS_ES_MAX_CLOCKS];
    uint32_t datapath_count;
    struct vos_es_datapath_spec datapaths[VOS_ES_MAX_DATAPATHS];
    uint32_t region_count;
    struct vos_es_region_spec regions[VOS_ES_MAX_REGIONS];
};

struct vos_es_supply_cfg {
    uint32_t voltage_min_uv;
    uint32_t voltage_max_uv;
    uint32_t hysteresis_uv;
};

struct vos_es_clock_cfg {
    uint32_t period_min_ps;
    uint32_t period_max_ps;
    uint32_t high_min_ps;
    uint32_t high_max_ps;
    uint32_t low_min_ps;
    uint32_t low_max_ps;
    uint32_t duty_min_permille;
    uint32_t duty_max_permille;
    uint32_t missing_edge_max_ps;
    uint32_t observer_clock_id;
    uint32_t is_rot_slow_clock;
    uint32_t adaptive_ref;
};

struct vos_es_timing_cfg {
    uint32_t slack_min_ps;
    uint32_t correspondence_qualified;
    uint32_t fixed_public_excitation;
    uint32_t samples_operand;
};

struct vos_es_optical_cfg {
    uint32_t photocurrent_trip_na;
    uint32_t dark_current_max_na;
    uint32_t site_pitch_um;
    uint32_t max_site_pitch_um;
    uint32_t occludes_backside;
};

struct vos_es_sensor {
    uint32_t sensor_id;
    uint32_t family;
    uint32_t resource_id;
    uint32_t site_id;
    uint32_t affected_island_mask;
    uint32_t rot_self_fault;
    uint32_t always_on;
    uint32_t enable_constant;
    uint32_t has_pending;
    uint32_t has_owner;
    uint32_t has_evidence_tuple;
    uint32_t retired_artifact;
    uint32_t sw_writable_threshold;
    uint32_t sw_writable_disable;
    uint32_t dynamic_calibration;
    uint32_t adds_isa_or_csr;
    uint32_t opp_table_bound;
    uint32_t ref_resource_id;
    uint32_t health_observer_id;
    uint32_t uses_only_guarded_liveness;
    uint32_t dep_count;
    uint32_t dep_sensor_ids[VOS_ES_MAX_DEPS];
    struct vos_es_supply_cfg supply;
    struct vos_es_clock_cfg clock;
    struct vos_es_timing_cfg timing;
    struct vos_es_optical_cfg optical;
};

struct vos_es_inventory {
    uint32_t sensor_count;
    struct vos_es_sensor sensors[VOS_ES_MAX_SENSORS];
};

struct vos_es_sample {
    uint32_t sensor_id;
    uint32_t sensor_disabled;
    uint32_t corrupt_constants;
    uint32_t open_or_stuck_line;
    uint32_t stopped_reference;
    uint32_t broken_transducer;
    uint32_t health_timeout;
    uint32_t table_off_authorized;
    uint32_t consumer_reset_isolated;
    uint32_t physically_inactive;
    uint32_t transition_overrun;
    uint32_t voltage_uv;
    uint32_t period_ps;
    uint32_t high_ps;
    uint32_t low_ps;
    uint32_t edge_gap_ps;
    uint32_t clock_stopped;
    uint32_t slack_ps;
    uint32_t photocurrent_na;
    uint64_t sw_operand_value;
};

struct vos_es_env_context {
    uint32_t rot_cpu_alive;
    uint32_t main_spine_clock_alive;
    uint32_t firmware_mailbox_ready;
    uint32_t sw_mask_requested;
    uint32_t transport_ack_requested;
};

struct vos_es_attested_event {
    uint32_t known_trip;
    uint32_t trip_class;
    uint32_t recurrent_count;
    uint32_t lost_accounting_interval;
};

struct vos_es_controller {
    uint32_t inventory_valid;
    uint32_t rot_latch;
    uint32_t rot_watchdog_bite;
    uint32_t reset_hold;
    uint32_t frozen_island_mask;
    uint32_t last_trip_class;
    uint32_t pending_firmware_consume;
    uint32_t lost_accounting_interval;
    uint32_t recurrent_containment_count;
    uint32_t event_count;
    struct vos_es_attested_event events[VOS_ES_MAX_ATTESTED_LOG];
    struct vos_es_inventory inventory;
};

enum vos_es_status vos_es_validate_sensor(const struct vos_es_sensor *sensor);
enum vos_es_status vos_es_check_dependencies(const struct vos_es_inventory *inv);
enum vos_es_status vos_es_validate_topology(const struct vos_es_topology *topo,
                                            const struct vos_es_inventory *inv);
enum vos_es_status vos_es_controller_init(struct vos_es_controller *ctrl,
                                          const struct vos_es_topology *topo,
                                          const struct vos_es_inventory *inv);
enum vos_es_status vos_es_evaluate_step(struct vos_es_controller *ctrl,
                                        const struct vos_es_sample *samples,
                                        uint32_t sample_count,
                                        const struct vos_es_env_context *env);
enum vos_es_status vos_es_acknowledge_transport(struct vos_es_controller *ctrl,
                                                uint32_t island_mask);
enum vos_es_status vos_es_power_loss(struct vos_es_controller *ctrl);
enum vos_es_status vos_es_recover_reset(struct vos_es_controller *ctrl,
                                        uint32_t boundary_healthy,
                                        uint32_t reset_table_done);
enum vos_es_status vos_es_can_release_island(const struct vos_es_controller *ctrl,
                                             uint32_t island_id,
                                             uint32_t constants_ok,
                                             uint32_t enable_ok,
                                             uint32_t health_ok);
enum vos_es_status vos_es_firmware_consume_event(struct vos_es_controller *ctrl,
                                                 struct vos_es_attested_event *out_event);

#endif
