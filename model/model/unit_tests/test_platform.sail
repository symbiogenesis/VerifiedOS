// Properties of the platform surface the profile adds and no upstream model
// carries: `fence.t` (extensions/platform/fence_t.sail), the machine-level
// interrupt file, and the revocation sidecar's register slave
// (sys/platform.sail, core/revocation.sail).
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
