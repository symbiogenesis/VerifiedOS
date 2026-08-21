// Properties of the capability instruction surface
// (extensions/CHERI/cheri_insts.sail and cheri_mem.sail).
//
// These are the surface's standing regression, as the algebra's are
// (test_capability.sail), and with `riscv-tests` no longer a corpus this
// machine can run they are also the only programs exercising it until M0.12's
// purecap corpus exists.

// *****************************************************************
// Control transfers.

// There is one decode: the base encodings of `auipc`, `jal` and `jalr` have
// only their capability reading, so no mode selects between two of them
// (postlude/decode_ext.sail, R-15-001).
$[test]
function test_the_control_transfers_decode_as_capability_forms() -> unit = {
  PCC = default_cap;
  // jalr c1, 0(c2)
  match ext_decode(0x00010_0e7) {
    CJALR(_, _, _) => (),
    _              => assert(false, "jalr must decode as cjalr"),
  };
  match ext_decode(0x00001_097) {
    AUIPCC(_, _) => (),
    _            => assert(false, "auipc must decode as auipcc"),
  };
  match ext_decode(0x0080_006f) {
    CJAL(_, _) => (),
    _          => assert(false, "jal must decode as cjal"),
  };
  match ext_decode(0x00208_033) {
    RTYPE(_, _, _, _) => (),
    _                 => assert(false, "an integer op must not be redecoded"),
  };
}

// The forward and backward edges of a capability call are one instruction: the
// target is unsealed into the executing PCC and the return address is written
// back already sealed, so there is no separate call gate and a return
// capability is a control-flow target exactly once (R-15-008, R-15-068).
//
// The split is enforced by *role*: a jump that writes a link is a call and may
// enter only a forward-edge sentry, and a return address, sealed as the
// backward edge, is reachable only by a jump that writes none. So a forged or
// replayed return address cannot be called and a function pointer cannot be
// returned to (R-15-071).
$[test]
function test_cjalr_enforces_the_sentry_split() -> unit = {
  let (_, region) = setCapBounds(default_cap, 0x080000000, 0b0 @ 0x080001000);
  PCC = setCapAddrChecked(region, 0x0000000080000000);
  PC = 0x0000000080000000;
  nextPC = 0x0000000080000004;

  let entry = setCapAddrChecked(region, 0x0000000080000800);
  let fwd = sealCap(entry, otype_sentry_fwd_bits);
  let bwd = sealCap(entry, otype_sentry_bwd_bits);

  // A call into a forward-edge sentry unseals it and links a backward edge.
  C(encdec_reg(0b00010)) = fwd;
  match execute(CJALR(zeros(), encdec_reg(0b00010), encdec_reg(0b00001))) {
    Retire_Success() => (),
    _                => assert(false, "a forward sentry must be callable"),
  };
  assert(nextPC == 0x0000000080000800);
  assert(not(isCapSealed(nextPCC)));
  assert(nextPCC.tag);

  let link = C(encdec_reg(0b00001));
  assert(link.tag);
  assert(link.otype == otype_sentry_bwd_bits);
  assert(link.address == 0x080000004);

  // The same call into a *return address* is a seal violation.
  C(encdec_reg(0b00010)) = bwd;
  match execute(CJALR(zeros(), encdec_reg(0b00010), encdec_reg(0b00001))) {
    Ext_ControlAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_SealViolation),
    _ => assert(false, "a backward sentry must not be callable"),
  };

  // A jump that writes no link returns to it.
  match execute(CJALR(zeros(), encdec_reg(0b00010), zreg)) {
    Retire_Success() => (),
    _                => assert(false, "a backward sentry must be returnable to"),
  };
  assert(nextPC == 0x0000000080000800);
  assert(not(isCapSealed(nextPCC)));

  // Any other sealed type is a seal violation, and so is a non-zero
  // displacement onto a sentry: a sentry names its entry point and nothing
  // near it.
  C(encdec_reg(0b00010)) = sealCap(entry, to_bits(3));
  match execute(CJALR(zeros(), encdec_reg(0b00010), encdec_reg(0b00001))) {
    Ext_ControlAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_SealViolation),
    _ => assert(false, "a sealed non-sentry target must fault"),
  };
  C(encdec_reg(0b00010)) = fwd;
  match execute(CJALR(0x004, encdec_reg(0b00010), encdec_reg(0b00001))) {
    Ext_ControlAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_SealViolation),
    _ => assert(false, "a displaced sentry call must fault"),
  };
  PCC = default_cap;
}

// *****************************************************************
// Derivations.

// The derivations are monotone or they are untagged. A narrowing that would
// widen its input, an offset that leaves the representable region, and a
// permission mask that would add a permission all yield a result whose tag is
// clear, and none of them traps: a failed derivation is a data result that
// faults at its next dereference (R-15-007h).
$[test]
function test_a_widening_derivation_yields_an_untagged_result() -> unit = {
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
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
  // and a mask of zeroes strips it to the lattice's bottom, whatever the input
  // held.
  C(encdec_reg(0b00010)) = c;
  X(encdec_reg(0b00011)) = ones();
  match execute(CAndPerm(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "candperm must not trap"),
  };
  assert(getCapPerms(C(encdec_reg(0b00100))) == getCapPerms(c));
  assert(C(encdec_reg(0b00100)).tag);

  X(encdec_reg(0b00011)) = zeros();
  match execute(CAndPerm(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "candperm must not trap"),
  };
  assert(getCapPerms(C(encdec_reg(0b00100))) == zeros());
  assert(C(encdec_reg(0b00100)).tag);
}

// A sentry is minted by `csealentry` and read back by `cgettype`, and sealing an
// already-sealed capability clears the tag rather than re-sealing it. What
// software can mint is the *forward* edge only: a return address is minted by
// the call, which is what keeps it out of software's gift (R-15-071).
$[test]
function test_csealentry_and_cgettype() -> unit = {
  C(encdec_reg(0b00010)) = default_cap;
  match execute(CSealEntry(encdec_reg(0b00011), encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "csealentry must not trap"),
  };
  assert(C(encdec_reg(0b00011)).tag);
  assert(isCapSealed(C(encdec_reg(0b00011))));
  assert(C(encdec_reg(0b00011)).otype == otype_sentry_fwd_bits);

  match execute(CGetType(encdec_reg(0b00100), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "cgettype must not trap"),
  };
  // A reserved object type reads as the negative architectural value it stands
  // for, so an unsealed capability is -1, a forward-edge sentry -2, and a
  // backward-edge sentry -3.
  assert(X(encdec_reg(0b00100)) == ones() - 1);

  match execute(CSealEntry(encdec_reg(0b00101), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "csealentry over a sealed input must not trap"),
  };
  assert(not(C(encdec_reg(0b00101)).tag));
}

// *****************************************************************
// Memory.

// A capability survives a store and a load with its tag, and a load through an
// authority without load-capability permission delivers it untagged rather than
// faulting: the cleared tag is one of the load's defined results, which is what
// lets the revocation filter be an architectural result rather than an effect
// layered on the instruction (R-08-005b).
$[test]
function test_a_capability_round_trips_through_memory() -> unit = {
  let addr : xlenbits = 0x0000000080000000;
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
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

  let no_load_cap = { auth with perms = perms_rw | perms_global_bit };
  match cap_load(encdec_reg(0b00101), no_load_cap, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "a load without load-capability must not fault"),
  };
  assert(not(C(encdec_reg(0b00101)).tag));
  assert(C(encdec_reg(0b00101)).address == value.address);
}

// The load's transitivity: what comes back is bounded by what the authority is
// willing to pass on (R-15-074). Without `load-global` the result is local, so
// authority read through a local view cannot be stored anywhere long-lived;
// without `load-mutable` it loses its store permissions. Both land on a
// codepoint rather than below one, the read half of every admitted permission
// set being itself an admitted set.
$[test]
function test_a_load_strips_what_the_authority_withholds() -> unit = {
  let addr : xlenbits = 0x0000000080000200;
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let auth = setCapAddrChecked(region, addr);
  let value = setCapAddrChecked(region, addr + 64);

  C(encdec_reg(0b00011)) = value;
  match cap_store(encdec_reg(0b00011), auth, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "the store must succeed"),
  };

  // `perms_rw_cap` carries neither load-global nor load-mutable.
  let strip = { auth with perms = perms_rw_cap | perms_global_bit };
  match cap_load(encdec_reg(0b00100), strip, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "the load must succeed"),
  };
  let got = C(encdec_reg(0b00100));
  assert(got.tag);
  assert(not(cap_global(got)));
  assert(not(cap_permit_store(got)));
  assert(not(cap_store_cap(got)));
  assert(cap_permit_load(got));
  assert(capBoundsEqual(got, value));

  // An untagged value is data and survives the load unchanged, or an integer
  // would not round-trip through memory.
  C(encdec_reg(0b00011)) = int_to_cap(0x0123456789abcdef);
  match cap_store(encdec_reg(0b00011), auth, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "storing data must succeed"),
  };
  match cap_load(encdec_reg(0b00100), strip, 0b000010, addr) {
    Retire_Success() => (),
    _                => assert(false, "loading data must succeed"),
  };
  assert(X(encdec_reg(0b00100)) == 0x0123456789abcdef);
}

// The store side has no such clause: storing a tagged capability through an
// authority that cannot carry one faults, and so does storing a local
// capability through an authority without store-local (R-15-074). Storing an
// untagged value through either is data and is permitted.
$[test]
function test_a_capability_store_needs_the_capability_permissions() -> unit = {
  let addr : xlenbits = 0x0000000080000000;
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let auth = setCapAddrChecked(region, addr);
  let value = setCapAddrChecked(region, addr + 64);

  let no_store_cap = { auth with perms = perms_rw | perms_global_bit };
  C(encdec_reg(0b00011)) = value;
  match cap_store(encdec_reg(0b00011), no_store_cap, 0b000010, addr) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_PermitStoreCapViolation);
      assert(idx == 0b000010);
    },
    _ => assert(false, "storing a tagged capability without store-capability must fault"),
  };

  // The data root carries store-local; `perms_data_root` is the same shape
  // without it, which is the one distinction the stack's own capability makes.
  let no_store_local = { auth with perms = perms_data_root | perms_global_bit };
  C(encdec_reg(0b00011)) = { value with perms = perms_data_root };
  match cap_store(encdec_reg(0b00011), no_store_local, 0b000010, addr) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitStoreLocalCapViolation),
    _ => assert(false, "storing a local capability without store-local must fault"),
  };

  C(encdec_reg(0b00011)) = clearTag(value);
  match cap_store(encdec_reg(0b00011), no_store_cap, 0b000010, addr) {
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
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let auth = setCapAddrChecked(region, addr);

  match cap_load(encdec_reg(0b00100), auth, 0b000010, addr + 4) {
    Trap(_, _) => (),
    _          => assert(false, "a misaligned capability load must fault"),
  };

  // The last capability inside the region fits; one past it does not, and the
  // bound is checked over the whole capability rather than over its first byte.
  match cap_load(encdec_reg(0b00100), auth, 0b000010, 0x0000000080000ff8) {
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
  let addr : xlenbits = 0x0000000080000400;
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let auth = setCapAddrChecked(region, addr);
  let value = setCapAddrChecked(region, addr + 64);

  // The block holds eight granules at the frozen format's width.
  assert(caps_per_block == 8);

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
  C(encdec_reg(0b00010)) = { auth with perms = perms_rw | perms_global_bit };
  match execute(CLoadTags(encdec_reg(0b00100), encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitLoadCapViolation),
    _ => assert(false, "cloadtags without load-capability must fault"),
  };
}

// *****************************************************************
// The rows M0.6g adds: the conditional capability move, the masked register
// clear, the indexed access, and the revocation filter.

// The conditional capability move writes the destination **whole**, tag
// included, on the taken arm and leaves it untouched on the other (R-15-054a).
// That is what separates it from `Zicond`: an integer select can zero one arm
// and OR the two together, and the recombining `or` would be reconstruction
// from a bit pattern, which the profile forbids at the root (R-15-054,
// R-05-136).
$[test]
function test_the_conditional_capability_move_carries_the_whole_register() -> unit = {
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let value = setCapAddrChecked(region, 0x0000000080000040);
  assert(value.tag);

  // Taken: the destination becomes the source, tag and all.
  C(encdec_reg(0b00010)) = value;
  C(encdec_reg(0b00100)) = null_cap;
  X(encdec_reg(0b00011)) = zeros();
  match execute(CMOVZ(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "cmovz must not trap"),
  };
  assert(C(encdec_reg(0b00100)) == value);

  // Not taken: the destination is untouched, which is a stronger statement than
  // *unchanged in value* — nothing is written, so a tagged destination keeps its
  // own authority rather than being rewritten with it.
  C(encdec_reg(0b00100)) = null_cap;
  X(encdec_reg(0b00011)) = 0x0000000000000001;
  match execute(CMOVZ(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "an untaken cmovz must not trap"),
  };
  assert(C(encdec_reg(0b00100)) == null_cap);

  // `cmovn` is the complementary condition on the same operands.
  match execute(CMOVN(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "cmovn must not trap"),
  };
  assert(C(encdec_reg(0b00100)) == value);

  C(encdec_reg(0b00100)) = null_cap;
  X(encdec_reg(0b00011)) = zeros();
  match execute(CMOVN(encdec_reg(0b00100), encdec_reg(0b00010), encdec_reg(0b00011))) {
    Retire_Success() => (),
    _                => assert(false, "an untaken cmovn must not trap"),
  };
  assert(C(encdec_reg(0b00100)) == null_cap);
}

// `cclear h, mask` clears the sixteen registers the mask selects within the half
// `h` selects, each to the all-zeroes granule that decodes as untagged NULL, so
// two of them clear the merged file (R-15-069a, R-15-182). It is the one
// instruction on the machine that can only ever destroy authority.
$[test]
function test_cclear_clears_exactly_the_registers_the_mask_names() -> unit = {
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let value = setCapAddrChecked(region, 0x0000000080000080);

  foreach (i from 1 to 31) {
    C(zreg + i) = value
  };

  // Registers 4 through 7 of the low half.
  match execute(CClear(0b0, 0x00F0)) {
    Retire_Success() => (),
    _                => assert(false, "cclear must not trap"),
  };
  foreach (i from 1 to 31) {
    if 4 <= i & i <= 7 then {
      assert(C(zreg + i) == null_cap);
      assert(not(C(zreg + i).tag));
    } else {
      assert(C(zreg + i) == value)
    }
  };

  // The half selector moves the same sixteen positions up the file: bit 0 of the
  // mask names x16 rather than x0.
  match execute(CClear(0b1, 0x0003)) {
    Retire_Success() => (),
    _                => assert(false, "cclear over the high half must not trap"),
  };
  assert(C(zreg + 16) == null_cap);
  assert(C(zreg + 17) == null_cap);
  assert(C(zreg + 18) == value);

  // An empty mask clears nothing, and its latency is the same as a full mask's:
  // the instruction is unconditional and its worst case is its every case
  // (R-15-069b).
  match execute(CClear(0b0, zeros())) {
    Retire_Success() => (),
    _                => assert(false, "an empty cclear must not trap"),
  };
  assert(C(zreg + 8) == value);
}

// The indexed access checks the authorising capability at **base plus scaled
// index** and performs the access there, with no intermediate capability
// materialized at any point (R-15-007e, R-15-007f). The two consequences are
// checked together, because the second is the reason for the first: an index
// far outside the representable region is a *length violation on the authority*
// rather than an untagged intermediate that faults one instruction later.
$[test]
function test_the_indexed_access_checks_at_base_plus_scaled_index() -> unit = {
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let auth = setCapAddrChecked(region, 0x0000000080000000);
  C(encdec_reg(0b01000)) = auth;

  // Element three of an array of doublewords: index 3, scale 3.
  X(encdec_reg(0b00011)) = 0x0000000000000003;
  X(encdec_reg(0b00100)) = 0x0123456789abcdef;
  match execute(CIndexedStore(0b11, encdec_reg(0b00011), encdec_reg(0b01000), encdec_reg(0b00100))) {
    Retire_Success() => (),
    _                => assert(false, "an in-bounds indexed store must succeed"),
  };
  match execute(CIndexedLoad(0b11, encdec_reg(0b00011), encdec_reg(0b01000), encdec_reg(0b00101))) {
    Retire_Success() => (),
    _                => assert(false, "an in-bounds indexed load must succeed"),
  };
  assert(X(encdec_reg(0b00101)) == 0x0123456789abcdef);

  // The scale is part of the address and not decoration: index twenty-four
  // unscaled names the same doubleword as index three at the doubleword scale.
  // Which scales the backend emits is the composition-time selection; the width
  // of the field is what the freeze fixes (R-15-007g).
  X(encdec_reg(0b00011)) = 0x0000000000000018;
  match execute(CIndexedLoad(0b00, encdec_reg(0b00011), encdec_reg(0b01000), encdec_reg(0b00110))) {
    Retire_Success() => (),
    _                => assert(false, "an unscaled indexed load must succeed"),
  };
  assert(X(encdec_reg(0b00110)) == 0x0123456789abcdef);

  // Past the top of the authority: a length violation naming the authorising
  // register, checked at base plus scaled index.
  X(encdec_reg(0b00011)) = 0x0000000000001000;
  match execute(CIndexedLoad(0b11, encdec_reg(0b00011), encdec_reg(0b01000), encdec_reg(0b00101))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_LengthViolation);
      assert(idx == 0b001000);
    },
    _ => assert(false, "an out-of-bounds indexed load must fault"),
  };

  // An index far outside the representable region is the same fault. This is
  // the case the instruction exists to take off the dereference path: the
  // equivalent `cincoffset` would have yielded an untagged capability, and the
  // fault would have been a tag violation one instruction later.
  X(encdec_reg(0b00011)) = 0x0000000008000000;
  match execute(CIndexedStore(0b11, encdec_reg(0b00011), encdec_reg(0b01000), encdec_reg(0b00100))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_LengthViolation),
    _ => assert(false, "an unrepresentable indexed store must fault on the authority"),
  };
}

// The revocation filter is part of the capability load's own definition and not
// an effect layered onto it (R-08-005, R-08-005b): a load whose result is
// revoked writes the value back with its validity tag cleared, and the value
// itself is delivered unchanged. The bit is selected by the **loaded
// capability's base**, so a stale capability pointing into the middle of a
// freed object is caught exactly as one pointing at its start is.
$[test]
function test_a_revoked_capability_loads_with_its_tag_cleared() -> unit = {
  // Inside the composition's revocable interval (model/config).
  let object_base : xlenbits = 0x0000000080008000;
  let (_, region) = setCapBounds(root_data_cap, 0x080008000, 0b0 @ 0x080008100);
  let auth = setCapAddrChecked(region, object_base);
  let value = setCapAddrChecked(region, object_base + 64);
  assert(revocation_covered(zero_extend(object_base)));

  revocation_bits = zeros();
  C(encdec_reg(0b00011)) = value;
  match cap_store(encdec_reg(0b00011), auth, 0b000010, object_base) {
    Retire_Success() => (),
    _                => assert(false, "the store must succeed"),
  };

  // Live: the capability comes back whole.
  match cap_load(encdec_reg(0b00100), auth, 0b000010, object_base) {
    Retire_Success() => (),
    _                => assert(false, "a live load must succeed"),
  };
  assert(C(encdec_reg(0b00100)).tag);

  // Revoked: the same load succeeds, delivers the same bits, and clears the
  // tag. It does not trap, and it names no cause code, because a revoked result
  // is one of the load's defined results rather than a failure of it.
  revocation_bits = [revocation_bits with revocation_index(zero_extend(object_base)) = bitone];
  match cap_load(encdec_reg(0b00100), auth, 0b000010, object_base) {
    Retire_Success() => (),
    _                => assert(false, "a revoked load must still succeed"),
  };
  assert(not(C(encdec_reg(0b00100)).tag));
  assert(C(encdec_reg(0b00100)).address == value.address);

  // The bit belongs to the granule of the *base*, not of the access: a
  // capability read from a different address whose base is the revoked granule
  // is revoked too.
  match cap_store(encdec_reg(0b00011), auth, 0b000010, object_base + 8) {
    Retire_Success() => (),
    _                => assert(false, "the second store must succeed"),
  };
  match cap_load(encdec_reg(0b00100), auth, 0b000010, object_base + 8) {
    Retire_Success() => (),
    _                => assert(false, "the second load must succeed"),
  };
  assert(not(C(encdec_reg(0b00100)).tag));

  // A base outside the covered union takes the same path with a constant live
  // result, which is what keeps one fixed latency on every capability load
  // (R-08-005a, R-17-023).
  assert(not(revocation_covered(0x0000000080000000)));
  assert(not(revocation_revoked(0x0000000080000000)));

  revocation_bits = zeros();
}

// *****************************************************************
// The rows M0.6h adds: the block revocation reclaim. (`vmclear` and
// `cbo.scrub` are platform surface and are in test_platform.sail.)

// `creclaim` applies over one granule group the same per-granule conditional
// clear the load already applies to one value, and returns the group's tags as
// they stand afterwards (R-15-007s, R-08-007b). Three properties travel
// together because each is the reason the next is safe: the predicate is the
// **loaded capability's base** and not the granule it sits in, a surviving
// granule is untouched bit for bit, and a cleared one differs in its tag alone,
// which is what keeps R-15-007r's exclusion of a bulk tag clear undisturbed.
$[test]
function test_creclaim_clears_the_revoked_granules_of_a_group() -> unit = {
  // The block is inside the composition's revocable interval and is the group
  // `cbo.zero` allocates, so it is aligned to it (model/config, R-15-007q).
  let block : xlenbits = 0x0000000080008080;
  let (_, arena) = setCapBounds(root_data_cap, 0x080008000, 0b0 @ 0x080008100);
  let auth = setCapAddrChecked(arena, block);

  // Two objects with *different* bases, so the bit that decides one does not
  // decide the other. Both are stored inside a third granule group, which is
  // the case that matters: what the sweep walks and what the bit names are
  // different addresses.
  let (_, obj_a) = setCapBounds(arena, 0x080008000, 0b0 @ 0x080008040);
  let (_, obj_b) = setCapBounds(arena, 0x080008040, 0b0 @ 0x080008080);

  revocation_bits = zeros();
  C(encdec_reg(0b00011)) = obj_a;
  match cap_store(encdec_reg(0b00011), auth, 0b000010, block) {
    Retire_Success() => (),
    _                => assert(false, "storing the first object must succeed"),
  };
  C(encdec_reg(0b00011)) = obj_b;
  match cap_store(encdec_reg(0b00011), auth, 0b000010, block + cap_size) {
    Retire_Success() => (),
    _                => assert(false, "storing the second object must succeed"),
  };
  // A third granule holds data, so the pass has a granule with no tag to
  // consider and no base to index by.
  let _ = mem_write_value(physical_address(Virtaddr(block + (2 * cap_size))), 8,
                          0x0123456789abcdef, Store(Data), false, false);

  let stored_a : bits(64) =
    match mem_read(Load(Data), physical_address(Virtaddr(block)), 8, false, false) {
      Ok(v)     => v,
      Err(_, _) => { assert(false, "the stored capability must be readable as data"); zeros() },
    };

  // Only the first object's base is revoked.
  revocation_bits = [revocation_bits with revocation_index(0x0000000080008000) = bitone];

  C(encdec_reg(0b00010)) = auth;
  match execute(CReclaim(encdec_reg(0b00100), encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "creclaim over an authorised group must succeed"),
  };

  // The answer is the tags *after* the pass: the first granule's authority is
  // gone, the second's survives, and the data granule never had one.
  let tags = X(encdec_reg(0b00100))[caps_per_block - 1 .. 0];
  assert(tags == (zero_extend(0b1) << 1));

  // The cleared granule differs in its tag and in nothing else. No data is
  // written by either case, which is the whole of *without materializing the
  // value*.
  match mem_read(Load(Data), physical_address(Virtaddr(block)), 8, false, false) {
    Ok(v)     => assert(v == stored_a),
    Err(_, _) => assert(false, "the cleared granule must still be readable"),
  };
  match cap_load(encdec_reg(0b00101), auth, 0b000010, block) {
    Retire_Success() => (),
    _                => assert(false, "loading the cleared granule must succeed"),
  };
  assert(not(C(encdec_reg(0b00101)).tag));
  match cap_load(encdec_reg(0b00101), auth, 0b000010, block + cap_size) {
    Retire_Success() => (),
    _                => assert(false, "loading the surviving granule must succeed"),
  };
  assert(C(encdec_reg(0b00101)).tag);

  // A second pass over the same group answers the same thing and changes
  // nothing: the clear is in place and the sweep may revisit a group without
  // its result depending on how many times it has.
  match execute(CReclaim(encdec_reg(0b00110), encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "a repeated creclaim must succeed"),
  };
  assert(X(encdec_reg(0b00110))[caps_per_block - 1 .. 0] == tags);

  // It requires what a tag-preserving capability load over the group requires
  // and faults rather than answering zeroes, for `cloadtags`' reason: an answer
  // of no tags is indistinguishable from a group with none.
  C(encdec_reg(0b00010)) = { auth with perms = perms_rw | perms_global_bit };
  match execute(CReclaim(encdec_reg(0b00100), encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_PermitLoadCapViolation),
    _ => assert(false, "creclaim without load-capability must fault"),
  };

  revocation_bits = zeros();
}

// *****************************************************************
// The special capability registers.

// Privilege is the capability: the trap capabilities are reachable only with
// the access-system-registers permission on the executing PCC, and PCC itself
// is readable but not writable (R-15-003, R-15-073).
$[test]
function test_cspecialrw_is_gated_by_the_capability() -> unit = {
  PCC = default_cap;
  MTDC = null_cap;
  C(encdec_reg(0b00010)) = root_data_cap;

  match execute(CSpecialRW(encdec_reg(0b00011), 0b11101, encdec_reg(0b00010))) {
    Retire_Success() => (),
    _                => assert(false, "a write to MTDC under ASR must succeed"),
  };
  assert(MTDC == root_data_cap);
  assert(C(encdec_reg(0b00011)) == null_cap);

  // Without the permission the same write is a capability violation naming the
  // special register rather than a general-purpose one. The permission is one
  // codepoint away: the unprivileged code root is the same shape without it.
  PCC = { default_cap with perms = perms_code_root | perms_global_bit };
  match execute(CSpecialRW(encdec_reg(0b00011), 0b11101, encdec_reg(0b00010))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_AccessSystemRegsViolation);
      assert(idx == 0b111101);
    },
    _ => assert(false, "a write to MTDC without ASR must fault"),
  };
  PCC = default_cap;

  // PCC is read-only, and a number the bank does not carry is illegal. Number
  // one is such a number: it was `ddc`, which went with hybrid mode
  // (R-15-001c).
  match execute(CSpecialRW(encdec_reg(0b00011), 0b00000, encdec_reg(0b00010))) {
    Illegal_Instruction() => (),
    _                     => assert(false, "PCC must not be writable"),
  };
  match execute(CSpecialRW(encdec_reg(0b00011), 0b00001, zreg)) {
    Illegal_Instruction() => (),
    _                     => assert(false, "the ddc number must be illegal"),
  };
  match execute(CSpecialRW(encdec_reg(0b00011), 0b11110, zreg)) {
    Illegal_Instruction() => (),
    _                     => assert(false, "an absent special register must be illegal"),
  };
}
