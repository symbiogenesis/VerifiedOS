// The capability semantics of the vector memory surface: the per-element check
// on a scalar-issued vector access, the tag clear a vector store lands on every
// granule it overwrites, and the mask that decides which element may raise
// (R-08-003, R-15-115, R-15-115a, R-15-115b, extensions/V/vext_mem_checks.sail).
//
// **The properties are written against `vlen` rather than against an element
// count**, because the harness runs under the generated *max* configuration and
// not under the profile's (M0.6g), and because the class this surface belongs to
// is the one whose VLEN is 4096 where the configuration the harness runs is 256
// (R-15-113). What is asserted here is therefore true of every geometry the
// model can be configured at, which is what makes it evidence for the V class
// and not only for the machine the test happens to run on.
//
// Every property below places its authority in `c2` and its data in `v8`, and
// leaves the region at [0x80000000, 0x80001000) so that a base address 16 bytes
// below the top admits exactly two 64-bit elements. That is the shape the
// element-wise claim needs: whether the access faults is decided by how far its
// *elements* reach and not by where the access begins.

// The region every property below authorises against, and the register the
// checks name when they fail.
val vector_test_region : unit -> Capability
function vector_test_region() = {
  let (_, region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  region
}

// SEW=64, LMUL=1, and a `vtype` no clause may refuse.
val vector_test_vtype : (bits(3), range(1, 8)) -> unit
function vector_test_vtype(vsew_bits, elems) = {
  vtype = Mk_Vtype(zeros());
  vtype[vsew] = vsew_bits;
  vtype[vlmul] = 0b000;
  vl = to_bits(xlen, elems);
}

// *****************************************************************
// The check is per element, at the element's own address.

// A vector memory operation is scalar-issued: it names a base register, and that
// register holds the capability the access is authorised by, exactly as an
// ordinary load does (R-15-115). What makes the check *element-wise* rather than
// a bounds test over the whole access is that each element presents its own
// address and its own width, so the same instruction through the same base
// faults or does not according to how many elements it reaches (R-08-003).
$[test]
function test_a_vector_load_is_checked_one_element_at_a_time() -> unit = {
  let region = vector_test_region();
  // Sixteen bytes below the top: elements 0 and 1 fit, element 2 does not.
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, 0x0000000080000ff0);
  V(zvreg) = zeros();

  // Four elements reach 32 bytes and the last two are outside the region.
  vector_test_vtype(0b011, 4);
  match execute(VLSEGTYPE(1, 0b1, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_LengthViolation);
      // The violation names the register the access took its authority from,
      // which is the base register and never the vector destination: there is
      // one authority for the whole operation and one address per element
      // (R-15-073a).
      assert(idx == capreg_idx_of_regidx(encdec_reg(0b00010)));
    },
    _ => assert(false, "a vector load reaching past its authority must fault"),
  };

  // Two elements reach sixteen bytes and both are inside it. Same instruction,
  // same authority, same base address: only the element count moved.
  vector_test_vtype(0b011, 2);
  match execute(VLSEGTYPE(1, 0b1, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Retire_Success() => (),
    _                => assert(false, "a vector load inside its authority must retire"),
  };

  // And the last element is checked at its own *width*: one byte further on,
  // the two elements still start inside the region and the second ends outside
  // it, which a check over the first byte of each would admit (R-15-007c).
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, 0x0000000080000ff1);
  match execute(VLSEGTYPE(1, 0b1, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_LengthViolation),
    Trap(_, _) => (),   // the misalignment policy may reach this address first
    _ => assert(false, "an element ending past the top must not load"),
  };
}

// *****************************************************************
// Only an active element raises.

// The two contracts compose as *check every element, fault only on the active
// ones* (R-15-115b). The instruction retiring is the "fault only on the active
// ones" half; the "check every element" half is the same address handed to the
// same check, which reports the violation the instruction did not raise. Both
// halves are asserted here against one address, because either alone is
// consistent with the mask being skipped or with the mask being observable.
$[test]
function test_only_an_active_vector_element_raises() -> unit = {
  let region = vector_test_region();
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, 0x0000000080000ff0);
  vector_test_vtype(0b011, 4);

  // Elements 0 and 1 active, 2 and 3 masked off. Elements 2 and 3 are the ones
  // outside the region.
  V(zvreg) = zero_extend(0b0011);
  match execute(VLSEGTYPE(1, 0b0, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Retire_Success() => (),
    _ => assert(false, "a masked-off element must not raise a capability exception"),
  };

  // The check the masked-off element performed is a failing one: this is the
  // very call `vector_masked_element_check` makes for element 2, and its result
  // is what R-15-115b discards.
  match ext_data_get_addr(encdec_reg(0b00010), to_bits(xlen, 16), Load(Vector), 8) {
    Ext_DataAddr_Error((capEx, _)) => assert(capEx == CapEx_LengthViolation),
    Ext_DataAddr_OK(_) => assert(false, "the masked-off element's check must fail"),
  };

  // The mask decides which element raises and nothing else: turning element 2
  // back on brings the fault back, and turning element 3 off does not take it
  // away, because element 2 is outside the region on its own account.
  V(zvreg) = zero_extend(0b0111);
  match execute(VLSEGTYPE(1, 0b0, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_LengthViolation),
    _ => assert(false, "an active element outside the region must raise"),
  };

  // The store side answers the same way, and it matters more there: a masked-off
  // store that reached memory would write it.
  V(zvreg) = zero_extend(0b0011);
  match execute(VSSEGTYPE(1, 0b0, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Retire_Success() => (),
    _ => assert(false, "a masked-off store element must not raise"),
  };
  V(zvreg) = zero_extend(0b0111);
  match execute(VSSEGTYPE(1, 0b0, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Ext_DataAddr_Check_Failure((capEx, _)) => assert(capEx == CapEx_LengthViolation),
    _ => assert(false, "an active store element outside the region must raise"),
  };
}

// *****************************************************************
// A tail element is not a masked-off element.

// `init_masked_result` and `init_masked_source` return one mask that folds three
// reasons an element is inactive, and only one of them is the vector mask.
// R-15-115b's obligation attaches to that one: `vl` and `vtype` are
// architectural registers a partition reads back, so an operation shorter than
// VLMAX leaks nothing by being shorter, where the mask is what R-15-085 forbids
// observing through timing or memory traffic. The separation is
// `vector_body_inactive`, and this is the property that holds it.
$[test]
function test_the_vector_tail_is_not_the_vector_mask() -> unit = {
  let num_elem = get_num_elem(0, 64);
  let 'n = num_elem;
  // Every geometry the model admits gives at least four 64-bit elements at
  // LMUL=1, VLEN=256 being the narrowest class in the table (R-15-113).
  assert(num_elem >= 4);

  V(zvreg) = zero_extend(0b0011);
  vector_test_vtype(0b011, 4);
  let vm_val : bits('n) = read_vmask(num_elem, 0b0, zvreg);
  let inactive : bits('n) = vector_body_inactive(num_elem, 0, vm_val);

  // Elements 2 and 3 are body elements the mask turns off, so they owe a check.
  assert(inactive[2] == bitone);
  assert(inactive[3] == bitone);
  // Elements 0 and 1 are active, so they raise rather than discarding.
  assert(inactive[0] == bitzero);
  assert(inactive[1] == bitzero);
  // Everything past `vl` is tail and owes nothing at all.
  foreach (i from 4 to (num_elem - 1)) {
    assert(inactive[i] == bitzero);
  };

  // Shortening `vl` moves elements 2 and 3 from masked-off to tail without
  // touching `v0`, and the obligation goes with them. This is the whole content
  // of the separation: the same mask bits, a different answer.
  vector_test_vtype(0b011, 2);
  let vm_val : bits('n) = read_vmask(num_elem, 0b0, zvreg);
  let inactive : bits('n) = vector_body_inactive(num_elem, 0, vm_val);
  assert(inactive == zeros());

  // And an unmasked operation has no masked-off element at any `vl`, which is
  // why the whole-register and mask-load forms owe no discarded check.
  vector_test_vtype(0b011, 4);
  let unmasked : bits('n) = read_vmask(num_elem, 0b1, zvreg);
  assert(vector_body_inactive(num_elem, 0, unmasked) == zeros());
}

// *****************************************************************
// A vector store clears the tag of every granule it overwrites.

// Tag clearing is a property of the write path rather than of an instruction
// (R-15-007r), so a vector store lands the tag write a scalar store already
// performs, once per element (R-15-115a). Without it a vector store would leave
// a stale tag standing over data it has overwritten, which is a forgery
// primitive rather than a residue.
//
// The masked-off element in the same operation is what shows the other half:
// its granule keeps both its tag and its bits, because no address was presented
// for it at all (vext_mem_checks.sail).
$[test]
function test_a_vector_store_clears_the_tags_it_overwrites() -> unit = {
  let region = vector_test_region();
  let first : xlenbits  = 0x0000000080000400;
  let second : xlenbits = 0x0000000080000408;
  let value = setCapAddrChecked(region, 0x0000000080000800);

  // Two granules, each holding a tagged capability.
  let _ = mem_write_value_meta(physical_address(Virtaddr(first)), cap_size,
                               capToMemBits(value), Store(Data), true, false, false);
  let _ = mem_write_value_meta(physical_address(Virtaddr(second)), cap_size,
                               capToMemBits(value), Store(Data), true, false, false);

  C(encdec_reg(0b00010)) = setCapAddrChecked(region, first);
  vector_test_vtype(0b011, 2);
  // Element 0 active, element 1 masked off.
  V(zvreg) = zero_extend(0b0001);
  write_single_element(64, 0, Vregidx(0b01000), 0x0123456789abcdef);
  write_single_element(64, 1, Vregidx(0b01000), 0xfedcba9876543210);

  match execute(VSSEGTYPE(1, 0b0, encdec_reg(0b00010), VLE64, Vregidx(0b01000))) {
    Retire_Success() => (),
    _                => assert(false, "an authorised vector store must retire"),
  };

  // The active element's granule: the data is the element's and the tag is gone.
  match mem_read_meta(Load(Data), physical_address(Virtaddr(first)), cap_size,
                      false, false, true) {
    Ok(v, tag) => {
      assert(v == 0x0123456789abcdef);
      assert(not_bool(tag), "a vector store must clear the tag of the granule it overwrote");
    },
    Err(_, _) => assert(false, "the first granule must be readable"),
  };

  // The masked-off element's granule: untouched bit for bit, tag included.
  match mem_read_meta(Load(Data), physical_address(Virtaddr(second)), cap_size,
                      false, false, true) {
    Ok(v, tag) => {
      assert(v == capToMemBits(value));
      assert(tag, "a masked-off element must present no address at all");
    },
    Err(_, _) => assert(false, "the second granule must be readable"),
  };
}

// *****************************************************************
// A partial-granule vector store clears the granule it lands in.

// R-15-115a says *partial-granule writes included*, and this is the case that
// distinguishes the write path's clearing from an aligned capability-width one:
// a single-byte element inside a granule holding a capability destroys that
// capability's authority, because a granule whose bits have moved may not keep
// a tag that says they have not (`__WriteRAM_Meta` clears every granule the
// access spans, core/mem_metadata.sail).
$[test]
function test_a_partial_granule_vector_store_clears_the_whole_granule() -> unit = {
  let region = vector_test_region();
  let granule : xlenbits = 0x0000000080000480;
  let value = setCapAddrChecked(region, 0x0000000080000800);

  let _ = mem_write_value_meta(physical_address(Virtaddr(granule)), cap_size,
                               capToMemBits(value), Store(Data), true, false, false);
  match mem_read_meta(Load(Data), physical_address(Virtaddr(granule)), cap_size,
                      false, false, true) {
    Ok(_, tag) => assert(tag, "the granule must start out tagged"),
    Err(_, _)  => assert(false, "the granule must be readable"),
  };

  // One 8-bit element, three bytes into the granule.
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, granule + 3);
  vector_test_vtype(0b000, 1);
  V(zvreg) = zeros();
  write_single_element(8, 0, Vregidx(0b01000), 0xff);

  match execute(VSSEGTYPE(1, 0b1, encdec_reg(0b00010), VLE8, Vregidx(0b01000))) {
    Retire_Success() => (),
    _                => assert(false, "a single-byte vector store must retire"),
  };

  match mem_read_meta(Load(Data), physical_address(Virtaddr(granule)), cap_size,
                      false, false, true) {
    Ok(_, tag) => assert(not_bool(tag),
                         "a partial-granule vector store must clear the granule's tag"),
    Err(_, _)  => assert(false, "the granule must be readable"),
  };
}

// *****************************************************************
// The indexed form is checked at its own index.

// This is the form R-08-003 names by itself, and R-15-085a is why: an indexed
// element's address is a runtime value, so no check over the base can stand in
// for the per-element one and the discharge for admitting the form at all is
// that the check lands where the address is made.
$[test]
function test_an_indexed_vector_access_is_checked_per_element() -> unit = {
  let region = vector_test_region();
  C(encdec_reg(0b00010)) = setCapAddrChecked(region, 0x0000000080000400);
  vector_test_vtype(0b011, 2);

  // Element 0 indexes inside the region; element 1 indexes past its top.
  write_single_element(64, 0, Vregidx(0b00100), zeros());
  write_single_element(64, 1, Vregidx(0b00100), to_bits(64, 4096));
  V(zvreg) = zeros();

  match execute(VLXSEGTYPE(1, 0b1, Vregidx(0b00100), encdec_reg(0b00010), VLE64,
                           Vregidx(0b01000), INDEXED_ORDERED)) {
    Ext_DataAddr_Check_Failure((capEx, idx)) => {
      assert(capEx == CapEx_LengthViolation);
      assert(idx == capreg_idx_of_regidx(encdec_reg(0b00010)));
    },
    _ => assert(false, "an index reaching past the authority must fault"),
  };

  // Masking that element off discards its check like any other, the index being
  // the element's and the mask being the operation's.
  V(zvreg) = zero_extend(0b0001);
  match execute(VLXSEGTYPE(1, 0b0, Vregidx(0b00100), encdec_reg(0b00010), VLE64,
                           Vregidx(0b01000), INDEXED_ORDERED)) {
    Retire_Success() => (),
    _ => assert(false, "a masked-off indexed element must not raise"),
  };

  // The same index inside the region loads, so the fault above is the index's
  // and not the form's.
  write_single_element(64, 1, Vregidx(0b00100), to_bits(64, 256));
  V(zvreg) = zeros();
  match execute(VLXSEGTYPE(1, 0b1, Vregidx(0b00100), encdec_reg(0b00010), VLE64,
                           Vregidx(0b01000), INDEXED_ORDERED)) {
    Retire_Success() => (),
    _ => assert(false, "an index inside the authority must load"),
  };
}
