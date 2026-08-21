// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The two static latency classes of main memory (R-15-247).
//
// Main memory is bespoke volatile 6T SRAM for the scalar working set and every
// cycle-critical array, and oxide-semiconductor 2T0C decks for bulk. Both are
// assigned at composition by the same static memory plan that already assigns
// banks, and **each enters §11 as one fixed latency constant**. There is no
// cache, no migration, no tiering, no wake-on-access, and no runtime promotion
// between them, so a second class is a second constant and not a hierarchy
// (R-15-164).
//
// **What is here is the constants; where a region sits is a PMA** (sys/pma.sail).
// That split is the requirement's own: the class boundary is decided once, at
// composition, by the memory plan, and no instruction, no fault, and no power
// transition moves a region across it (R-15-247), so the assignment belongs to
// the same per-region declaration that already carries every other property the
// composition fixes about an address range, and the constants belong here beside
// the platform's other composition-time numbers.
//
// **No instruction reads any of this and none ever will** (R-15-247h). Discharge,
// refresh, second-class tag maintenance, and class migration are §12 matter, a
// fixed-function register slave sequenced by the RoT while every requester is
// held in reset (sys/memory_sequencer.sail), and refresh rides the existing
// `cbo.scrub` (extensions/platform/cbo_scrub.sail, R-15-177a) where the schedule
// prefers software. The decode surface is therefore unchanged by this file and
// by that one, which is what the absence contract's A-17 is an auditor's search
// for.
//
// **The class carries no trust gradient** (R-15-247s). Tags, ECC, and the
// R-08-005 revocation load filter are identical across classes, so nothing in
// this model consults the class before deciding a capability question, and a
// grep finding it consulted there would be the defect. The one plane that could
// have made the boundary a trust boundary is the tag plane, and it does not: the
// validity tag is native to each class's own array, one plane per class, read
// and written in parallel with the data, with no sidecar in a foreign medium
// (R-15-247a, R-15-203). The model's tag plane is keyed by granule and knows
// nothing of classes, which is that requirement realized rather than merely
// permitted (core/mem_metadata.sail).

enum MemoryClass = { FirstClass, SecondClass }

mapping memory_class_str : MemoryClass <-> string = {
  FirstClass  <-> "first",
  SecondClass <-> "second",
}
overload to_str = {memory_class_str}

// The declared widths. Each bound says what the field is allowed to be rather
// than what it is: the values themselves are R-15-247m's to measure and are
// placeholders in every configuration this tree ships (below).
//
// Latency is in **cycles**, because it enters §11 as a schedule term against the
// same clock every other term is stated in. Retention is in **microseconds**,
// because an array leaks in time and not in cycles: the refresh deadline the
// M0.16 sequencer is fixed against is a wall-clock deadline, so stating it in
// cycles would make it a function of a frequency the mode index also moves.
type memory_class_latency   = range(0, 65535)
type memory_class_retention = range(0, 86400000000)
type memory_class_density   = range(0, 65535)
type memory_class_banks     = range(0, 65535)

// **The record is symmetric and the machine is not**, and the asymmetry is
// R-15-247n's rather than a composition's to choose: the first class is latched
// and the second stores charge on a gate node with no restoring feedback, so
// three of these fields have no meaning on the first class at all. They are
// declared zero there and the validator refuses anything else
// (postlude/validate_config.sail), which is the model's existing
// zero-is-absent idiom (`misaligned_atomicity_granule_size_exp`, sys/pma.sail)
// used for a distinction that is architectural rather than optional.
//
//   - `retention_floor_us` / `retention_ceiling_us`. The corner is a **measured
//     interval and not a point**, a minutes-to-hours spread deciding refresh
//     power, droop admissibility at capacity, maintenance cadence, and the
//     R-17-058f window at once (R-15-247m). Only the floor is ever consumed, and
//     only by the refresh deadline: no reset, sanitization, or containment
//     guarantee may rest on a decay rate, on an upper bound on retention, or on
//     any timing derived from leakage, so the ceiling is carried for the
//     qualification record and read by nothing (R-15-247c). That is why the two
//     are separate fields rather than a mean with a tolerance.
//   - `refresh_cycles`. A latched array has no refresh.
//   - `discharge_cycles`. On the second class this is R-15-247f's fixed
//     worst-corner dwell, after which a single fail-stop completion indication
//     is read once, with no poll and no retry. On the first class there is no
//     dwell to declare: R-15-200's cold-boot answer is stated over a medium
//     whose retention is seconds, so its OFF is its own sanitization, where the
//     second class's OFF is a power action and not a sanitization at all, which
//     is exactly why R-15-247q takes the discharge on the mode-exit path.
//
// `qualified` is a property of the **configuration** and not of the machine.
// R-15-247m puts these constants in the attested devicetree at part
// qualification, measured on a repaired megabit-class macro carrying complete
// tag, ECC, refresh, discharge, and routing overhead, and says in the same
// breath that no density figure is an architectural input ahead of that
// measurement. A devicetree that carries provisional numbers with nothing
// distinguishing them from measured ones is how a placeholder becomes an input,
// so the flag is carried in the record, emitted into the generated devicetree
// (postlude/device_tree.sail), and false in every configuration here until R5
// lands the measurement.
struct MemoryClassConstants = {
  qualified                   : bool,
  usable_density_mbit_per_mm2 : memory_class_density,
  banks                       : memory_class_banks,
  retention_floor_us          : memory_class_retention,
  retention_ceiling_us        : memory_class_retention,
  read_cycles                 : memory_class_latency,
  write_cycles                : memory_class_latency,
  refresh_cycles              : memory_class_latency,
  discharge_cycles            : memory_class_latency,
}

let plat_memory_class_first  : MemoryClassConstants = config memory.classes.first
let plat_memory_class_second : MemoryClassConstants = config memory.classes.second

function memory_class_constants(c : MemoryClass) -> MemoryClassConstants =
  match c {
    FirstClass  => plat_memory_class_first,
    SecondClass => plat_memory_class_second,
  }

// **There is no separate fetch constant, and that is a consequence rather than
// an omission.** R-15-247j prices second-class code placement against "that
// class's fetch constant"; with R-15-164 deleting every cache there is no
// instruction cache, no separate instruction path, and nothing to amortize, so a
// fetch is a read of whichever class the code resides on and the fetch constant
// *is* the read constant. The delta R-15-247j makes admission-visible is
// therefore the difference of two numbers this record already carries, computed
// by the static memory plan (M1.9) rather than by anything the machine executes.
function memory_class_fetch_cycles(c : MemoryClass) -> memory_class_latency =
  memory_class_constants(c).read_cycles

// The one consumer of a retention figure, stated once so that a second one is
// visible as a new call site rather than as a new arithmetic (R-15-247c). The
// sequencer's composition-fixed cadence is fixed against this and against
// nothing else (sys/memory_sequencer.sail).
function memory_class_refresh_deadline_us(c : MemoryClass) -> memory_class_retention =
  memory_class_constants(c).retention_floor_us
