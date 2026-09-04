// Properties of the software-managed scratchpad, the addressable region class
// the V- and M-class datapaths stream through (sys/pma.sail, core/core_class.sail,
// R-15-165, R-15-167).
//
// **The subject is a placement and not a structure**, which is what these
// properties are shaped by. A scratchpad here is capability-governed plain
// memory at a fixed address range with no fill, no eviction, and no lookup that
// is not the ordinary address decode, so what can be asserted about it is where
// it is, whose it is, that it is on neither main-memory latency class, and that
// the partition switch's pass covers exactly it (R-07-014c). There is nothing
// else about one for a property to reach.
//
// **No configuration in this tree declares a scratchpad**, so the first property
// below is that fact and the two after it install one. `scratchpad_bytes` is one
// of R-15-108's frozen parameters and the exploration that selects it has not
// run, so a size written into a shipped configuration would be a placeholder
// becoming an architectural input (core/core_class.sail). Installing one here is
// what lets the region class be exercised without one being declared, and each
// property restores the address map it found.

// **The shipped state, stated rather than assumed.** Both halves matter: no
// class table row declares a scratchpad size, and no address map region declares
// itself a scratchpad, so the two agree at zero the way the validator requires
// them to agree at anything (postlude/validate_config.sail).
$[test]
function test_no_configuration_here_declares_a_scratchpad() -> unit = {
  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    assert(core_class_datapath(c).scratchpad_bytes == 0);
    match scratchpad_region_of(pma_regions, c) {
      None()  => (),
      Some(_) => assert(false, "no configuration in this tree places a scratchpad region"),
    };
    let (base, size) = scratchpad_extent_of(c);
    assert(base == zeros() & size == zeros());
  };

  // And the two per-region declarations are disjoint rather than merely
  // different: main memory is on a latency class and is nobody's scratchpad.
  assert(memory_class_at(Physaddr(0x0000000080000000)) == Some(FirstClass));
  assert(scratchpad_class_at(Physaddr(0x0000000080000000)) == None());
}

// A test scratchpad, placed above every region the configurations declare so
// that installing it shadows nothing: it is two whole 4 KiB pages, which is what
// the region alignment rule requires of every region and what makes the
// partition switch's pass over it a whole number of the memory interface's own
// widest accesses (postlude/validate_config.sail, sys/pma.sail).
let test_scratchpad_base : bits(64) = 0x0000000300000000
let test_scratchpad_size : bits(64) = 0x0000000000002000

function test_scratchpad_pma(c : CoreClass) -> PMA_Region = struct {
  base = test_scratchpad_base,
  size = test_scratchpad_size,
  attributes = struct {
    mem_type         = MainMemory,
    // Not a cache and nothing above it to cache it (R-15-164, R-15-165).
    cacheable        = false,
    // Coherence-exempt (R-15-167).
    coherent         = false,
    // The admitted scratchpad is the datapath's data staging memory; a
    // statically-placed *instruction* scratchpad is an open question this
    // profile does not specify (R-18-009).
    executable       = false,
    readable         = true,
    writable         = true,
    read_idempotent  = true,
    write_idempotent = true,
    misaligned_exceptions = struct {
      load_store = None(),
      vector     = None(),
      amo        = AccessFault,
    },
    atomic_support   = AMOArithmetic,
    supports_cbo_zero = true,
    misaligned_atomicity_granule_size_exp = 0,
    vector_misaligned_atomicity_granule_size_exp = 0,
    // On neither of the two static latency classes: those are media of *main*
    // memory and this is the local tier above them (R-15-247, R-15-168).
    memory_class     = None(),
    scratchpad       = Some(c),
  },
  include_in_device_tree = true,
}

// Installing the region and taking it out again are two functions rather than
// an idiom written at each property, and the removal reads the register it is
// restoring rather than a binding taken before the change. Both shapes restore
// (M0.20 measured it, against the property below), but only this one is correct
// *whatever the list representation is*: assigning a saved binding back is
// correct here because the emitted list is reference-counted, so the binding
// aliases the register instead of being a copy of it, which is a property of
// the backend rather than of the property that relies on it.
function test_install_scratchpad(c : CoreClass) -> unit =
  pma_regions = test_scratchpad_pma(c) :: pma_regions

function test_uninstall_scratchpad() -> unit =
  match pma_regions {
    _ :: rest => pma_regions = rest,
    [||]      => assert(false, "the installed scratchpad region must still be there"),
  }

// **A declared scratchpad is found from either end, and it is on neither latency
// class.** The class table sizes it and the address map places it, so the two
// questions a reader can ask are *where is this class's scratchpad* and *whose
// scratchpad is this address*, and both are answered off one declaration rather
// than off two that could drift.
$[test]
function test_a_declared_scratchpad_is_found_from_either_end() -> unit = {
  test_install_scratchpad(CoreClass_M);

  let inside = Physaddr(test_scratchpad_base + 0x0000000000000010);
  assert(scratchpad_class_at(inside) == Some(CoreClass_M));
  assert(memory_class_at(inside) == None());

  match scratchpad_region_of(pma_regions, CoreClass_M) {
    None()       => assert(false, "the declared region must be the M class's scratchpad"),
    Some(region) => assert(region.base == test_scratchpad_base & region.size == test_scratchpad_size),
  };
  let (base, size) = scratchpad_extent_of(CoreClass_M);
  assert(base == test_scratchpad_base & size == test_scratchpad_size);

  // One class's scratchpad is not another's, which is what makes the region's
  // class column load-bearing rather than decorative: a machine composed of
  // several classes has several of these and the switch pass takes its own.
  assert(scratchpad_region_of(pma_regions, CoreClass_V) == None());
  let (v_base, v_size) = scratchpad_extent_of(CoreClass_V);
  assert(v_base == zeros() & v_size == zeros());

  // And an address outside it is nobody's, so the region class is a placement
  // and not a property of the machine at large.
  assert(scratchpad_class_at(Physaddr(0x0000000080000000)) == None());

  test_uninstall_scratchpad();
}

// **The partition switch's pass covers exactly the declared range, and it takes
// the tags with it.** The eager zeroize is unconditional and mask-independent
// (R-07-014a, R-07-014c), so what is asserted is that every byte of the
// scratchpad is zero afterwards, that a granule that held a tagged capability
// holds neither the bits nor the authority, and that a granule outside the
// declared range is untouched: the trip count is the composition's declaration
// and never a function of what the outgoing partition wrote.
//
// The tag half is not a clause of `vmclear`'s own. Tag clearing is a property of
// the write path (R-15-007r), so the plain write the pass makes clears the
// validity tag of every granule it covers for free, which is exactly the
// disclosure half of the zeroize discipline (R-15-060, R-15-182).
$[test]
function test_vmclear_covers_the_declared_scratchpad_and_nothing_else() -> unit = {
  test_install_scratchpad(CoreClass_C);

  // Two capabilities, one inside the scratchpad and one in first-class RAM
  // outside it, written through the ordinary capability store so that both
  // carry a set validity tag before the pass.
  let (_, pad_region) = setCapBounds(root_data_cap, 0x300000000, 0b0 @ 0x300002000);
  let pad_auth = setCapAddrChecked(pad_region, test_scratchpad_base);
  let (_, ram_region) = setCapBounds(root_data_cap, 0x080000000, 0b0 @ 0x080001000);
  let ram_auth = setCapAddrChecked(ram_region, 0x0000000080000000);

  C(encdec_reg(0b00011)) = pad_auth;
  match cap_store(encdec_reg(0b00011), pad_auth, 0b000010, test_scratchpad_base) {
    Retire_Success() => (),
    _                => assert(false, "storing a capability into the scratchpad must succeed"),
  };
  // And the last granule of the range, so the pass is measured over the whole of
  // it rather than over its first chunk.
  match cap_store(encdec_reg(0b00011), pad_auth, 0b000010,
                  test_scratchpad_base + test_scratchpad_size - to_bits(64, cap_size)) {
    Retire_Success() => (),
    _                => assert(false, "storing into the last granule of the scratchpad must succeed"),
  };

  C(encdec_reg(0b00011)) = ram_auth;
  match cap_store(encdec_reg(0b00011), ram_auth, 0b000010, 0x0000000080000000) {
    Retire_Success() => (),
    _                => assert(false, "storing a capability into first-class RAM must succeed"),
  };

  // A data pattern in the middle of the range too, so that a pass covering only
  // the granules that held capabilities would be visible.
  match mem_write_value(Physaddr(test_scratchpad_base + 0x0000000000001000), 8,
                        0xdeadbeefdeadbeef, Store(Data), false, false) {
    Ok(_)     => (),
    Err(_, _) => assert(false, "writing the scratchpad must succeed"),
  };

  match execute(VMClear()) {
    Retire_Success() => (),
    _                => assert(false, "vmclear must retire"),
  };

  // Every chunk of the declared range reads zero and untagged.
  let chunks = unsigned(test_scratchpad_size) / cap_size;
  foreach (i from 0 to (chunks - 1)) {
    let addr = Physaddr(test_scratchpad_base + to_bits(64, i * cap_size));
    match mem_read_meta(Load(Data), addr, cap_size, false, false, true) {
      Ok((value, tag)) => {
        assert(value == zeros(), "the scratchpad must read zero after the switch's pass");
        assert(tag == default_meta, "the switch's pass leaves no validity tag standing over what it overwrote");
      },
      Err(_, _) => assert(false, "reading the cleared scratchpad must succeed"),
    }
  };

  // And the capability outside it is exactly where it was, tag included: the
  // pass is bounded by the declaration and not by the region the declaration
  // sits beside.
  match cap_load(encdec_reg(0b00100), ram_auth, 0b000010, 0x0000000080000000) {
    Retire_Success() => (),
    _                => assert(false, "the capability outside the scratchpad must still load"),
  };
  assert(C(encdec_reg(0b00100)).tag);
  assert(C(encdec_reg(0b00100)) == ram_auth);

  test_uninstall_scratchpad();
}

// **The restore is observed rather than assumed.** The two properties above
// install a region and take it out again, and until this one nothing asked
// whether the map afterwards was the map before: the harness resets every
// register between properties, so a restore that did nothing is
// indistinguishable from one that worked at every point outside the property
// body that made it. The question can therefore only be put *inside* one body,
// which is what this property is, and it is what decides the idiom above rather
// than asserting it.
$[test]
function test_a_scratchpad_install_is_undone_by_its_own_restore() -> unit = {
  let inside = Physaddr(test_scratchpad_base);
  let ram    = Physaddr(0x0000000080000000);

  assert(scratchpad_class_at(inside) == None(), "the shipped map places no scratchpad");
  assert(memory_class_at(ram) == Some(FirstClass), "and it places main memory");

  test_install_scratchpad(CoreClass_M);
  assert(scratchpad_class_at(inside) == Some(CoreClass_M), "the install is visible");

  test_uninstall_scratchpad();

  // Both halves, because a restore can fail in two directions: it can leave what
  // it installed standing, and it can lose the map it was restoring.
  assert(scratchpad_class_at(inside) == None(),
         "the restore takes the installed region back out");
  assert(scratchpad_region_of(pma_regions, CoreClass_M) == None(),
         "and it is gone from the class's end of the map as well");
  assert(memory_class_at(ram) == Some(FirstClass),
         "the restore puts back the map it found rather than some other one");
}
