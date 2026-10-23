(* SPDX-License-Identifier: Apache-2.0 *)
Require Import Probe.bindings_types Probe.bindings TagQualification.CallerBridge.
Set Printing All.
Set Printing Universes.
Print Module Type SailStdpp.ConcurrencyInterface.InterfaceT.
Print bindings_types.Interface.outcome.
Print bindings_types.Interface.outcome_ind.
Print bindings_types.Interface.outcome_rec.
Print bindings_types.Interface.outcome_rect.
Print bindings_types.Defs.read_tag_bool.
Print bindings_types.Defs.write_tag_bool.
Print bindings.read_mem_.
Print bindings.read_mem_ifetch_.
Print bindings.read_mem_exclusive_.
Print bindings.write_mem_.
Print bindings.write_mem_exclusive_.
Print bindings.addr_to_tag_addr.
Print bindings.__ReadRAM_Meta.
Print bindings.__WriteRAM_Meta.
Print bindings.write_ram.
Print bindings.read_ram.
Print Assumptions CallerBridge.L.absent_false.
Print Assumptions CallerBridge.L.lookup_written.
Print Assumptions CallerBridge.L.neighbor_framed.
Print Assumptions CallerBridge.L.read_bridge.
Print Assumptions CallerBridge.L.write_bridge.
Print Assumptions CallerBridge.L.read_native.
Print Assumptions CallerBridge.L.write_native.
Print Assumptions CallerBridge.L.old_event_preserved.
Print Assumptions CallerBridge.L.read_try_catch.
Print Assumptions CallerBridge.L.write_try_catch.
Print Assumptions CallerBridge.L.read_extra_map.
Print Assumptions CallerBridge.L.write_extra_map.
Print Assumptions CallerBridge.L.tag_before_early_return.
Print Assumptions CallerBridge.L.read_write_read_clear.
Print Assumptions CallerBridge.loop_events.
Print Assumptions CallerBridge.loop_state.
Print Assumptions CallerBridge.metadata_events.
Print Assumptions CallerBridge.metadata_state.
Print Assumptions CallerBridge.metadata_read.
Print Assumptions CallerBridge.physical_write_response.
Print Assumptions CallerBridge.requested_read_first.
Print Assumptions CallerBridge.unrequested_read_first.
Print Assumptions CallerBridge.requested_read_then_data.
Print Assumptions CallerBridge.unrequested_read_refusal.
Print Assumptions CallerBridge.aligned_capability.
Print Assumptions CallerBridge.partial_clear.
Print Assumptions CallerBridge.multi_clear.
Print Assumptions CallerBridge.wraparound_preserved.
Print Assumptions CallerBridge.absent_zero.
Print Assumptions CallerBridge.absent_max.
Print Assumptions CallerBridge.no_extra_granule_shift.
Print Assumptions CallerBridge.requested_read_success_meta.
Print Assumptions CallerBridge.unrequested_read_success_default.
Print Assumptions CallerBridge.requested_read_refusal.
