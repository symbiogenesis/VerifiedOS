// Properties of the platform surface the profile adds and no upstream model
// carries: `fence.t` (extensions/platform/fence_t.sail), `vmclear` and
// `cbo.scrub` beside it, the machine-level interrupt file, the revocation
// sidecar's register slave (sys/platform.sail, core/revocation.sail), the two
// static latency classes of main memory (core/memory_class.sail), and the
// refresh and discharge sequencer over the second of them
// (sys/memory_sequencer.sail).
//
// Each of these is net-new here, so there is no oracle to differentially test
// it against and a property asserted about it and a program that runs it are
// different evidence. These are the first half; the corpus is the second
// (docs/differential-corpus.md).

// *****************************************************************
// `fence.t`.

// The flush set is a single structure, the store buffer, and this model has no
// buffer to drain: it is in-order and single-copy, so the fence's whole
// architectural content is that it retires having disturbed nothing
// (R-15-062, R-15-213). What is worth asserting is exactly that, and that its
// reserved fields are reserved rather than ignored.
$[test]
function test_fence_t_retires_and_disturbs_nothing() -> unit = {
  match ext_decode(0x0000400f) {
    FENCE_T() => (),
    _         => assert(false, "MISC-MEM funct3 100 must decode as fence.t"),
  };

  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, 0x0000000080000000);
  X(encdec_reg(0b00011)) = 0x0123456789abcdef;

  match execute(FENCE_T()) {
    Retire_Success() => (),
    _                => assert(false, "fence.t must retire"),
  };
  assert(C(encdec_reg(0b00010)).tag);
  assert(X(encdec_reg(0b00011)) == 0x0123456789abcdef);

  // `fence`'s reserved `rs1` and `rd` fields are ignored for forward
  // compatibility with finer-grained fences. This instruction has no future
  // extension to reserve them for, so a non-zero field decodes to nothing and
  // traps (R-15-014).
  match ext_decode(0x0800400f) {
    ILLEGAL(_) => (),
    _          => assert(false, "fence.t with a non-zero rs1 must be illegal"),
  };
  match ext_decode(0x0000418f) {
    ILLEGAL(_) => (),
    _          => assert(false, "fence.t with a non-zero rd must be illegal"),
  };
  match ext_decode(0x0010400f) {
    ILLEGAL(_) => (),
    _          => assert(false, "fence.t with a non-zero immediate must be illegal"),
  };
}

// *****************************************************************
// `vmclear`.

// The partition switch's eager zeroize as one unconditional pass over the unit
// state it does not save (R-15-069d, R-07-014c). What is asserted is that the
// pass reaches every structure of the inventory this model carries and that it
// clears `vtype` to *no configuration* rather than to zeroes, which are
// different states: an all-zeroes `vtype` is SEW=8 at LMUL=1, a valid
// configuration the successor partition never selected.
$[test]
function test_vmclear_clears_the_whole_unit_inventory() -> unit = {
  match ext_decode(0x0000100b) {
    VMClear() => (),
    _         => assert(false, "custom-0 funct3 001 must decode as vmclear"),
  };

  let full : vlenbits = ones();
  V(Vregidx(0b00011)) = full;
  V(Vregidx(0b11111)) = full;
  vl          = 0x0000000000000010;
  vtype[vill] = 0b0;
  vtype[vsew] = 0b010;
  vcsr[vxrm]  = 0b11;
  vcsr[vxsat] = 0b1;

  // The unit is dirty and `mstatus.VS` says it is not. That is the state the
  // decode guard has to survive: `VS` is writable by the executing partition,
  // so an instruction gated on `currentlyEnabled` rather than on `hartSupports`
  // would trap here and leave the residue the switch exists to erase
  // (extensions/platform/vmclear.sail, R-07-014a).
  mstatus[VS] = extStatus_map(Off);

  match execute(VMClear()) {
    Retire_Success() => (),
    _                => assert(false, "vmclear must retire"),
  };

  assert(V(Vregidx(0b00011)) == zeros());
  assert(V(Vregidx(0b11111)) == zeros());
  assert(vl == zeros());
  assert(vtype[vill] == 0b1);
  assert(vcsr.bits == zeros());

  // And it leaves `mstatus` alone: the extension-context gate is the switch's
  // to restore over every register a partition can name, not this
  // instruction's to edit (R-07-015).
  assert(extStatus_map(mstatus[VS]) == Off);

  // It takes no operand the clear could depend on and names no destination, the
  // class's unit-state inventory naming them all, so every other field is
  // reserved and a non-zero one decodes to nothing rather than being ignored
  // (R-15-069d, R-15-014).
  match ext_decode(0x0000900b) {
    ILLEGAL(_) => (),
    _          => assert(false, "vmclear with a non-zero rs1 must be illegal"),
  };
  match ext_decode(0x0000108b) {
    ILLEGAL(_) => (),
    _          => assert(false, "vmclear with a non-zero rd must be illegal"),
  };
  match ext_decode(0x0200100b) {
    ILLEGAL(_) => (),
    _          => assert(false, "vmclear with a non-zero funct7 must be illegal"),
  };
}

// *****************************************************************
// `cbo.scrub`.

// The scrub is exactly value- and tag-preserving, which is the property that
// separates it from every other write on the machine: an ordinary store of the
// same bits clears the validity tag of the granule it covers, tag clearing
// being a property of the write path rather than an instruction (R-15-007r), so
// maintenance of a capability-bearing array through the store path would
// destroy the authority in it (R-15-177a).
$[test]
function test_cbo_scrub_preserves_the_data_and_the_tag_plane() -> unit = {
  let block : xlenbits = 0x0000000080000400;
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let auth = setCapAddrChecked(region, block);
  let value = setCapAddrChecked(region, block + 128);

  C(encdec_reg(0b00011)) = value;
  foreach (i from 0 to (caps_per_block - 1)) {
    match cap_store(encdec_reg(0b00011), auth, 0b000010, block + (i * cap_size)) {
      Retire_Success() => (),
      _                => assert(false, "filling the block must succeed"),
    }
  };

  // The base register names an address anywhere in the block and the block is
  // the naturally aligned one containing it, as `cbo.zero` addresses it: there
  // is no alignment requirement on the operand, only on what it selects.
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, block + 24);
  match execute(CBO_SCRUB(encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "an authorised scrub must retire"),
  };

  foreach (i from 0 to (caps_per_block - 1)) {
    match cap_load(encdec_reg(0b00100), auth, 0b000010, block + (i * cap_size)) {
      Retire_Success() => (),
      _                => assert(false, "the scrubbed block must still load"),
    };
    assert(C(encdec_reg(0b00100)).tag);
    assert(C(encdec_reg(0b00100)) == value);
  };

  // It reads the block *and* writes back what it corrects, so it needs both
  // permissions: a holder of a read-only view may not cause a write to memory
  // it cannot write, even one that puts back what it found.
  C(encdec_reg(0b00010)) = { auth with perms = perms_r_cap_lm_lg | perms_global_bit };
  match execute(CBO_SCRUB(encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitStoreViolation),
    _ => assert(false, "a scrub without store permission must fault"),
  };
  C(encdec_reg(0b00010)) = { auth with perms = perms_none | perms_global_bit };
  match execute(CBO_SCRUB(encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitLoadViolation),
    _ => assert(false, "a scrub without load permission must fault"),
  };

  // And only over an array that carries the code it verifies. A device register
  // has no codeword to scrub, so IO memory refuses it at the PMA rather than at
  // the instruction, which is where the distinction belongs (sys/mem.sail).
  C(encdec_reg(0b00010)) = setCapAddrChecked(root_data_cap, zero_extend(plat_imsic_base));
  match execute(CBO_SCRUB(encdec_reg(0b00010))) {
    Trap(_, _) => (),
    _          => assert(false, "a scrub of IO memory must fault"),
  };

  match ext_decode(0x0050200f) {
    CBO_SCRUB(_) => (),
    _            => assert(false, "MISC-MEM funct3 010 at immediate 5 must decode as cbo.scrub"),
  };
}

// *****************************************************************
// The machine-level interrupt file.

// An MSI *is* a store to the interrupt file, so send authority is a write
// capability rather than an entry in a side table (R-15-064); and the pending
// array is read with ordinary loads, the indirect interface that would
// otherwise carry that read being deleted (R-15-065). Nothing here raises a
// trap: an MSI is latched pending state that software polls.
$[test]
function test_the_interrupt_file_latches_pending_state() -> unit = {
  let doorbell = Physaddr(zero_extend(plat_imsic_base));
  let array    = Physaddr(zero_extend(plat_imsic_base + 8));

  let _ = mem_write_value(array, 8, zeros(), Store(Data), false, false);

  // Sending identity 5 sets bit 5 and nothing else.
  let _ = mem_write_value(doorbell, 8, to_bits(64, 5), Store(Data), false, false);
  match mem_read(Load(Data), array, 8, false, false) {
    Ok(v) => assert(v == (zero_extend(0b1) << 5)),
    Err(_, _) => assert(false, "the pending array must be readable"),
  };

  // Pending state accumulates: a second sender's identity joins the first
  // rather than replacing it.
  let _ = mem_write_value(doorbell, 8, to_bits(64, 9), Store(Data), false, false);
  match mem_read(Load(Data), array, 8, false, false) {
    Ok(v) => assert(v == ((zero_extend(0b1) << 5) | (zero_extend(0b1) << 9))),
    Err(_, _) => assert(false, "the pending array must be readable"),
  };

  // The receiver clears by writing the array back, and identity 0 is reserved:
  // it is neither settable nor readable as pending.
  let _ = mem_write_value(array, 8, ones(), Store(Data), false, false);
  match mem_read(Load(Data), array, 8, false, false) {
    Ok(v) => assert(v == (ones() ^ zero_extend(0b1))),
    Err(_, _) => assert(false, "the pending array must be readable"),
  };
  let _ = mem_write_value(array, 8, zeros(), Store(Data), false, false);
  let _ = mem_write_value(doorbell, 8, zeros(), Store(Data), false, false);
  match mem_read(Load(Data), array, 8, false, false) {
    Ok(v) => assert(v == zeros()),
    Err(_, _) => assert(false, "the pending array must be readable"),
  };

  // The doorbell is write-only, as it is upstream: reading back the number a
  // sender wrote would give the pending state a second name.
  let _ = mem_write_value(doorbell, 8, to_bits(64, 5), Store(Data), false, false);
  match mem_read(Load(Data), doorbell, 8, false, false) {
    Ok(v) => assert(v == zeros()),
    Err(_, _) => assert(false, "the doorbell must read as zero"),
  };
  let _ = mem_write_value(array, 8, zeros(), Store(Data), false, false);
}

// *****************************************************************
// The revocation sidecar.

// The bitmap is not addressable as data: it is a register slave of its own, so
// *only the kernel revocation path may update it* is a fact about which
// compartment the composed distribution hands a capability to that window, not
// about a mode (R-08-005a, R-15-003). What is asserted here is the round trip
// through that window and its agreement with the plane the load filter reads,
// which is the one thing that would otherwise be two structures.
$[test]
function test_the_revocation_window_and_the_plane_are_one_structure() -> unit = {
  let window = Physaddr(zero_extend(plat_revocation_base));
  revocation_bits = zeros();

  let _ = mem_write_value(window, 8, to_bits(64, 5), Store(Data), false, false);
  match mem_read(Load(Data), window, 8, false, false) {
    Ok(v) => assert(v == to_bits(64, 5)),
    Err(_, _) => assert(false, "the revocation window must be readable"),
  };

  // Bit 0 and bit 2 of word 0 are the granules at the interval's base and two
  // granules above it, and they are the bits the filter reads.
  let base : physaddrbits = plat_revocation_interval_base;
  assert(revocation_revoked(base));
  assert(not(revocation_revoked(base + 8)));
  assert(revocation_revoked(base + 16));

  // A second word is a second sixty-four granules and not a second structure.
  let _ = mem_write_value(Physaddr(zero_extend(plat_revocation_base + 8)), 8,
                          to_bits(64, 1), Store(Data), false, false);
  assert(revocation_revoked(base + (64 * 8)));

  // Doublewords only: the sweep and the kernel's retire path both work a word
  // at a time, and a narrower access would name a sub-word of a structure whose
  // index is a granule.
  match mem_read(Load(Data), window, 4, false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a narrow read of the revocation window must fault"),
  };

  revocation_bits = zeros();
}

// *****************************************************************
// The refresh and discharge sequencer.

// **The slave answers no requester at all** (R-15-247h). The mechanism is §12
// matter, sequenced by the RoT while every application core, DMA engine, and
// capability-bearing fabric initiator is held in reset, and a hart executing an
// instruction is by construction not in reset; so an access that reaches the
// window is the same fail-stop sentinel event a non-ON decode already is
// (R-15-189h, R-15-247k) rather than a door software may knock on.
//
// The contrast at the end is the point of claiming the window rather than
// leaving it unmapped: an IO address no device claims falls through to the RAM
// path and reads as zero (sys/mem.sail), which is silence and not a refusal, so
// a slave that means to refuse has to be in the map to do it.
$[test]
function test_the_sequencer_answers_no_requester() -> unit = {
  assert(plat_have_memory_sequencer);
  let door   = Physaddr(plat_memory_sequencer_base);
  let inside = Physaddr(plat_memory_sequencer_base + 0x0000000000000800);

  // Both directions, at every width a requester can name, at the window's first
  // address and inside it.
  match mem_read(Load(Data), door, 8, false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a doubleword read of the sequencer window must fault"),
  };
  match mem_read(Load(Data), door, 4, false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a word read of the sequencer window must fault"),
  };
  match mem_read(Load(Data), door, 1, false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a byte read of the sequencer window must fault"),
  };
  match mem_read(Load(Data), inside, 8, false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a read inside the sequencer window must fault"),
  };
  match mem_write_value(door, 8, zeros(), Store(Data), false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a doubleword write of the sequencer window must fault"),
  };
  match mem_write_value(inside, 8, ones(), Store(Data), false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a write inside the sequencer window must fault"),
  };

  // A capability-width access is refused on the same terms, so nothing is
  // reachable there under any authority whatever.
  match mem_read(Load(Data), door, cap_size, false, false) {
    Err(_, _) => (),
    Ok(_)     => assert(false, "a capability-width read of the sequencer window must fault"),
  };

  // And the refusal is the slave's rather than the address map's: one page above
  // the window is IO memory no device claims, and it answers.
  let unclaimed = Physaddr(plat_memory_sequencer_base + 0x0000000000010000);
  match mem_read(Load(Data), unclaimed, 8, false, false) {
    Ok(v)     => assert(v == zeros()),
    Err(_, _) => assert(false, "an unclaimed IO address reads rather than faults, which is what the window is claimed to prevent"),
  };
}

// **The refresh sweep finishes inside the retention floor**, which is the one
// arithmetic fact about the cadence that is not a matter of taste: a sweep
// slower than the floor is data lost on a schedule (R-15-247c, R-15-247g). What
// is asserted beside it is that the phase schedule is a partition of the class's
// banks, so that no bank is reached twice and none is left out, and that no
// phase exceeds the simultaneous-activation set the composition declared.
$[test]
function test_the_refresh_sweep_partitions_the_banks_and_meets_the_deadline() -> unit = {
  let banks  = memory_sequencer_banks();
  let per    = plat_memory_sequencer_refresh_banks_per_phase;
  let phases = memory_sequencer_refresh_phases();
  assert(banks > 0 & per > 0 & phases > 0);

  var covered : int = 0;
  foreach (p from 0 to (phases - 1)) {
    let count = memory_sequencer_phase_bank_count(per, p);
    assert(count > 0 & count <= per);
    assert(memory_sequencer_phase_first_bank(per, p) == covered);
    assert(memory_sequencer_phase_of_bank(per, covered) == p);
    covered = covered + count;
  };
  assert(covered == banks);

  // One phase past the end reaches nothing, which is what makes the sweep a
  // sweep rather than a walk off the end of the array.
  assert(memory_sequencer_phase_bank_count(per, phases) == 0);

  // The deadline, crossed into cycles at the spine ratio rather than the sweep
  // crossed down into whole microseconds, which could round a cadence into a
  // compliance it does not have.
  let second = memory_class_constants(SecondClass);
  assert(memory_sequencer_refresh_deadline_cycles() ==
         second.retention_floor_us * (plat_clock_frequency / 1000000));
  assert(memory_sequencer_refresh_period_cycles() < memory_sequencer_refresh_deadline_cycles());

  // And the deadline is the floor's and never the ceiling's, the corner being a
  // measured interval whose upper end no guarantee may rest on (R-15-247c).
  assert(memory_class_refresh_deadline_us(SecondClass) == second.retention_floor_us);
}

// **The discharge dwell is one data-independent constant** (R-15-247f): a fixed
// worst-corner dwell followed by a single read, with no poll-until-done loop, no
// retry, and no discharge-speed-dependent timing on either path. A poll would
// make transition time a function of temperature, charge state, and what the
// bank held, so what is asserted here is that filling the domain moves the
// budget by nothing at all.
$[test]
function test_the_mode_exit_dwell_is_one_data_independent_constant() -> unit = {
  let per = plat_memory_sequencer_discharge_banks_per_phase;
  let second = memory_class_constants(SecondClass);

  // A discharge asserts every write wordline in the bank where a refresh asserts
  // a row (R-15-247e), so its simultaneous-activation set is no larger, and each
  // phase interval covers the dwell it waits out.
  assert(per > 0 & per <= plat_memory_sequencer_refresh_banks_per_phase);
  assert(plat_memory_sequencer_discharge_phase_cycles >= second.discharge_cycles);

  let empty = memory_sequencer_mode_exit_cycles();
  assert(empty == memory_sequencer_discharge_phases() * plat_memory_sequencer_discharge_phase_cycles);
  assert(empty > 0);

  let bulk : xlenbits = 0x0000000100000000;
  let (_, region) = setCapBounds(root_data_cap, 0x100000000, 0b0 @ 0x100001000);
  let auth = setCapAddrChecked(region, bulk);
  C(encdec_reg(0b00011)) = setCapAddrChecked(root_data_cap, 0x0000000080000400);
  match cap_store(encdec_reg(0b00011), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "a capability store to the second class must succeed"),
  };
  let _ = mem_write_value(Physaddr(bulk + 64), 8, ones(), Store(Data), false, false);

  assert(memory_sequencer_mode_exit_cycles() == empty);
}

// **What the discharge removes is authority**, which is the whole reason it is
// on the exit path rather than the entry one (R-15-247d, R-15-247q): the tag
// plane is discharged and the discharge confirmed before any requester may name
// the domain, and a domain drained on the way out needs no clear on the way back
// in. The pass needs no mechanism of its own: it rides the write path, which is
// the model's reading of the cells' own write devices, so the tag of every
// granule it covers goes with the data (R-15-007r, R-15-247e).
$[test]
function test_a_discharged_bank_holds_no_authority_and_a_stop_is_not_retried() -> unit = {
  memory_sequencer_fail_stop = false;

  let bulk : xlenbits = 0x0000000100000000;
  let (_, region) = setCapBounds(root_data_cap, 0x100000000, 0b0 @ 0x100001000);
  let auth = setCapAddrChecked(region, bulk);
  C(encdec_reg(0b00011)) = setCapAddrChecked(root_data_cap, 0x0000000080000400);
  match cap_store(encdec_reg(0b00011), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "a capability store to the second class must succeed"),
  };
  match cap_load(encdec_reg(0b00100), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "the capability must load before the discharge"),
  };
  assert(C(encdec_reg(0b00100)).tag);

  let per   = plat_memory_sequencer_discharge_banks_per_phase;
  let bank : nat = match memory_sequencer_bank_of(bulk) {
    Some(b) => b,
    None()  => { assert(false, "the address under test is in the sequencer's domain"); 0 },
  };
  let phase = memory_sequencer_phase_of_bank(per, bank);
  assert(bank >= memory_sequencer_phase_first_bank(per, phase));
  assert(bank < memory_sequencer_phase_first_bank(per, phase) + memory_sequencer_phase_bank_count(per, phase));

  match memory_sequencer_discharge_phase(phase) {
    Seq_Confirmed => (),
    answer        => assert(false, "the exit-path discharge must confirm, and it answered " ^ to_str(answer)),
  };
  assert(not(memory_sequencer_fail_stop));

  // The granule is the all-zeroes untagged NULL R-15-182 and R-15-060 already
  // fix, so the state after a discharge is an architectural state with a defined
  // reading rather than whatever the array was left holding.
  match cap_load(encdec_reg(0b00100), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "the discharged granule must still load"),
  };
  assert(not(C(encdec_reg(0b00100)).tag));
  assert(C(encdec_reg(0b00100)) == null_cap);
  match mem_read(Load(Data), Physaddr(bulk), 8, false, false) {
    Ok(v)     => assert(v == zeros()),
    Err(_, _) => assert(false, "the discharged granule must read"),
  };

  // A latched fail-stop stops the transition rather than repeating it: there is
  // no retry on either path, so the domain that did not confirm does not enter
  // the mode (R-15-189n, R-15-247f).
  memory_sequencer_fail_stop = true;
  match memory_sequencer_discharge_phase(phase) {
    Seq_Stopped => (),
    answer      => assert(false, "a latched fail-stop is not retried, and it answered " ^ to_str(answer)),
  };
  memory_sequencer_fail_stop = false;
}

// *****************************************************************
// The two static latency classes.

// Main memory is two static latency classes under one placement discipline
// (R-15-247), so the class is a property of the region the static memory plan
// declared and never of an access. What is asserted here is the plan's shape
// and the query over it; what is asserted by *absence* is that no access path
// calls that query at all, a machine consulting the class at run time being the
// hierarchy the requirement refuses.
$[test]
function test_the_memory_plan_places_every_array_on_one_class() -> unit = {
  // Placement, in both directions and with a third answer beside them. An array
  // is on exactly one class, a device endpoint is on neither, and an address in
  // no region at all is not on a default class: the validator refuses a
  // configuration that gets either of the first two wrong, and this reads the
  // result back off the plan.
  match memory_class_at(Physaddr(0x0000000080000000)) {
    Some(FirstClass) => (),
    _                => assert(false, "the scalar working set is on the first class"),
  };
  match memory_class_at(Physaddr(0x0000000100000000)) {
    Some(SecondClass) => (),
    _                 => assert(false, "the bulk array is on the second class"),
  };
  match memory_class_at(Physaddr(zero_extend(plat_imsic_base))) {
    None() => (),
    _      => assert(false, "a device endpoint is on neither class"),
  };
  match memory_class_at(Physaddr(zeros())) {
    None() => (),
    _      => assert(false, "an address in no region is on no class"),
  };

  let first  = memory_class_constants(FirstClass);
  let second = memory_class_constants(SecondClass);

  // Two constants and not a hierarchy: the second class is the slower one on
  // both access constants, which is the difference R-15-247j makes visible to
  // admission when it prices second-class placement.
  assert(first.read_cycles > 0 & first.write_cycles > 0);
  assert(second.read_cycles >= first.read_cycles);
  assert(second.write_cycles >= first.write_cycles);

  // The record is symmetric and the machine is not, and the asymmetry is
  // R-15-247n's: the first class is latched, so its retention corner, its
  // refresh, and its discharge dwell are absent rather than small.
  assert(first.retention_floor_us == 0 & first.retention_ceiling_us == 0);
  assert(first.refresh_cycles == 0 & first.discharge_cycles == 0);
  assert(second.retention_floor_us > 0 & second.refresh_cycles > 0);
  assert(second.discharge_cycles > 0);

  // The corner is a measured interval rather than a point, and only its floor
  // is ever consumed: no guarantee may rest on a decay rate or on an upper
  // bound on retention, so the ceiling is carried for the qualification record
  // and read by nothing (R-15-247c, R-15-247m).
  assert(second.retention_floor_us <= second.retention_ceiling_us);
  assert(memory_class_refresh_deadline_us(SecondClass) == second.retention_floor_us);
  assert(memory_class_refresh_deadline_us(FirstClass) == 0);

  // And there is no separate fetch constant to state. R-15-164 deletes every
  // cache, so a fetch is a read of whichever class the code resides on and the
  // fetch constant R-15-247j prices against *is* the read constant.
  assert(memory_class_fetch_cycles(FirstClass) == first.read_cycles);
  assert(memory_class_fetch_cycles(SecondClass) == second.read_cycles);

  // Nothing is asserted about `qualified`, deliberately: its value is a fact
  // about whether R-15-247m's measurement has landed, so a property fixing it
  // would be a property about the calendar. What the model owes is that the
  // devicetree carries it (postlude/device_tree.sail), not that it is false.
}

// The class boundary is **latency-criticality and carries no trust gradient**
// (R-15-247s): tags, ECC, and the R-08-005 revocation load filter are identical
// across it, so no capability, compartment, or confidentiality label is
// weakened by residing on the second class and no TCB boundary tracks the
// memory boundary. The tag plane is the one structure that could have made it a
// trust boundary and does not, being native to each class's own array rather
// than a sidecar held in the faster one (R-15-247a, R-15-203).
$[test]
function test_a_capability_is_not_weakened_by_residing_on_the_second_class() -> unit = {
  let bulk : xlenbits = 0x0000000100000000;
  let (_, region) = setCapBounds(root_data_cap, 0x100000000, 0b0 @ 0x100001000);
  let auth = setCapAddrChecked(region, bulk);

  match memory_class_at(Physaddr(bulk)) {
    Some(SecondClass) => (),
    _                 => assert(false, "the address under test must be on the second class"),
  };

  // The capability stored here is one derived on the *first* class, so what the
  // round trip decides is whether the medium reaches the value. It does not:
  // the granule's own plane carries the tag, and the authority comes back whole.
  C(encdec_reg(0b00011)) = setCapAddrChecked(root_data_cap, 0x0000000080000400);
  match cap_store(encdec_reg(0b00011), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "a capability store to the second class must succeed"),
  };
  match cap_load(encdec_reg(0b00100), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "a capability load from the second class must succeed"),
  };
  assert(C(encdec_reg(0b00100)).tag);
  assert(C(encdec_reg(0b00100)) == C(encdec_reg(0b00011)));

  // And the write path clears a tag here exactly as it clears one there. Tag
  // clearing is a property of the write and not of the medium (R-15-007r), so
  // the second class neither preserves an authority a data store overwrote nor
  // loses one a capability store put down.
  let _ = mem_write_value(Physaddr(bulk), 8, zeros(), Store(Data), false, false);
  match cap_load(encdec_reg(0b00100), auth, 0b000010, bulk) {
    Retire_Success() => (),
    _                => assert(false, "the overwritten granule must still load"),
  };
  assert(not(C(encdec_reg(0b00100)).tag));

  // The block operations reach it on the same terms, which is what keeps
  // `cloadtags` at one cost model wherever the group it names resides
  // (R-15-007q): issue rather than traffic, on either class.
  C(encdec_reg(0b00010)) = auth;
  match execute(CBO_SCRUB(encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "a scrub of a second-class block must retire"),
  };
}

// The core classes and the roster.

// `mhartid` is the sole implementation identifier with a consumer, and what it
// is a consumer *of* is the roster (R-15-052b): one kernel binary runs
// unmodified on every core class and selects its per-hart state, the core's
// class, and the island binding out of it at boot. What is asserted here is that
// the identity and the table are one fact rather than two; what is asserted by
// **absence** is that no access path, no fault path, and no decode clause
// consults the class at all, a machine branching on its own class being the
// per-class ISA R-15-005 refuses (absence-contract A-17).
$[test]
function test_the_roster_fixes_the_hart_identity_space() -> unit = {
  // The composed hart is a row of the roster and not a value beside it. The
  // validator refuses a composition where it is not, so this reads the result
  // back off the plan.
  match this_core_entry() {
    None()      => assert(false, "the composed hart must be named by the roster"),
    Some(entry) => {
      assert(entry.hartid == plat_hartid);
      assert(unsigned(mhartid) == plat_hartid);
    },
  };

  // And an identity the roster does not name is not one this machine can
  // present, which is the other half of the same criterion: the lookup answers
  // `None` rather than a default class.
  match core_roster_lookup(core_roster, 999) {
    None()  => (),
    Some(_) => assert(false, "a hart identity outside the roster names no core"),
  };

  // Counts are composition parameters and not architecture (R-15-113), so no
  // count is declared and every class's count is the number of its entries. The
  // five counts therefore partition the roster exactly: a class gained or lost
  // here is a roster entry, and there is no second place for the two to disagree.
  let total = core_class_count(core_roster, CoreClass_C)
            + core_class_count(core_roster, CoreClass_V)
            + core_class_count(core_roster, CoreClass_M)
            + core_class_count(core_roster, CoreClass_S)
            + core_class_count(core_roster, CoreClass_RoT);
  assert(total == core_roster_size(core_roster));
  assert(core_roster_size(core_roster) > 0);

  // The index the generated devicetree writes the roster's class column as, and
  // its inverse, are a round trip over the whole enumeration (core_class.sail).
  // The tree emits the mapping beside the class nodes, so what decodes the
  // roster travels with it; this is what keeps the two ends of that agreeing.
  foreach (i from 0 to 4) {
    assert(core_class_to_index(core_class_of_index(i)) == i);
  };
}

// The class table says what kind of core each class is (R-15-113), and the
// asymmetry in it is the machine's rather than a composition's to choose. What
// the table may declare is held by the validator; what is held here is the
// reading a consumer gets back.
$[test]
function test_the_class_table_separates_the_vector_bearing_classes() -> unit = {
  // Three classes carry a vector datapath and two do not. The vectorless pair is
  // load-bearing rather than incidental: no vector permutation instruction is
  // reachable there, which is why the sentinel and the RoT hash SHA-3/SHAKE in
  // plain 64-bit integer with `Zbb` rotations rather than wanting a hardware
  // round unit (R-15-041, R-15-042, R-15-059, R-09-005a), and why `vmclear`
  // traps on a vectorless class like any unallocated encoding (R-15-069d).
  assert(core_class_is_vector_bearing(CoreClass_C));
  assert(core_class_is_vector_bearing(CoreClass_V));
  assert(core_class_is_vector_bearing(CoreClass_M));
  assert(not(core_class_is_vector_bearing(CoreClass_S)));
  assert(not(core_class_is_vector_bearing(CoreClass_RoT)));

  // The systolic array is one class's, and it is one array with two geometries
  // rather than two arrays: the unit consumes int8 and bf16 only, de-quantization
  // and microscaling block-scale application being software on the same class's
  // vector unit (R-15-116, R-15-117).
  assert(core_class_has_matrix(CoreClass_M));
  assert(not(core_class_has_matrix(CoreClass_C)));
  assert(not(core_class_has_matrix(CoreClass_V)));
  let m = core_class_datapath(CoreClass_M);
  assert(m.matrix_int8_dim > 0 & m.matrix_bf16_dim > 0);

  // Whatever a class may attach below the vector waterline, a vectorless one
  // attaches none of it, and a scalar core carries no local memory tier at all
  // (R-15-168).
  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    let d = core_class_datapath(c);
    if not(core_class_is_vector_bearing(c)) then {
      assert(d.lanes == 0 & d.scratchpad_bytes == 0);
      assert(not(d.keccak_unit));
      assert(not(core_class_has_matrix(c)));
    };
  };

  // The core-class table carries replication for the sentinel row alone
  // (R-16-008e): the detection-lockstepped pair presents one architectural core
  // whose comparator holds no architectural state, so it is a field of the class
  // and not a second hart in the roster (R-16-008d).
  assert(core_class_datapath(CoreClass_S).replicated);
  assert(not(core_class_datapath(CoreClass_C).replicated));
  assert(not(core_class_datapath(CoreClass_V).replicated));
  assert(not(core_class_datapath(CoreClass_M).replicated));
  assert(not(core_class_datapath(CoreClass_RoT).replicated));

  // Nothing is asserted about `frozen`, deliberately, for the reason nothing is
  // asserted about the memory classes' `qualified`: its value is a fact about
  // whether R-15-108's exploration has run, so a property fixing it would be a
  // property about the calendar. What the model owes is that the devicetree
  // carries it (postlude/device_tree.sail), not that it is false.
}

// One build realizes one vector length, `vlen_exp` being a Sail type-level
// configuration that sizes the vector register file (core/vlen.sail), so the
// class table cannot derive the geometry and the two are bound by a refusal
// instead (postlude/validate_config.sail). This is that refusal read back: the
// class the roster puts this hart on is the class this model was built as.
$[test]
function test_the_composed_hart_runs_the_geometry_its_class_declares() -> unit = {
  match this_core_entry() {
    None()      => assert(false, "the composed hart must be named by the roster"),
    Some(entry) => {
      let d = core_class_datapath(entry.class);
      assert(d.vlen_exp == sizeof(vlen_exp));
      assert(d.elen_exp == sizeof(elen_exp));
      // And from the other side: a class declaring a vector geometry is composed
      // onto a model whose vector extension is enabled, and a vectorless one is
      // not. A sentinel with a vector unit is the machine `vmclear`'s trap is
      // stated against (R-15-069d, R-07-014c).
      assert(core_class_is_vector_bearing(entry.class) == (vector_support_level != Disabled));
    },
  };
}
// The timing annotations.

// The obligations this platform states against the microarchitecture split by
// whether a model of architectural state can express them (R-15-089), and this
// file is the expressible half read back. What is asserted here is the table's
// shape and the one relation the register states inside it; what is asserted by
// **absence** is the whole of the rest, because a Sail model executes no cycles
// and can no more measure a latency than it can state that no branch predictor
// exists (R-15-098). The magnitudes are R-17-041's crown-jewel specification and
// none is measured, which is what `qualified` records.
$[test]
function test_every_operation_carries_a_latency() -> unit = {
  // Total by construction, the reader being a match over the enumeration, so
  // what a property can add is that no row is zero: every one is a term a WCET
  // derivation sums (R-11-015, R-18-024), and a zero contributes nothing to a
  // bound that has to be sound.
  assert(timing_cycles(Timing_Integer) > 0);
  assert(timing_cycles(Timing_Divide) > 0);
  assert(timing_cycles(Timing_Branch) > 0);
  assert(timing_cycles(Timing_Atomic) > 0);
  assert(timing_cycles(Timing_CapLoad) > 0);
  assert(timing_cycles(Timing_LoadTags) > 0);
  assert(timing_cycles(Timing_Reclaim) > 0);
  assert(timing_cycles(Timing_BlockZero) > 0);
  assert(timing_cycles(Timing_BlockScrub) > 0);
  assert(timing_cycles(Timing_VectorFloat) > 0);

  // The one relation the register states between two rows, and it is a shape
  // rather than a value: the off-list vector access enters at its
  // fully-conflicted bound, every element resolving to one bank, where the
  // on-list one's bank sequence follows from the element width and a
  // granule-aligned base alone (R-15-085a, R-15-085b).
  assert(timing_cycles(Timing_VectorMemIndexed) >= timing_cycles(Timing_VectorMemUnit));

  // Reading twice answers twice the same, which is the whole of what a model
  // with no cycle counter can say about data independence beyond the signature
  // that carries it: `timing_cycles` takes an operation class and takes no
  // operand, no register, no address, and no prior state, so there is nowhere
  // for a value to enter it (R-15-053, R-15-095).
  assert(timing_cycles(Timing_Divide) == timing_cycles(Timing_Divide));
}

// The two tables meet at one function and neither restates the other's constants
// (R-15-247, R-15-247j). A memory access costs the pipeline's own term plus the
// fixed constant of the class its region is placed on, so the delta §11 charges
// a second-class placement is the difference of two array constants and nothing
// about the instruction changes across the boundary.
$[test]
function test_a_placement_moves_only_the_array_term() -> unit = {
  let first  = memory_class_constants(FirstClass).read_cycles;
  let second = memory_class_constants(SecondClass).read_cycles;

  assert(timing_access_cycles(Timing_Load, FirstClass)
         == timing_cycles(Timing_Load) + first);
  assert(timing_access_cycles(Timing_Load, SecondClass)
         == timing_cycles(Timing_Load) + second);

  // The delta is the classes' and not the operation's, which is why the same
  // difference falls out whichever operation is priced.
  assert(timing_access_cycles(Timing_Load, SecondClass)
         - timing_access_cycles(Timing_Load, FirstClass)
         == timing_access_cycles(Timing_CapLoad, SecondClass)
            - timing_access_cycles(Timing_CapLoad, FirstClass));
}

// The partition switch costs three terms and no fourth (R-15-220), and two of
// them are here: the padded `fence.t` constant and the eager vector and matrix
// zeroize. The third is the operating-point relock, which is a property of the
// rail and the mode schedule rather than of anything the machine executes
// (R-11-017), so this model carries two and says which two.
$[test]
function test_the_switch_costs_the_fence_and_the_zeroize() -> unit = {
  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    let t = core_class_timing(c);
    assert(partition_switch_cycles(c) == t.vmclear_cycles + t.fence_t_cycles);

    // The fence is core surface on every class and completes at its bound rather
    // than early, so every class carries the constant (R-15-218). The zeroize is
    // the class's own: on a vectorless class `vmclear` traps like any
    // unallocated encoding, so there is no pass to cost and the switch is the
    // fence alone (R-15-069d, R-07-014c).
    assert(t.fence_t_cycles > 0);
    if core_class_is_vector_bearing(c) then {
      assert(t.vmclear_cycles > 0);
    } else {
      assert(t.vmclear_cycles == 0);
      assert(partition_switch_cycles(c) == t.fence_t_cycles);
    };
  };

  // Nothing is asserted about `qualified`, deliberately, for the reason nothing
  // is asserted about the memory classes': its value is a fact about whether the
  // measurement has landed, so a property fixing it would be a property about
  // the calendar.
}