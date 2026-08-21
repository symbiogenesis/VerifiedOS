// Properties of the platform surface the profile adds and no upstream model
// carries: `fence.t` (extensions/platform/fence_t.sail), `vmclear` and
// `cbo.scrub` beside it, the machine-level interrupt file, the revocation
// sidecar's register slave (sys/platform.sail, core/revocation.sail), and the
// two static latency classes of main memory (core/memory_class.sail).
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
