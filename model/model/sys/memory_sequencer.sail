// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The refresh and discharge sequencer (R-15-247h): the composition-fixed
// schedule the second latency class is maintained on, and the mode-exit
// discharge that invalidates the authority resident in it.
//
// **It is a register slave and not an agent, and nothing here is reachable from
// an instruction.** The mechanism is §12 matter: a fixed-function register slave
// with no instruction fetch and no firmware, sequenced by the RoT while every
// application core, DMA engine, and capability-bearing fabric initiator is held
// in reset. No opcode is spent because there is no instruction stream in flight
// to carry one, which is what the absence contract's A-17 is an auditor's search
// of the decode surface for (docs/absence-contract.md). The slave's window sits
// in the address map and answers no requester at all (sys/platform.sail); the
// door these functions sit behind is the RoT's, and until the RoT core arrives
// (M3.1) it is the harness's and the model's own properties'.
//
// **What the sequencer reads is the composition and nothing else** (R-15-247r).
// Not `mtime`, not a counter, not an occupancy figure, not an access record, not
// a temperature: its whole input is the cadence table declared at composition
// and the bank count of the class it maintains, so no cadence or discharge
// schedule here is a function of a runtime measure, and there is no
// wake-on-access anywhere in it. That is a property a reader checks by looking
// at what these functions take, which is why the table is read once, in
// core/platform_config.sail, and computed with rather than sampled.
//
// **Refresh has no architectural content to execute and discharge has.** A
// refresh restores a charge this model does not represent and disturbs nothing
// observable, so what the model carries of it is the cadence and the deadline it
// is fixed against, which is the half a composition can get wrong: a sweep
// slower than the retention floor is data lost on a schedule, and the validator
// refuses it (postlude/validate_config.sail). The deadline is the floor and
// never the ceiling, retention being a lower bound with exactly one consumer
// (R-15-247c, core/memory_class.sail). Discharge is the other half, and it *is*
// observable, because what it removes is authority.
//
// **Discharge needs no new mechanism, which is R-15-247e read as a model.** The
// requirement realizes it through the cells' existing write devices, every write
// wordline in the bank asserted against grounded write bitlines, and it lands on
// all-zeros; this model's ordinary write path *is* those devices, and a write
// through it already clears the validity tag of every granule it covers, tag
// clearing being a property of the write path rather than an instruction
// (R-15-007r, core/mem_metadata.sail). So the discharge is a schedule over the
// write path: no instruction, no access type, and no second way to reach the
// array, landing in the untagged NULL granule R-15-182 and R-15-060 already fix,
// which is why R-15-189j's OFF→ON regeneration pass is obviated rather than
// scaled to capacity.
//
// **The unit of work is the bank and the walk over the banks is the RoT's.**
// R-15-198 makes power and reset sequencing one composition-time sequence table
// executed by the verified RoT firmware as the only sequencer, so what the slave
// does is one phase and what walks the phases is that table. The split is also
// what keeps the mode-exit path a property rather than a measurement: a composed
// bulk domain is gigabytes, and a whole-domain pass in this model is a run of the
// emulator rather than something a `$[test]` asserts.
//
// **There is no error model here, so the fail-stop's negative reading has no
// source in a valid composition, and that is stated rather than papered over.**
// The completion indication below is the pass's own answer: it is negative when
// a bank's write is refused or when a phase reaches no bank at all, and this
// model has no charge to leave behind and no syndrome to read, so a valid
// configuration always confirms. What matters is the shape, and the shape is
// R-15-247f's: the indication is read **once**, after a fixed worst-corner
// dwell, with no poll-until-done loop, no retry, and no discharge-speed-dependent
// timing on either path. A machine that can leave charge behind joins that read
// as a case rather than as a mechanism, exactly as an uncorrectable codeword
// joins `cbo.scrub`'s (extensions/platform/cbo_scrub.sail). What is *not* here is
// a fault-injection register, which would model the harness rather than the
// machine.

// The outcome of one phase of the exit-path discharge.
enum MemorySequencerOutcome = {
  // The pass drained its banks and the single completion read was positive.
  Seq_Confirmed,
  // The single completion read was negative. The transition stops here and the
  // domain does not enter the mode (R-15-189n, R-15-247f).
  Seq_FailStop,
  // The fail-stop is already latched, or the composition has no sequencer. Both
  // are refusals to act rather than results, and neither is a retry.
  Seq_Stopped,
}

mapping memory_sequencer_outcome_str : MemorySequencerOutcome <-> string = {
  Seq_Confirmed <-> "confirmed",
  Seq_FailStop  <-> "fail-stop",
  Seq_Stopped   <-> "stopped",
}
overload to_str = {memory_sequencer_outcome_str}

// The latch. A negative reading stops the transition rather than repeating it
// (R-15-247f), so this is architectural state and not a diagnostic: what it
// records is that a domain did not confirm, which is the fail-stop sentinel
// event R-17-030n composes with the rest of the detector class.
register memory_sequencer_fail_stop : bool = false

// The one second-class domain this composition declares.
//
// **That is a fact about the composition rather than a narrowing of the
// requirement**, the same shape the revocable interval map takes
// (core/revocation.sail): everything below quantifies over the domain this
// returns, so a composition with two bulk regions is served by making this a
// list and not by adding a mechanism.
private function second_class_region(regions : list(PMA_Region)) -> option(PMA_Region) =
  match regions {
    [||] => None(),
    region :: rest => match region.attributes.memory_class {
      Some(SecondClass) => Some(region),
      _                 => second_class_region(rest),
    },
  }

function memory_sequencer_domain() -> option(PMA_Region) =
  second_class_region(pma_regions)

// The bank set the schedule quantifies over, which is the class's own
// (R-15-247p): banks are whole-bound to islands, no bank is dynamically
// allocated, stolen, or donated, and no bank count varies with occupancy or
// load, so this is read out of the class record rather than counted at run time.
function memory_sequencer_banks() -> memory_class_banks =
  memory_class_constants(SecondClass).banks

// Phases over that set. The stagger is the whole of what banking buys: total
// refresh energy is fixed by cell count, so what a finer phase set lowers is
// peak instantaneous current, which converts a peak-current ceiling into a
// schedule the composition already owns (R-15-247g). Which set is *admissible*
// against droop, thermal coupling, and the power signature is M0.17's to decide
// and not a number this model holds; what it holds is that a phase's set is a
// subset of the class's banks, and the validator is where that is refused.
function memory_sequencer_phases(banks_per_phase : memory_sequencer_banks) -> nat =
  if banks_per_phase <= 0 then 0
  else (memory_sequencer_banks() + banks_per_phase - 1) / banks_per_phase

function memory_sequencer_refresh_phases() -> nat =
  memory_sequencer_phases(plat_memory_sequencer_refresh_banks_per_phase)

function memory_sequencer_discharge_phases() -> nat =
  memory_sequencer_phases(plat_memory_sequencer_discharge_banks_per_phase)

// The first bank of a phase and how many banks it reaches. A phase is a
// contiguous run because banks are whole-bound and no address interleaving
// crosses an island boundary (R-15-247p); the last phase is short where the set
// does not divide the count, which is a property of the schedule rather than a
// case in it.
function memory_sequencer_phase_first_bank(banks_per_phase : memory_sequencer_banks, phase : int) -> nat =
  if phase <= 0 then 0 else phase * banks_per_phase

function memory_sequencer_phase_bank_count(banks_per_phase : memory_sequencer_banks, phase : int) -> nat = {
  let banks = memory_sequencer_banks();
  let first = memory_sequencer_phase_first_bank(banks_per_phase, phase);
  if phase < 0 | first >= banks then 0
  else if first + banks_per_phase > banks then banks - first
  else banks_per_phase
}

// And the inverse, which is what the RoT's sequence table walks with and what
// the model's own properties name a phase by: the phase that reaches a bank.
function memory_sequencer_phase_of_bank(banks_per_phase : memory_sequencer_banks, bank : int) -> nat =
  if banks_per_phase <= 0 | bank <= 0 then 0 else bank / banks_per_phase

// The refresh sweep: every bank reached once, one phase at a time, at the
// composition-fixed interval.
function memory_sequencer_refresh_period_cycles() -> nat =
  memory_sequencer_refresh_phases() * plat_memory_sequencer_refresh_phase_cycles

// The deadline that sweep is fixed against, crossed into cycles rather than the
// sweep crossed into microseconds. One of the two has to cross: the retention
// floor is a wall-clock figure because an array leaks in time, and the cadence
// is stated in cycles because it enters §11 as a schedule term against the same
// clock every other term is stated in (R-15-195, core/memory_class.sail).
// Multiplying is what makes the crossing free of a runtime divisor, and it also
// rounds nothing: a period divided down to whole microseconds could round a
// cadence into compliance it does not have.
function memory_sequencer_refresh_deadline_cycles() -> nat =
  memory_class_refresh_deadline_us(SecondClass) * (plat_clock_frequency / 1000000)

// The mode-transition budget term (R-15-247f, R-15-247g): the whole exit-path
// discharge as one data-independent constant. No factor of it is a function of
// temperature, charge state, or what the bank held, which is the property a poll
// would destroy and the whole reason there is no poll.
function memory_sequencer_mode_exit_cycles() -> nat =
  memory_sequencer_discharge_phases() * plat_memory_sequencer_discharge_phase_cycles

// The bank geometry. The domain divides into its class's banks exactly, which
// the validator establishes, so this is arithmetic and not a search.
function memory_sequencer_bank_bytes() -> nat =
  match memory_sequencer_domain() {
    None()       => 0,
    Some(region) => {
      let banks = memory_sequencer_banks();
      if banks <= 0 then 0 else unsigned(region.size) / banks
    },
  }

function memory_sequencer_bank_base(bank : int) -> option(physaddrbits) =
  match memory_sequencer_domain() {
    None()       => None(),
    Some(region) =>
      if bank < 0 | bank >= memory_sequencer_banks() then None()
      else Some(region.base + to_bits_truncate(64, bank * memory_sequencer_bank_bytes())),
  }

// The bank an address falls in.
//
// **Nothing on an access path calls this, and nothing may.** It is here for the
// same reason `memory_class_at` is (sys/pma.sail): the model's own properties
// name the bank holding a granule they wrote, and the RoT's sequence table names
// the banks a mode releases. An access that consulted the bank map would be the
// machine deciding at run time what the memory plan decided at composition,
// which is the hierarchy R-15-247 exists to refuse.
function memory_sequencer_bank_of(addr : physaddrbits) -> option(nat) =
  match memory_sequencer_domain() {
    None()       => None(),
    Some(region) => {
      let base   = unsigned(region.base);
      let here   = unsigned(addr);
      let bytes  = memory_sequencer_bank_bytes();
      if bytes <= 0 then None()
      else if here < base then None()
      else if here >= base + unsigned(region.size) then None()
      else Some((here - base) / bytes)
    },
  }

// The widest access the memory interface takes, which is the chunk the drain is
// issued in: the pass is the same write every other agent makes, so the number
// of granules it clears per call is the interface's business and not this
// file's (sys/mem.sail, core/mem_metadata.sail).
type memory_sequencer_chunk_bytes : Int = max_mem_access
let  memory_sequencer_chunk_bytes = sizeof(memory_sequencer_chunk_bytes)

// One bank drained through its own write devices.
private function memory_sequencer_discharge_bank(bank : int) -> bool =
  match memory_sequencer_bank_base(bank) {
    None()     => false,
    Some(base) => {
      let chunks = memory_sequencer_bank_bytes() / memory_sequencer_chunk_bytes;
      // A bank that reaches no chunk is not a drained bank. The validator
      // refuses that geometry, so this is the arm that keeps the confirmation
      // from being vacuously positive rather than an arm a composition takes.
      var drained : bool = chunks > 0;
      foreach (i from 0 to (chunks - 1)) {
        let paddr = Physaddr(base + to_bits_truncate(64, i * memory_sequencer_chunk_bytes));
        match mem_write_ea(paddr, memory_sequencer_chunk_bytes, Store(Data), false, false) {
          Err(_, _) => drained = false,
          Ok(_)     =>
            match mem_write_value(paddr, memory_sequencer_chunk_bytes, zeros(), Store(Data), false, false) {
              Ok(true) => (),
              _        => drained = false,
            },
        }
      };
      drained
    },
  }

// One phase of the exit-path discharge (R-15-247q): a second-class domain
// leaving a mode is discharged on the way out rather than cleared on the way
// back in, which relocates the dwell rather than adding one and narrows the
// R-17-058f exposure to the domains ON or RETAINED at the instant of power loss.
//
// The order is R-15-247d's and it is not this function's to vary: the tag plane
// is discharged and the discharge confirmed *before* any requester may name the
// domain. Here that ordering is structural rather than sequenced, because the
// requesters are in reset for the whole of it and the tag plane discharges with
// the data plane in one write (R-15-247b's granule-atomic commit); what the RoT
// owes on top is to admit the domain only against `Seq_Confirmed`.
function memory_sequencer_discharge_phase(phase : int) -> MemorySequencerOutcome = {
  // A composition with no sequencer has no bulk domain to drain, and the
  // validator refuses the pairing in both directions, so this arm is a refusal
  // to act rather than an arm a valid configuration takes.
  if not(plat_have_memory_sequencer) then return Seq_Stopped;

  // A latched fail-stop is not retried. R-15-247f admits no retry on either
  // path, so a transition that stopped stays stopped.
  if memory_sequencer_fail_stop then return Seq_Stopped;

  let per_phase = plat_memory_sequencer_discharge_banks_per_phase;
  let first = memory_sequencer_phase_first_bank(per_phase, phase);
  let count = memory_sequencer_phase_bank_count(per_phase, phase);

  var drained : bool = count > 0;
  foreach (bank from first to (first + count - 1)) {
    if not(memory_sequencer_discharge_bank(bank)) then drained = false
  };

  // The fixed worst-corner dwell elapses here and is not waited out: nothing
  // observes the array while it does, every requester being in reset, so the
  // model carries the constant (`memory_sequencer_mode_exit_cycles`) where a
  // machine carries the wait. Then the completion indication, read **once**.
  if drained then Seq_Confirmed
  else {
    memory_sequencer_fail_stop = true;
    Seq_FailStop
  }
}
