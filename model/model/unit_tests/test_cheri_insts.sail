// Properties of the capability instruction surface
// (extensions/CHERI/cheri_insts.sail and cheri_mem.sail).
//
// These are the transplant's standing regression, as the algebra's are
// (test_capability.sail): the differential harness compares this model against
// the M0.4 oracle over whole programs, and these are what a change to one
// instruction is caught by without one. M0.6f narrows the surface, and every
// property here that survives the narrowing must still pass.

// A capability-mode PCC reads `jalr` as `cjalr` and an integer-mode one reads it
// as `jalr`. The two decodes are over the same encoding, which is why capability
// mode needs a second mapping rather than a second opcode
// (postlude/decode_ext.sail).
$[test]
function test_capability_mode_redecodes_the_control_transfers() -> unit = {
  // jalr c1, 0(c2) / jalr x1, 0(x2)
  let insn : word = 0x00010_0e7;
  PCC = setCapFlags(default_cap, 0b1);
  match ext_decode(insn) {
    CJALR(_, _, _) => (),
    _              => assert(false, "capability mode must decode jalr as cjalr"),
  };
  // auipc and jal are the other two, and every other encoding falls through to
  // the ordinary decode.
  match ext_decode(0x00001_097) {
    AUIPCC(_, _) => (),
    _            => assert(false, "capability mode must decode auipc as auipcc"),
  };
  match ext_decode(0x0080_006f) {
    CJAL(_, _) => (),
    _          => assert(false, "capability mode must decode jal as cjal"),
  };
  match ext_decode(0x00208_033) {
    RTYPE(_, _, _, _) => (),
    _                 => assert(false, "capability mode must not redecode add"),
  };
  PCC = default_cap;
  match ext_decode(insn) {
    JALR(_, _, _) => (),
    _             => assert(false, "integer mode must decode jalr as jalr"),
  };
}

// The forward and backward edges of a capability call are one instruction: the
// target is unsealed into the executing PCC and the return address is written
// back already sealed, so there is no separate call gate and a return capability
// is a control-flow target exactly once (R-15-008, R-15-068, R-15-071).
$[test]
function test_cjalr_unseals_the_target_and_seals_the_return() -> unit = {
  let (_, region) = setCapBounds(default_cap, 0x0000000080000000, 0b0 @ 0x0000000080001000);
  PCC = setCapFlags(setCapAddrChecked(region, 0x0000000080000000), 0b1);
  PC = 0x0000000080000000;
  nextPC = 0x0000000080000004;

  let target = sealCap(setCapAddrChecked(region, 0x0000000080000800), otype_sentry_bits);
  C(encdec_reg(0b00010)) = target;

  match execute(CJALR(zeros(), encdec_reg(0b00010), encdec_reg(0b00001))) {
    Retire_Success() => (),
    _                => assert(false, "a sentry target must be callable"),
  };
  assert(nextPC == 0x0000000080000800);
  assert(not(isCapSealed(nextPCC)));
  assert(nextPCC.tag);

  let link = C(encdec_reg(0b00001));
  assert(link.tag);
  assert(link.otype == otype_sentry_bits);
  assert(link.address == 0x0000000080000004);

  // Any other sealed type is a seal violation, and so is a non-zero
  // displacement onto a sentry: a sentry names its entry point and nothing
  // near it.
  C(encdec_reg(0b00010)) = sealCap(setCapAddrChecked(region, 0x0000000080000800), to_bits(3));
  match execute(CJALR(zeros(), encdec_reg(0b00010), encdec_reg(0b00001))) {
    Ext_ControlAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_SealViolation),
    _ => assert(false, "a sealed non-sentry target must fault"),
  };
  C(encdec_reg(0b00010)) = target;
  match execute(CJALR(0x004, encdec_reg(0b00010), encdec_reg(0b00001))) {
    Ext_ControlAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_SealViolation),
    _ => assert(false, "a displaced sentry call must fault"),
  };
  PCC = default_cap;
}

// The derivations are monotone or they are untagged. A narrowing that would
// widen its input, an offset that leaves the representable region, and a
// permission mask that would add a permission all yield a result whose tag is
// clear, and none of them traps: a failed derivation is a data result that
// faults at its next dereference (R-15-007h).
$[test]
function test_a_widening_derivation_yields_an_untagged_result() -> unit = {
  let (_, region) = setCapBounds(default_cap, 0x0000000080000000, 0b0 @ 0x0000000080001000);
  let c = setCapAddrChecked(region, 0x0000000080000000);
  C(encdec_reg(0b00010)) = c;

  // A narrowing inside the input keeps the tag.
  X(encdec_reg(0b00011)) = 0x0000000000000100;
  match execute(CSetBounds(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "csetbounds must not trap"),
  };
  assert(C(encdec_reg(0b00100)).tag);
  assert(getCapLength(C(encdec_reg(0b00100))) == 256);

  // A narrowing past its top does not.
  X(encdec_reg(0b00011)) = 0x0000000000002000;
  match execute(CSetBounds(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "an over-wide csetbounds must not trap"),
  };
  assert(not(C(encdec_reg(0b00100)).tag));

  // An offset far outside the representable region does not either.
  X(encdec_reg(0b00011)) = 0x0000000040000000;
  match execute(CIncOffset(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "cincoffset must not trap"),
  };
  assert(not(C(encdec_reg(0b00100)).tag));

  // `candperm` masks and cannot set: a mask of all ones leaves the input alone
  // and a mask of zeroes strips it, whatever the input held.
  C(encdec_reg(0b00010)) = setCapPerms(c, zeros());
  X(encdec_reg(0b00011)) = ones();
  match execute(CAndPerm(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "candperm must not trap"),
  };
  assert(getCapPerms(C(encdec_reg(0b00100))) == zeros());
  assert(C(encdec_reg(0b00100)).tag);
}

// A sentry is minted by `csealentry` and read back by `cgettype`, and sealing an
// already-sealed capability clears the tag rather than re-sealing it.
$[test]
function test_csealentry_and_cgettype() -> unit = {
  C(encdec_reg(0b00010)) = default_cap;
  match execute(CSealEntry(encdec_reg(0b00011), encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "csealentry must not trap"),
  };
  assert(C(encdec_reg(0b00011)).tag);
  assert(isCapSealed(C(encdec_reg(0b00011))));

  match execute(CGetType(encdec_reg(0b00100), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "cgettype must not trap"),
  };
  // A reserved object type reads as the negative architectural value it stands
  // for, so a sentry is -2 and an unsealed capability is -1.
  assert(X(encdec_reg(0b00100)) == ones() - 1);

  match execute(CSealEntry(encdec_reg(0b00101), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "csealentry over a sealed input must not trap"),
  };
  assert(not(C(encdec_reg(0b00101)).tag));
}

// A capability survives a store and a load with its tag, and a load through an
// authority without load-capability permission delivers it untagged rather than
// faulting: the cleared tag is one of the load's defined results, which is what
// lets the revocation filter be an architectural result rather than an effect
// layered on the instruction (R-08-005b).
$[test]
function test_a_capability_round_trips_through_memory() -> unit = {
  let addr : xlenbits = 0x0000000080000000;
  let (_, region) = setCapBounds(default_cap, addr, 0b0 @ 0x0000000080001000);
  let auth = setCapAddrChecked(region, addr);
  let value = setCapAddrChecked(region, addr + 64);
  assert(value.tag);

  C(encdec_reg(0b00011)) = value;
  match cap_store(encdec_reg(0b00011), auth, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "an in-bounds capability store must succeed"),
  };
  match cap_load(encdec_reg(0b00100), auth, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "an in-bounds capability load must succeed"),
  };
  assert(C(encdec_reg(0b00100)) == value);

  match cap_load(encdec_reg(0b00101), { auth with permit_load_cap = false }, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "a load without load-capability must not fault"),
  };
  assert(not(C(encdec_reg(0b00101)).tag));
  assert(C(encdec_reg(0b00101)).address == value.address);
}

// The store side has no such clause: storing a tagged capability through an
// authority that cannot carry one faults, and so does storing a local
// capability through an authority without store-local (R-15-074). Storing an
// untagged value through either is data and is permitted.
$[test]
function test_a_capability_store_needs_the_capability_permissions() -> unit = {
  let addr : xlenbits = 0x0000000080000000;
  let (_, region) = setCapBounds(default_cap, addr, 0b0 @ 0x0000000080001000);
  let auth = setCapAddrChecked(region, addr);
  let value = setCapAddrChecked(region, addr + 64);

  C(encdec_reg(0b00011)) = value;
  match cap_store(encdec_reg(0b00011), { auth with permit_store_cap = false }, 0b000010, addr) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_PermitStoreCapViolation);
      assert(idx == 0b000010);
    },
    _ => assert(false, "storing a tagged capability without store-capability must fault"),
  };

  C(encdec_reg(0b00011)) = { value with global = false };
  match cap_store(encdec_reg(0b00011), { auth with permit_store_local_cap = false }, 0b000010, addr) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitStoreLocalCapViolation),
    _ => assert(false, "storing a local capability without store-local must fault"),
  };

  C(encdec_reg(0b00011)) = clearTag(value);
  match cap_store(encdec_reg(0b00011), { auth with permit_store_cap = false }, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "storing data needs only store permission"),
  };
}

// A capability access is always naturally aligned and always bounds-checked at
// the capability width, whatever the platform admits for data: a capability
// straddling a granule boundary would have no tag of its own (R-15-203).
$[test]
function test_a_capability_access_is_aligned_and_width_checked() -> unit = {
  let addr : xlenbits = 0x0000000080000000;
  let (_, region) = setCapBounds(default_cap, addr, 0b0 @ 0x0000000080001000);
  let auth = setCapAddrChecked(region, addr);

  match cap_load(encdec_reg(0b00100), auth, 0b000010, addr + 8) {
    Trap(_, _) => (),
    _          => assert(false, "a misaligned capability load must fault"),
  };

  // The last capability inside the region fits; one past it does not, and the
  // bound is checked over the whole capability rather than over its first byte.
  match cap_load(encdec_reg(0b00100), auth, 0b000010, 0x0000000080000ff0) {
    Retire_Success() => (),
    _                => assert(false, "the last capability in the region must load"),
  };
  match cap_load(encdec_reg(0b00100), auth, 0b000010, 0x0000000080001000) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_LengthViolation),
    _ => assert(false, "a capability load past the top must fault"),
  };
}

// The tag group is reported as stored: `cloadtags` answers with the validity
// tags of the granules of one CBO block, and a granule whose capability was
// overwritten with data reads back clear, tag clearing being a property of the
// write path (R-15-007q, R-15-007r).
$[test]
function test_cloadtags_reports_the_tags_as_stored() -> unit = {
  let addr : xlenbits = 0x0000000080000000;
  let (_, region) = setCapBounds(default_cap, addr, 0b0 @ 0x0000000080001000);
  let auth = setCapAddrChecked(region, addr);
  let value = setCapAddrChecked(region, addr + 64);

  // Fill the block with capabilities, then overwrite the second granule with
  // data through an ordinary store.
  C(encdec_reg(0b00011)) = value;
  foreach (i from 0 to (caps_per_block - 1)) {
    match cap_store(encdec_reg(0b00011), auth, 0b000010, addr + (i * cap_size)) {
      Retire_Success() => (),
      _                => assert(false, "filling the block must succeed"),
    }
  };
  let _ = mem_write_value(physical_address(Virtaddr(addr + cap_size)), 8, zeros(), Store(Data), false, false);

  C(encdec_reg(0b00010)) = auth;
  match execute(CLoadTags(encdec_reg(0b00100), encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "cloadtags over an authorised block must succeed"),
  };
  let tags = X(encdec_reg(0b00100))[caps_per_block - 1 .. 0];
  assert(tags == (ones() ^ (zero_extend(0b1) << 1)));

  // It faults rather than answering zeroes where the authority cannot load
  // capabilities: an answer of no tags would be indistinguishable from an empty
  // block, and the sweep that read it would miss every capability in it.
  C(encdec_reg(0b00010)) = { auth with permit_load_cap = false };
  match execute(CLoadTags(encdec_reg(0b00100), encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitLoadCapViolation),
    _ => assert(false, "cloadtags without load-capability must fault"),
  };
}

// Privilege is the capability: the trap capabilities are reachable only with
// the access-system-registers permission on the executing PCC, and PCC itself
// is readable but not writable (R-15-003, R-15-073).
$[test]
function test_cspecialrw_is_gated_by_the_capability() -> unit = {
  PCC = default_cap;
  MTDC = null_cap;
  C(encdec_reg(0b00010)) = default_cap;

  match execute(CSpecialRW(encdec_reg(0b00011), 0b11101, encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "a write to MTDC under ASR must succeed"),
  };
  assert(MTDC == default_cap);
  assert(C(encdec_reg(0b00011)) == null_cap);

  // Without the permission the same write is a capability violation naming the
  // special register rather than a general-purpose one.
  PCC = { default_cap with access_system_regs = false };
  match execute(CSpecialRW(encdec_reg(0b00011), 0b11101, encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_AccessSystemRegsViolation);
      assert(idx == 0b111101);
    },
    _ => assert(false, "a write to MTDC without ASR must fault"),
  };
  PCC = default_cap;

  // PCC is read-only, and a number the bank does not carry is illegal.
  match execute(CSpecialRW(encdec_reg(0b00011), 0b00000, encdec_reg(0b00010))) {
    Illegal_Instruction() => (),
    _                     => assert(false, "PCC must not be writable"),
  };
  match execute(CSpecialRW(encdec_reg(0b00011), 0b11110, zreg)) {
    Illegal_Instruction() => (),
    _                     => assert(false, "an absent special register must be illegal"),
  };
}

// `cclear` destroys authority by mask and can do nothing else: it is the one
// instruction whose every result is smaller than its input, which is what makes
// its monotonicity trivial rather than argued (R-15-069a).
$[test]
function test_cclear_clears_by_mask() -> unit = {
  C(encdec_reg(0b01000)) = default_cap;
  C(encdec_reg(0b01001)) = default_cap;
  C(encdec_reg(0b01010)) = default_cap;

  // The second half, bits 0 and 2: registers 8 and 10.
  match execute(CClear(0b01, 0b00000101)) {
    Retire_Success() => (),
    _                => assert(false, "cclear must not trap"),
  };
  assert(C(encdec_reg(0b01000)) == null_cap);
  assert(C(encdec_reg(0b01001)) == default_cap);
  assert(C(encdec_reg(0b01010)) == null_cap);

  // Bit 0 of the first half names DDC rather than the zero register, which has
  // nothing to clear.
  DDC = default_cap;
  match execute(CClear(0b00, 0b00000001)) {
    Retire_Success() => (),
    _                => assert(false, "cclear over DDC must not trap"),
  };
  assert(DDC == null_cap);
  DDC = default_cap;
}
