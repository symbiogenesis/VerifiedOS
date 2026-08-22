// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

private function check_tvec() -> bool = {
  if not(config base.mtvec.direct.supported : bool) & not(config base.mtvec.vectored.supported : bool) then {
    print_endline("`mtvec` specifies neither `direct` or `vectored` is supported; one of the modes must be supported.");
    return false;
  };
  true
}

private function check_vlen_elen() -> bool = {
  // Should this be conditioned on a vector extension being enabled?

  // Due to the `constraint elen_exp <= vlen_exp` the Sail compiler will
  // dead-code eliminate this check without the `: nat` type annotations.
  // Technically it could still eliminate the check even with `: nat`, and
  // by running any code that violates the `constraint` we're invoking UB.
  // However this does work in practice for now so it's probably better
  // than nothing. The proper fix is: https://github.com/rems-project/sail/issues/1387
  if (vlen_exp : nat) < (elen_exp : nat)
  then {
    print_endline("VLEN (set to 2^" ^ dec_str(vlen_exp) ^ ") cannot be less than ELEN (set to 2^" ^ dec_str(elen_exp) ^ ").");
    return false;
  };
  // The above comment about dead code elimination applies here too.
  if (vlen_exp : nat) < 3 | (vlen_exp : nat) > 16
  then {
    print_endline("VLEN set to 2^" ^ dec_str(vlen_exp) ^ " but must be within [2^3, 2^16].");
    return false;
  };
  if (elen_exp : nat) < 3 | (elen_exp : nat) > 16
  then {
    print_endline("ELEN set to 2^" ^ dec_str(elen_exp) ^ " but must be within [2^3, 2^16].");
    return false;
  };
  true
}

private function check_vext_config() -> bool = {
  var valid : bool = true;
  // Standard Vector Extensions
  if vector_support_level >= Integer & (elen_exp : nat) < 5 then {
    valid = false;
    print_endline("Zve*x is enabled but ELEN is 2^" ^ dec_str(elen_exp) ^ ": ELEN must be >= 2^5");
  };
  // Ideally, this parameter should be
  //   let max_index_eew_exp = config extensions.V.max_index_eew_exp : range(3, elen_exp)
  // except that it runs into https://github.com/rems-project/sail/issues/1392
  let max_index_eew = config extensions.V.max_index_eew_exp : nat;
  if max_index_eew > elen_exp then {
    valid = false;
    print_endline("The maximum index EEW is 2^" ^ dec_str(max_index_eew) ^ " but ELEN is 2^" ^ dec_str(elen_exp) ^ ": the index EEW must not exceed ELEN.");
  } else if max_index_eew < 3 then {
    valid = false;
    print_endline("The maximum index EEW is 2^" ^ dec_str(max_index_eew) ^ " but it should be at least 2^3.");
  };
  // Upstream requires scalar `F` under a float-capable vector level and `D`
  // under a double-capable one. Those two checks are the validator half of the
  // vector-FP-without-scalar-FP fork (R-15-040): with scalar floating point
  // excluded (R-15-039) the element width is the only real precondition, and
  // this is the configuration the profile actually runs.
  if vector_support_level >= Float_double then {
    if (elen_exp : nat) < 6 then {
      valid = false;
      print_endline("Zve*d is enabled but ELEN is 2^" ^ dec_str(elen_exp) ^ ": ELEN must be >= 2^6");
    };
  };
  if hartSupports(Ext_Zve32x) & not(config extensions.Zicsr.supported : bool) then {
    valid = false;
    print_endline("Zve32x is enabled but Zicsr is disabled: supporting Zve32x requires Zicsr.");
  };
  if hartSupports(Ext_Zve32x) & not(hartSupports(Ext_Zvl32b)) then {
    valid = false;
    print_endline("VLEN (set to 2^" ^ dec_str(vlen_exp) ^ ") is below the minimum required for Zve32x (need Zvl32b).");
  };
  if hartSupports(Ext_Zve64x) & not(hartSupports(Ext_Zvl64b)) then {
    valid = false;
    print_endline("VLEN (set to 2^" ^ dec_str(vlen_exp) ^ ") is below the minimum required for Zve64x (need Zvl64b).");
  };
  if vector_support_level >= Full & not(hartSupports(Ext_Zvl128b)) then {
    valid = false;
    print_endline("VLEN (set to 2^" ^ dec_str(vlen_exp) ^ ") is below the minimum required for V (need Zvl128b).");
  };
  if (config extensions.Zvfhmin.supported : bool) & not(hartSupports(Ext_Zve32f)) then {
    valid = false;
    print_endline("Zvfhmin is enabled but Zve32f is disabled: Zvfhmin requires Zve32f.");
  };
  // Upstream also requires the scalar `Zfhmin` converts here (R-15-039).
  if (config extensions.Zvfh.supported : bool) & not(hartSupports(Ext_Zve32f)) then {
    valid = false;
    print_endline("Zvfh is enabled but Zve32f is disabled: Zvfh requires Zve32f.");
  };
  // Cryptography Extensions: Vector Instructions
  if (config extensions.Zvbb.supported : bool) & not(hartSupports(Ext_Zve32x)) then {
    valid = false;
    print_endline("Zvbb is enabled but Zve32x is disabled: Zvbb requires Zve32x.");
  };
  if (config extensions.Zvbc.supported : bool) & not(hartSupports(Ext_Zve64x) | hartSupports(Ext_V)) then {
    valid = false;
    print_endline("Zvbc is enabled but Zve64x and V are disabled: Zvbc requires Zve64x or V.");
  };
  if (config extensions.Zvkb.supported : bool) & not(hartSupports(Ext_Zve32x)) then {
    valid = false;
    print_endline("Zvkb is enabled but Zve32x is disabled: Zvkb requires Zve32x.");
  };
  if (config extensions.Zvkg.supported : bool) & not(hartSupports(Ext_Zve32x)) then {
    valid = false;
    print_endline("Zvkg is enabled but Zve32x is disabled: Zvkg requires Zve32x.");
  };
  if (config extensions.Zvkned.supported : bool) & not(hartSupports(Ext_Zve32x)) then {
    valid = false;
    print_endline("Zvkned is enabled but Zve32x is disabled: Zvkned requires Zve32x.");
  };
  if (config extensions.Zvknha.supported : bool) & not(hartSupports(Ext_Zve32x)) then {
    valid = false;
    print_endline("Zvknha is enabled but Zve32x is disabled: Zvknha requires Zve32x.");
  };
  if (config extensions.Zvknhb.supported : bool) & not(hartSupports(Ext_Zve64x) | hartSupports(Ext_V)) then {
    valid = false;
    print_endline("Zvknhb is enabled but Zve64x and V are disabled: Zvknhb requires Zve64x or V.");
  };
  if (config extensions.Zvkt.supported : bool) & not(hartSupports(Ext_Zve32x)) then {
    valid = false;
    print_endline("Zvkt is enabled but Zve32x is disabled: Zvkt requires Zve32x.");
  };
  valid;
}

private function check_pma_region(region : PMA_Region) -> bool = {
  // We currently require PMAs to be aligned to page boundaries.  This
  // simplifies memory protection and alignment checks: PMA properties
  // will not change within intra-page accesses.  Although this constraint
  // is not imposed by the specification, most implementations are
  // expected to conform with it.
  if region.base[pma_granule_bits - 1 .. 0] != zeros() then {
    print_endline("Memory region starting at " ^ bits_str(region.base) ^ " does not start on a 4K boundary.");
    return false;
  };
  if region.size[pma_granule_bits - 1 .. 0] != zeros() then {
    print_endline("Memory region starting at " ^ bits_str(region.base) ^ " with size " ^ bits_str(region.size) ^ " does not end on a 4K boundary.");
    return false;
  };

  let pma = region.attributes;
  // TODO: this could be extended, e.g. to check that read_idempotent => readable, etc.
  match pma.mem_type {
    MainMemory =>
      if not(pma.readable & pma.writable & pma.read_idempotent & pma.write_idempotent) then {
        print_endline("Memory region starting at " ^ bits_str(region.base) ^ " is marked as " ^ to_str(pma.mem_type) ^ " but is not readable, read-idempotent, writable, and write-idempotent.");
        return false;
      },
    IOMemory =>
      (),
  };

  // Every array is on exactly one of the two static latency classes and no
  // device endpoint is on either (R-15-247, core/memory_class.sail). Both
  // directions are refusals rather than defaults: an unplaced array would take
  // whichever constant a later reader assumed, and a device given a class would
  // put an endpoint's accept time, which the issuing compartment is charged for
  // separately (R-15-015c), into a term that is about arrays.
  //
  // The scratchpad is the third medium and the exemption is stated here rather
  // than assumed: R-15-247's two classes are media of *main* memory and a
  // scratchpad is the local tier above them, which R-15-168 gives no scalar core
  // at all, so it is the one main-memory-typed region carrying no class
  // (sys/pma.sail, R-15-165, R-15-167).
  match (pma.mem_type, pma.memory_class, pma.scratchpad) {
    (MainMemory, None(), None()) => {
      print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " declares no `memory_class`; the static memory plan places every array on one of the two latency classes.");
      return false;
    },
    (IOMemory, Some(c), _) => {
      print_endline("IO memory region starting at " ^ bits_str(region.base) ^ " declares `memory_class` " ^ to_str(c) ^ "; the latency classes are main-memory media and a device endpoint is on neither.");
      return false;
    },
    (MainMemory, Some(k), Some(c)) => {
      print_endline("The " ^ to_str(c) ^ " core class's scratchpad at " ^ bits_str(region.base) ^ " declares `memory_class` " ^ to_str(k) ^ "; a scratchpad is the local tier above main memory rather than a region of it, so it is on neither of the two latency classes.");
      return false;
    },
    (IOMemory, _, Some(c)) => {
      print_endline("The " ^ to_str(c) ^ " core class's scratchpad at " ^ bits_str(region.base) ^ " is declared as IO memory; a scratchpad is capability-governed plain memory the datapath streams through, not a register-slave endpoint.");
      return false;
    },
    (_, _, _) => (),
  };

  // The scratchpad's own two attributes, both of them refusals of a structure
  // the requirements decline rather than of a value they bound.
  match pma.scratchpad {
    None()  => (),
    Some(c) => {
      // R-15-167 states the scratchpad coherence-exempt, which on a machine with
      // no cache and no coherence protocol (R-15-164) is a declaration and not a
      // relaxation: there is nothing for it to be exempt *from* except a
      // composition claiming a property this platform does not implement.
      if pma.coherent then {
        print_endline("The " ^ to_str(c) ^ " core class's scratchpad at " ^ bits_str(region.base) ^ " is declared coherent; the scratchpad is coherence-exempt and this platform carries no coherence protocol for it to participate in.");
        return false;
      };
      // A **statically-placed instruction scratchpad is an open question and
      // explicitly not specified** (R-18-009), narrowed to pinned single-tenant
      // cores and left as a design-space-exploration parameter. What R-15-167
      // admits is the datapath's data staging memory, so a composition marking
      // one executable is declaring the structure that question leaves open.
      if pma.executable then {
        print_endline("The " ^ to_str(c) ^ " core class's scratchpad at " ^ bits_str(region.base) ^ " is declared executable; the admitted scratchpad is the datapath's data staging memory, and a statically-placed instruction scratchpad is an open question this profile does not specify.");
        return false;
      };
    },
  };
  true
}

private struct pma_check_opts = {
  zama16b  : bool,
  ziccamoa : bool,
  ziccamoc : bool,
  ziccif   : bool,
  zicclsm  : bool,
}

// Return true if a list of PMA regions are sorted and don't overlap, and the specified extension checks are satisfied.
private function check_pma_regions(regions : list(PMA_Region), prev_base : bits(64), prev_size : bits(64), check_opts : pma_check_opts) -> bool =
  match regions {
    [||] => true,
    region :: rest => {
      if region.base <_u prev_base + prev_size then {
        print_endline("Memory region starting at " ^ bits_str(region.base) ^
                      " is not above the end of the previous region starting at " ^
                      bits_str(prev_base) ^ " and ending at " ^ bits_str(prev_base + prev_size) ^ ".");
        return false;
      } else if unsigned(region.base) + unsigned(region.size) > 2 ^ physaddr_bits then {
        print_endline("Memory region starting at " ^ bits_str(region.base) ^
                      " ends at " ^ bits_str(region.base + region.size) ^
                      " which is above the representable limit of the physical address bit size (i.e. " ^
                      dec_str(physaddr_bits) ^ " from `memory.physaddr_bits`).");
        return false;
      };

      if not(check_pma_region(region)) then return false;

      let attributes = region.attributes;
      if attributes.mem_type == MainMemory & attributes.cacheable & attributes.coherent then {
        let mag = attributes.misaligned_atomicity_granule_size_exp;
        if check_opts.zama16b & mag < 4 then {
          print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " is coherent and cacheable with " ^
                        (if mag == 0 then "no specified misaligned atomicity granule PMA"
                         else "a misaligned atomicity granule size of 2^" ^ dec_str(mag)) ^
                        ", but Zama16b is enabled which requires granule size of at least 2^4 bytes.");
          return false;
        };
        if check_opts.ziccamoa & attributes.atomic_support < AMOArithmetic then {
          print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " is coherent and cacheable with " ^ atomic_support_str(attributes.atomic_support) ^ " atomicity support, but Ziccamoa is enabled which requires AMOArithmetic support.");
          return false;
        };
        if check_opts.ziccamoc & attributes.atomic_support != AMOCASQ then {
          print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " is coherent and cacheable with " ^ atomic_support_str(attributes.atomic_support) ^ " atomicity support, but Ziccamoc is enabled which requires AMOCASQ support.");
          return false;
        };
        if check_opts.ziccif & not(attributes.executable) then {
          print_endline("Memory region starting at " ^ bits_str(region.base) ^ " is coherent and cacheable with no instruction fetch support, but Ziccif is enabled which requires this support.");
          return false;
        };
        if check_opts.zicclsm then {
          if misaligned_exception_is_access_fault(attributes.misaligned_exceptions.load_store) then {
            print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " is coherent and cacheable with access faults for misaligned scalar loads/stores, but Zicclsm is enabled which requires no exceptions or only misaligned exceptions for such accesses.");
            return false;
          };
          if misaligned_exception_is_access_fault(attributes.misaligned_exceptions.vector) then {
            print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " is coherent and cacheable with access faults for misaligned vector loads/stores, but Zicclsm is enabled which requires no exceptions or only misaligned exceptions for such accesses.");
            return false;
          };
        };
      };

      check_pma_regions(rest, region.base, region.size, check_opts)
    },
  }

// Return true iff [addr, addr+size) is fully contained in a single configured PMA memory region of the specified type.
function within_configured_pma_memory(component : string, mem_type_opt : option(MemoryRegionType), addr : bits(64), size : bits(64)) -> bool = {
  var valid : bool = true;
  match (matching_pma_region_bits_range(pma_regions, addr, size), mem_type_opt) {
    (None(), _) => {
      valid = false;
      print_endline("The " ^ component ^ " for the platform is not in a defined memory region.");
    },
    (Some(region), Some(mem_type)) => {
      if region.attributes.mem_type != mem_type then {
        valid = false;
        print_endline("The " ^ component ^ " for the platform is in a memory region starting at " ^ bits_str(region.base) ^ " which is not a " ^ to_str(mem_type) ^ " region.");
      }
    },
    (Some(_), _) => (),
  };
  valid
}

private function dtb_within_configured_pma_memory(addr : bits(64), size : bits(64)) -> bool =
  // Allow DTBs to be in main memory or IO memory (e.g. ROM).
  within_configured_pma_memory("DTB", None(), addr, size)

// Check that all memory regions are sorted and don't overlap, and that PMAs are compatible with enabled extensions.
private function check_mem_layout() -> bool =
  if pma_regions == [||] then {
    print_endline("No memory regions specified.");
    false
  } else {
    let check_opts : pma_check_opts = struct {
      zama16b  = config extensions.Zama16b.supported,
      ziccamoa = config extensions.Ziccamoa.supported,
      ziccamoc = config extensions.Ziccamoc.supported,
      ziccif   = config extensions.Ziccif.supported,
      zicclsm  = config extensions.Zicclsm.supported,
    };
    let pmas_ok  = check_pma_regions(pma_regions, zeros(), zeros(), check_opts);
    let clint_supported : bool = config platform.clint.supported;
    let clint_ok = not(clint_supported) |
                   within_configured_pma_memory("CLINT (platform.clint)", Some(IOMemory),
                                                to_bits_checked(config platform.clint.base : int),
                                                to_bits_checked(config platform.clint.size : int));
    // The interrupt file and the revocation bitmap's window are register
    // slaves, so both belong in IO memory rather than in main memory: an MSI is
    // a store to a device (R-15-064), and the bitmap is not addressable as data
    // at all (R-08-005a).
    let imsic_ok = not(plat_have_imsic) |
                   within_configured_pma_memory("interrupt file (platform.imsic)", Some(IOMemory),
                                                plat_imsic_base, plat_imsic_size);
    let revocation_window_ok = not(plat_have_revocation) |
                   within_configured_pma_memory("revocation bitmap window (platform.revocation)", Some(IOMemory),
                                                plat_revocation_base,
                                                to_bits(physaddrbits_len, revocation_bitmap_bytes));
    // The sequencer's window is a register slave like the other three, so it
    // belongs in IO memory; that it refuses every requester is a property of the
    // slave and not of where it sits (sys/platform.sail, R-15-247h).
    let sequencer_window_ok = not(plat_have_memory_sequencer) |
                   within_configured_pma_memory("memory sequencer window (platform.memory_sequencer)", Some(IOMemory),
                                                plat_memory_sequencer_base, plat_memory_sequencer_size);
    pmas_ok & clint_ok & imsic_ok & revocation_window_ok & sequencer_window_ok
  }

private function check_misc_extension_dependencies() -> bool = {
  var valid : bool = true;

  // See https://github.com/riscv/sail-riscv/issues/1508 for the next two checks.
  if (config extensions.Zabha.supported : bool) & not((config extensions.Zaamo.supported : bool) | (config extensions.A.supported : bool)) then {
    valid = false;
    print_endline("The Zabha extension is enabled but Zaamo and A are disabled: supporting Zabha requires Zaamo or A.");
  };
  if (config extensions.Zacas.supported : bool) & not((config extensions.Zaamo.supported : bool) | (config extensions.A.supported : bool)) then {
    valid = false;
    print_endline("The Zacas extension is enabled but Zaamo and A are disabled: supporting Zacas requires Zaamo or A.");
  };

  if (config extensions.Zvfbfmin.supported : bool) & not(hartSupports(Ext_Zve32f)) then {
    valid = false;
    print_endline("The Zvfbfmin extension is enabled but Zve32f is disabled: supporting Zvfbfmin requires Zve32f.")
  };
  // Upstream also requires the scalar bf16 converts `Zfbfmin` here (R-15-039).
  if (config extensions.Zvfbfwma.supported : bool) & not(config extensions.Zvfbfmin.supported : bool) then {
    valid = false;
    print_endline("The Zvfbfwma extension is enabled but Zvfbfmin is disabled: supporting Zvfbfwma requires Zvfbfmin.")
  };
  valid
}

private function check_extension_param_constraints() -> bool = {
  var valid : bool = true;
  if (config extensions.Zic64b.supported : bool) & (plat_cache_block_size_exp != 6) then {
    valid = false;
    print_endline("The Zic64b extension is enabled but the cache block size is not 64 bytes.");
  };
  if (config extensions.Zicclsm.supported : bool) then {
    if misaligned_exception_is_access_fault((config memory.misaligned.exceptions : GlobalMisalignedExceptions).load_store) then {
      valid = false;
      print_endline("The Zicclsm extension is enabled, but misaligned scalar loads/stores raise access faults before address translation (as per `memory.misaligned.exceptions.load_store`); Zicclsm requires no exceptions or only misaligned exceptions for such accesses.");
    };
    if misaligned_exception_is_access_fault((config memory.misaligned.exceptions : GlobalMisalignedExceptions).vector) then {
      valid = false;
      print_endline("The Zicclsm extension is enabled, but misaligned vector loads/stores raise access faults before address translation (as per `memory.misaligned.exceptions.vector`); Zicclsm requires no exceptions or only misaligned exceptions for such accesses.");
    };
  };
  valid
}

// The MMIO-device check went with the device it checked: the simple
// interrupt generator's base alignment was its only clause, and the
// CLINT's placement is already checked in `check_mem_layout` above.

private function check_mstatus_fields() -> bool = {
  var valid : bool = true;

  // `mstatus.FS` has no rows here: the field is deleted with scalar floating
  // point (R-15-039), so `VS` is the only extension-context state left.
  let legal_vs : ExtContextPolicy = config base.mstatus.vs_legal_states;
  if vector_support_level >= Integer then {
    if legal_vs == ExtContext_Off then {
      valid = false;
      print_endline("The vector registers are enabled but `base.mstatus.vs_legal_states` is set to `ExtContext_Off`, which makes `mstatus.VS` read-only zero: it cannot be read-only zero.");
    }
  } else if legal_vs != ExtContext_Off then {
    valid = false;
    print_endline("The vector registers are not enabled, but `base.mstatus.vs_legal_states` is not set to `ExtContext_Off`; i.e. `mstatus.VS` is not read-only zero: it should be read-only zero.");
  };

  valid
}

private function check_physaddr_bits() -> bool = {
  let physaddr_bits_nat : nat = physaddr_bits;
  if physaddr_bits_nat > 64 then {
    print_endline("`memory.physaddr_bits` is " ^ dec_str(physaddr_bits) ^ " but cannot be greater than 64.");
    false
  } else if physaddr_bits_nat < 13 then {
    print_endline("`memory.physaddr_bits` is " ^ dec_str(physaddr_bits) ^ " but values smaller than 13 are not supported.");
    false
  } else { true }
}

// The revocable interval map. R-08-005a fixes the shape of what an attested
// devicetree may declare, and this is where a composition that declares
// something else is refused rather than silently under-covered: the intervals
// are 64-byte aligned, they carry one bit per 8-byte granule, and the payload
// is charged against the SRAM capacity budget.
//
// The width bound is the model's own (core/revocation.sail): a Sail register is
// a fixed width, so a composition wanting a wider covered union widens the
// plane and re-runs, rather than having its top granules quietly fall outside
// the filter.
private function check_revocation() -> bool = {
  if not(plat_have_revocation) then return true;

  var valid : bool = true;
  let interval_base = unsigned(plat_revocation_interval_base);
  let interval_size = unsigned(plat_revocation_interval_size);

  if interval_base % 64 != 0 then {
    valid = false;
    print_endline("The revocable interval starts at " ^ bits_str(plat_revocation_interval_base) ^ " but a revocable interval must be 64-byte aligned.");
  };
  if interval_size == 0 | interval_size % 64 != 0 then {
    valid = false;
    print_endline("The revocable interval is " ^ dec_str(interval_size) ^ " bytes but must be a non-zero multiple of 64.");
  };
  if interval_size > revocation_max_interval then {
    valid = false;
    print_endline("The revocable interval is " ^ dec_str(interval_size) ^ " bytes but the revocation plane covers at most " ^ dec_str(revocation_max_interval) ^ " bytes.");
  };

  valid & within_configured_pma_memory("revocable interval (platform.revocation.interval_base)", Some(MainMemory),
                                       plat_revocation_interval_base, plat_revocation_interval_size)
}

// The core classes and the roster (R-15-113, R-15-052b, core/core_class.sail).
//
// What is checked here is the shape a composition may declare, never the
// values, for the reason the memory classes are checked that way below: VLEN per
// class, core count, issue width, pipeline depth, and scratchpad size are
// R-15-108's frozen parameters, selected by an exploration that has not run, and
// a validator asserting a range for one would be the architectural input that
// requirement leaves to the search. What it can hold instead is that a class
// says what kind of core it is, that the roster names the hart this model was
// built as, and that the geometry the roster attributes to that hart is the
// geometry the model was actually built at.
//
// That last one is the load-bearing check. `vlen_exp` in core/vlen.sail is a
// **type**-level configuration: it sizes the vector register file, so one build
// realizes one VLEN and the class table cannot derive it. Binding the two is
// therefore a refusal rather than a derivation, and without it a composition
// could describe its C class as VLEN=256 while running a model built at
// something else, with nothing in the machine or the attested devicetree
// disagreeing.
private function roster_hartid_count(roster : list(CoreRosterEntry), h : core_hartid) -> nat =
  match roster {
    [||]          => 0,
    entry :: rest => (if entry.hartid == h then 1 else 0) + roster_hartid_count(rest, h),
  }

private function check_roster_entries(roster : list(CoreRosterEntry)) -> bool =
  match roster {
    [||]          => true,
    entry :: rest => {
      var valid : bool = true;

      // One identity is one core. Two entries claiming one `mhartid` would make
      // the roster ambiguous exactly where R-15-052b requires it to be the thing
      // the kernel selects per-hart state out of.
      if roster_hartid_count(core_roster, entry.hartid) != 1 then {
        valid = false;
        print_endline("Hart " ^ dec_str(entry.hartid) ^ " appears in the core roster more than once; one hart identity names one core, which is what the kernel selects its per-hart state, its class, and its island binding out of.");
      };

      // The FEC units are attached to the pinned radio cores of a vector-bearing
      // class under the coprocessor line (R-15-119, R-12-038): fixed-geometry
      // arithmetic the PHY server issues, not an engine and not a scalar
      // attachment. A composition attaching them elsewhere is describing a
      // machine whose decoders have no long-vector datapath to feed.
      if entry.fec_units & not(entry.pinned) then {
        valid = false;
        print_endline("Hart " ^ dec_str(entry.hartid) ^ " carries FEC units without being pinned; the decoders follow the statically pinned radio cores, whose switch cost is deleted rather than budgeted.");
      };
      if entry.fec_units & not(core_class_is_vector_bearing(entry.class)) then {
        valid = false;
        print_endline("Hart " ^ dec_str(entry.hartid) ^ " carries FEC units on the vectorless " ^ to_str(entry.class) ^ " class; the LDPC and polar decoders are core-issued attachments to a long-vector datapath, and the scaling axis is core count rather than a firmware processor.");
      };

      valid & check_roster_entries(rest)
    },
  }

private function check_core_roster() -> bool = {
  var valid : bool = true;

  // Every class row, in the shape the register fixes. The record is symmetric
  // and the machine is not: a vectorless class declares zero for every vector
  // and matrix field rather than a small one, under the model's zero-is-absent
  // idiom, and anything else is a plan describing a machine this is not.
  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    let d = core_class_datapath(c);

    // Element width is a property of a vector unit, so the two geometry fields
    // are present together or absent together, and a declared element width
    // wider than the register it sits in is not a geometry at all.
    if (d.vlen_exp == 0) != (d.elen_exp == 0) then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares one of its vector length and element width and not the other; a vector geometry is both or neither.");
    };
    if d.elen_exp > d.vlen_exp then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares an element width above its vector length; an element does not exceed the register holding it.");
    };

    // The array's two geometries are one array (R-15-113). It consumes int8 and
    // bf16 only, de-quantization and microscaling being software on the same
    // class's vector unit (R-15-117), so a row declaring one width and not the
    // other is declaring half an array.
    if (d.matrix_int8_dim == 0) != (d.matrix_bf16_dim == 0) then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares one of its two matrix geometries and not the other; the systolic array consumes int8 and bf16 and is one array.");
    };

    // Everything below the vector waterline goes with the vector unit. A
    // vectorless class has no lanes to organize, no array to stream through a
    // scratchpad, and no vector permutation instruction for a Keccak unit to be,
    // which is why the sentinel and the RoT hash in plain 64-bit integer with
    // `Zbb` rotations instead (R-15-041, R-15-042, R-15-059, R-09-005a), and
    // scalar cores carry no local memory tier at all (R-15-168).
    if not(core_class_is_vector_bearing(c)) then {
      if d.lanes != 0 | core_class_has_matrix(c) then {
        valid = false;
        print_endline("The vectorless " ^ to_str(c) ^ " core class declares lanes or a matrix geometry; both are organizations of a vector datapath it does not have.");
      };
      if d.scratchpad_bytes != 0 then {
        valid = false;
        print_endline("The vectorless " ^ to_str(c) ^ " core class declares a software-managed scratchpad; a scalar core carries no local memory tier.");
      };
      if d.keccak_unit then {
        valid = false;
        print_endline("The vectorless " ^ to_str(c) ^ " core class declares a Keccak unit; the frozen permutation is a single vector instruction, so it is placed on the vector-bearing cores and the vectorless ones hash in plain 64-bit integer with `Zbb` rotations.");
      };
    };

    // The core-class table carries replication for the sentinel row alone
    // (R-16-008e). The lockstep pair presents one architectural core and its
    // comparator holds no architectural state, so replication is a field of the
    // class rather than a second hart, and no other class may claim it.
    if d.replicated & c != CoreClass_S then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares replication; the detection-lockstepped pair is the sentinel's alone and no other core on the die is replicated.");
    };
  };

  // A machine has cores, and the roster is where it says which. Everything below
  // reads it, so an empty one is refused before it is walked.
  if core_roster_size(core_roster) == 0 then {
    valid = false;
    print_endline("The core roster is empty; the roster is what fixes the reachable `mhartid` value space, so a machine with no entry in it has no hart identity to present.");
    return valid;
  };

  valid = valid & check_roster_entries(core_roster);

  // R-15-052b's criterion, made a refusal: the reachable value space is a
  // composition-time constant fixed by the roster, so a hart identity outside it
  // is not a value this machine can present.
  match this_core_entry() {
    None() => {
      valid = false;
      print_endline("The composed hart " ^ dec_str(plat_hartid) ^ " is not in the core roster; `mhartid` indexes the roster rather than standing beside it, so an identity the roster does not name is not one this machine may present.");
    },
    Some(entry) => {
      let d = core_class_datapath(entry.class);

      // The build and the table, held against each other. `vlen_exp` sizes the
      // vector register file at compile time, so this is the one place the class
      // table and the model it describes can be made to agree.
      if d.vlen_exp != sizeof(vlen_exp) | d.elen_exp != sizeof(elen_exp) then {
        if core_class_is_vector_bearing(entry.class) then {
          valid = false;
          print_endline("The composed hart is on the " ^ to_str(entry.class) ^ " core class, which declares a vector geometry of 2^" ^ dec_str(d.vlen_exp) ^ " bits at 2^" ^ dec_str(d.elen_exp) ^ "-bit elements, but this model was built at 2^" ^ dec_str(sizeof(vlen_exp)) ^ " and 2^" ^ dec_str(sizeof(elen_exp) ) ^ "; one build realizes one vector length.");
        }
      };

      // And the vectorless case from the other side: a class with no vector
      // geometry composed onto a model whose vector extension is enabled is a
      // sentinel or an RoT with a vector unit, which is the one thing
      // `vmclear`'s trap on a vectorless class is stated against (R-15-069d).
      if core_class_is_vector_bearing(entry.class) != (vector_support_level != Disabled) then {
        valid = false;
        print_endline("The composed hart is on the " ^ to_str(entry.class) ^ " core class, whose declared vector geometry and this model's `extensions.V.support_level` disagree about whether this core has a vector unit at all.");
      };
    },
  };

  valid
}

// The software-managed scratchpads (R-15-165, R-15-167, sys/pma.sail).
//
// **Two artifacts describe one structure and neither can see the other**: the
// class table sizes each class's scratchpad (R-15-113, R-15-108) and the address
// map places it (R-15-167's *fixed address range*), so a composition can size it
// at one figure and lay it out at another with nothing in the machine
// disagreeing. That is the whole of what is held here, and it is held as a
// refusal for the reason every other shape refusal in this file is: the *values*
// are R-15-108's exploration to select and this validator asserts none of them.
//
// **No configuration this tree ships declares a scratchpad at all**, and that is
// the correct state rather than a gap. `scratchpad_bytes` is one of R-15-108's
// frozen parameters, the exploration has not run, and `frozen` is false in every
// row, so a zero here reads *not selected* exactly as a zero in the matrix
// geometry does (core/core_class.sail). A number written in ahead of the
// exploration is how a placeholder becomes an architectural input, so the model
// carries the shape and refuses a wrong one and carries no size.
private function scratchpad_region_count(regions : list(PMA_Region), c : CoreClass) -> nat =
  match regions {
    [||]           => 0,
    region :: rest => (if region.attributes.scratchpad == Some(c) then 1 else 0)
                      + scratchpad_region_count(rest, c),
  }

private function check_scratchpads() -> bool = {
  var valid : bool = true;

  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    let d = core_class_datapath(c);
    let n = scratchpad_region_count(pma_regions, c);

    // One class has one scratchpad. R-15-167 puts it at *a* fixed address range,
    // and two ranges claiming one class's would leave `vmclear`'s single
    // unconditional pass with a choice to make (R-07-014c).
    if n > 1 then {
      valid = false;
      print_endline("The address map declares " ^ dec_str(n) ^ " scratchpad regions for the " ^ to_str(c) ^ " core class; a class's scratchpad is one fixed address range, and the partition switch's single unconditional pass has no way to choose between two.");
    };

    // Both directions, because each is a different machine. A region with no
    // class behind it is fast local memory no datapath declares; a class with no
    // region is a declared size the address map does not place, which is a
    // scratchpad software cannot address and therefore cannot manage.
    if d.scratchpad_bytes == 0 & n != 0 then {
      valid = false;
      print_endline("The address map declares a scratchpad for the " ^ to_str(c) ^ " core class, whose class table declares none; a scratchpad is a datapath's local memory tier and there is no datapath here to stream through it.");
    };
    if d.scratchpad_bytes != 0 & n == 0 then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares a scratchpad of " ^ dec_str(d.scratchpad_bytes) ^ " bytes and the address map places none; the scratchpad is software-managed, so a size with no address range is one no program can reach.");
    };

    match scratchpad_region_of(pma_regions, c) {
      None()       => (),
      Some(region) =>
        if unsigned(region.size) != d.scratchpad_bytes then {
          valid = false;
          print_endline("The " ^ to_str(c) ^ " core class declares a scratchpad of " ^ dec_str(d.scratchpad_bytes) ^ " bytes and the address map places " ^ dec_str(unsigned(region.size)) ^ " bytes at " ^ bits_str(region.base) ^ "; one structure is described twice and the two do not agree.");
        },
    };
  };

  valid
}

private function check_timing_rows(rows : list((string, timing_cycles_t))) -> bool =
  match rows {
    [||]                  => true,
    (name, cycles) :: rest => {
      var valid : bool = true;
      if cycles == 0 then {
        valid = false;
        print_endline("The timing table declares a zero latency for `" ^ name ^ "`; every row is a per-instruction latency a WCET derivation sums, so a zero is a term contributing nothing to a bound that has to be sound.");
      };
      valid & check_timing_rows(rest)
    },
  }

// The timing annotations (isa-profile.md §9, core/timing.sail).
//
// The magnitudes are R-17-041's crown-jewel specification and nothing has
// measured one, so a validator asserting a range for any of them would be the
// architectural input that requirement is waiting on, exactly as it would be for
// the memory classes below. What can be held instead is that the table says what
// kind of table it is: that every operation has a latency at all, that the one
// relation the register states between two of them holds, and that the two
// per-class switch constants exist where the instruction they price does.
private function check_timing() -> bool = {
  var valid : bool = true;
  let k = plat_timing;

  // A zero-cycle operation is not an operation. Every row is a per-instruction
  // latency a WCET derivation sums (R-11-015, R-18-024), so a zero is a term
  // silently contributing nothing to a bound that is supposed to be sound. The
  // rows are named individually rather than folded into one message because a
  // finding that says which row is the one a reader can act on.
  let rows : list((string, timing_cycles_t)) = [|
    ("integer", k.integer), ("multiply", k.multiply), ("divide", k.divide),
    ("branch", k.branch), ("csr", k.csr), ("load", k.load), ("store", k.store),
    ("atomic", k.atomic), ("cap_inspect", k.cap_inspect),
    ("cap_derive", k.cap_derive), ("cap_select", k.cap_select),
    ("cap_clear", k.cap_clear), ("cap_load", k.cap_load),
    ("cap_store", k.cap_store), ("load_tags", k.load_tags),
    ("reclaim", k.reclaim), ("block_zero", k.block_zero),
    ("block_scrub", k.block_scrub), ("vector_integer", k.vector_integer),
    ("vector_float", k.vector_float), ("vector_divide", k.vector_divide),
    ("vector_mem_unit", k.vector_mem_unit),
    ("vector_mem_indexed", k.vector_mem_indexed)
  |];
  valid = check_timing_rows(rows) & valid;

  // The one relation the register states between two of these rows, and it is a
  // shape rather than a value: an indexed or runtime-strided vector access is
  // off the data-independent-timing list and enters the table at its
  // **fully-conflicted** bound, every element resolving to one bank, where a
  // unit-stride access's bank sequence follows from the element width alone
  // (R-15-085a, R-15-085b). A fully-conflicted bound below the unconflicted one
  // is not a bound.
  if k.vector_mem_indexed < k.vector_mem_unit then {
    valid = false;
    print_endline("The indexed vector access is declared faster than the unit-stride one; the indexed row is the fully-conflicted bound, every element to one bank, and cannot be below the access whose bank sequence follows from the element width.");
  };

  // The two per-class constants, against the class table they price a switch on.
  // `vmclear` traps on a vectorless class like any unallocated encoding
  // (R-15-069d), so a latency for it there is a cost for something that cannot
  // be issued; and on a class that has the unit it is the switch's whole
  // zeroize term, so its absence would delete one of R-15-220's three
  // (R-07-014c, R-15-069e).
  foreach (i from 0 to 4) {
    let c = core_class_of_index(i);
    let t = core_class_timing(c);
    if core_class_is_vector_bearing(c) & t.vmclear_cycles == 0 then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares no `vmclear` latency; it has a vector unit, so the partition switch's eager zeroize is one of that switch's three terms and this is the term.");
    };
    if not(core_class_is_vector_bearing(c)) & t.vmclear_cycles != 0 then {
      valid = false;
      print_endline("The vectorless " ^ to_str(c) ^ " core class declares a `vmclear` latency; the encoding traps there like any unallocated one, so there is no pass to cost.");
    };
    // The fence is core surface on every class and completes at its padded bound
    // rather than early (R-15-218), so every class has the constant whether or
    // not a switch is ever taken on it.
    if t.fence_t_cycles == 0 then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " core class declares no `fence.t` latency; the fence completes at a padded per-class constant on every class, which is what keeps the store-buffer drain one term in the switch budget rather than a second beside it.");
    };
  };

  valid
}

// The two static latency classes (R-15-247, core/memory_class.sail). What is
// checked here is the shape a composition may declare, never the values: the
// numbers themselves are R-15-247m's to measure on a repaired megabit-class
// macro at part qualification, and a validator asserting a range for them would
// be the architectural input that requirement forbids. What it can hold instead
// is that the record says what the two media are.
private function check_memory_classes() -> bool = {
  var valid : bool = true;

  let first  = memory_class_constants(FirstClass);
  let second = memory_class_constants(SecondClass);

  // A class with no array behind it is not a class. Density and bank count are
  // both composition-visible capacity terms (R-15-170, R-15-247p), and a read or
  // write that takes no cycles is not a latency constant at all.
  foreach (i from 0 to 1) {
    let c = if i == 0 then FirstClass else SecondClass;
    let k = memory_class_constants(c);
    if k.usable_density_mbit_per_mm2 == 0 | k.banks == 0 then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " memory class declares a zero usable density or bank count; each class is an array with a capacity the composition can see.");
    };
    if k.read_cycles == 0 | k.write_cycles == 0 then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " memory class declares a zero read or write latency; each class enters the schedule as one fixed non-zero constant.");
    };
    if k.retention_floor_us > k.retention_ceiling_us then {
      valid = false;
      print_endline("The " ^ to_str(c) ^ " memory class declares a retention floor above its ceiling; the corner is a measured interval and the floor is its lower end.");
    };
  };

  // The first class is latched, so its retention corner, its refresh, and its
  // discharge dwell are all absent rather than small (R-15-247n). Declaring any
  // of them over a latched array is a plan describing a machine this is not.
  if first.retention_floor_us != 0 | first.retention_ceiling_us != 0 | first.refresh_cycles != 0 then {
    valid = false;
    print_endline("The first memory class declares a retention corner or a refresh latency; it is latched, so it has no refresh deadline to state.");
  };
  if first.discharge_cycles != 0 then {
    valid = false;
    print_endline("The first memory class declares a discharge dwell; its power-off is its own sanitization and there is no drain to wait out.");
  };

  // And the second class is dynamic by mechanism, so all three are present
  // rather than optional: a refresh deadline it does not state is one no
  // sequencer can be fixed against (R-15-247c, R-15-247g), and a discharge it
  // does not state is R-15-247f's dwell missing from the mode-transition budget
  // that R-15-247d's ordering is built on.
  if second.retention_floor_us == 0 | second.refresh_cycles == 0 then {
    valid = false;
    print_endline("The second memory class declares no retention floor or no refresh latency; it stores charge with no restoring feedback, so both are measured constants it must carry.");
  };
  if second.discharge_cycles == 0 then {
    valid = false;
    print_endline("The second memory class declares no discharge dwell; discharge completion is a fixed worst-corner dwell followed by one fail-stop read, so the dwell is the constant.");
  };

  // The boundary between the classes is latency-criticality (R-15-247s), so the
  // second class is the slower one on both access constants. A second class that
  // is not slower is a plan declaring one class twice, and it would make
  // R-15-247j's admission-visible placement delta zero or negative, which is the
  // one number the placement rule exists to charge.
  if second.read_cycles < first.read_cycles | second.write_cycles < first.write_cycles then {
    valid = false;
    print_endline("The second memory class is not slower than the first on read or write; the class boundary is latency-criticality and the placement delta is computed against it.");
  };

  valid
}

// The refresh and discharge sequencer (R-15-247h, sys/memory_sequencer.sail).
//
// The values in the cadence table are the composition's and this is not where
// they are judged: which simultaneous-activation set a droop, thermal-coupling,
// and power-signature envelope admits is M0.17's to decide (R-15-247g,
// R-15-247p), and a validator asserting one here would be the architectural
// input that measurement is owed. What is checked is the **shape**, and one
// arithmetic fact that is not a matter of taste at all: a refresh sweep slower
// than the class's retention floor is data lost on a schedule.
private function check_memory_sequencer() -> bool = {
  var valid : bool = true;
  let has_domain : bool = match memory_sequencer_domain() { Some(_) => true, None() => false };

  // The pairing, in both directions. A bulk domain with no sequencer decays on a
  // schedule nobody wrote (R-15-247k: RETAINED there *is* the sequencer reaching
  // it), and a sequencer with no bulk domain is a maintenance mechanism for an
  // array the memory plan did not place.
  if has_domain & not(plat_have_memory_sequencer) then {
    valid = false;
    print_endline("A memory region is placed on the second latency class but `platform.memory_sequencer` is not supported; a class that stores charge with no restoring feedback is retained by its sequencer and by nothing else.");
  };
  if plat_have_memory_sequencer & not(has_domain) then {
    valid = false;
    print_endline("`platform.memory_sequencer` is supported but no memory region is placed on the second latency class; the sequencer maintains that class and there is nothing else for it to reach.");
  };
  if not(plat_have_memory_sequencer) then return valid;

  let second = memory_class_constants(SecondClass);
  let banks = memory_sequencer_banks();
  let refresh_set = plat_memory_sequencer_refresh_banks_per_phase;
  let discharge_set = plat_memory_sequencer_discharge_banks_per_phase;

  // A class with no banks is already refused where the class record is checked,
  // and `config_is_valid` runs that first, so this is the arithmetic's
  // precondition rather than a second message saying the same thing: every
  // quantity below divides by the bank count.
  if banks <= 0 then return valid;

  // A phase's set is a subset of the class's banks, and the discharge set is no
  // larger than the refresh set: a discharge asserts every write wordline in the
  // bank (R-15-247e) where a refresh asserts a row, so whatever instantaneous
  // current the refresh set is admitted at, the discharge set is admitted at no
  // more banks than that.
  if refresh_set == 0 | refresh_set > banks then {
    valid = false;
    print_endline("`platform.memory_sequencer.banks_per_refresh_phase` is " ^ dec_str(refresh_set) ^ " but the second latency class has " ^ dec_str(banks) ^ " banks; a phase reaches at least one of them and no more than all of them.");
  };
  if discharge_set == 0 | discharge_set > refresh_set then {
    valid = false;
    print_endline("`platform.memory_sequencer.banks_per_discharge_phase` is " ^ dec_str(discharge_set) ^ " against a refresh set of " ^ dec_str(refresh_set) ^ "; a discharge asserts every write wordline in a bank where a refresh asserts a row, so its simultaneous-activation set is no larger.");
  };

  // A phase interval that does not cover the operation it issues is a schedule
  // whose phases overlap, which is the one thing the stagger exists to prevent.
  if plat_memory_sequencer_refresh_phase_cycles < second.refresh_cycles then {
    valid = false;
    print_endline("`platform.memory_sequencer.refresh_phase_cycles` is " ^ dec_str(plat_memory_sequencer_refresh_phase_cycles) ^ " but the second latency class refreshes in " ^ dec_str(second.refresh_cycles) ^ " cycles; a phase interval covers the operation it issues.");
  };
  if plat_memory_sequencer_discharge_phase_cycles < second.discharge_cycles then {
    valid = false;
    print_endline("`platform.memory_sequencer.discharge_phase_cycles` is " ^ dec_str(plat_memory_sequencer_discharge_phase_cycles) ^ " but the second latency class's discharge dwell is " ^ dec_str(second.discharge_cycles) ^ " cycles; a phase interval covers the fixed worst-corner dwell it waits out.");
  };

  // The deadline crosses from the microseconds retention is stated in to the
  // cycles the cadence is stated in, at the spine frequency (R-15-195). A spine
  // below one megahertz has no whole cycles per microsecond to cross with, which
  // is a configuration this arithmetic cannot be run against rather than a
  // schedule that is too slow.
  if plat_clock_frequency < 1000000 then {
    valid = false;
    print_endline("`platform.clock_frequency` is " ^ dec_str(plat_clock_frequency) ^ ", below one cycle per microsecond; the refresh deadline is a retention figure in microseconds read against a cadence in cycles, and there is no spine ratio to read it at.");
  } else if memory_sequencer_refresh_period_cycles() >= memory_sequencer_refresh_deadline_cycles() then {
    valid = false;
    print_endline("The refresh sweep is " ^ dec_str(memory_sequencer_refresh_phases()) ^ " phases of " ^ dec_str(plat_memory_sequencer_refresh_phase_cycles) ^ " cycles, which is " ^ dec_str(memory_sequencer_refresh_period_cycles()) ^ " cycles against a retention floor of " ^ dec_str(memory_sequencer_refresh_deadline_cycles()) ^ "; a sweep that does not finish inside the floor loses the data it was maintaining.");
  };

  // And the domain divides into its class's banks exactly, each bank into whole
  // chunks of the widest access the memory interface takes. A remainder is a
  // sliver of the array no phase reaches, which is the failure mode a schedule
  // stated in banks rather than in addresses is otherwise silent about.
  match memory_sequencer_domain() {
    None() => (),
    Some(region) => {
      let size = unsigned(region.size);
      if size % banks != 0 then {
        valid = false;
        print_endline("The second-class region starting at " ^ bits_str(region.base) ^ " is " ^ dec_str(size) ^ " bytes over " ^ dec_str(banks) ^ " banks, which does not divide; a bank is a whole share of the domain and no part of it is left unreached.");
      } else if memory_sequencer_bank_bytes() % memory_sequencer_chunk_bytes != 0 then {
        valid = false;
        print_endline("A bank of the second-class region is " ^ dec_str(memory_sequencer_bank_bytes()) ^ " bytes, which is not a whole number of " ^ dec_str(memory_sequencer_chunk_bytes) ^ "-byte accesses; the discharge drains a bank through the memory interface's own widest write and leaves no remainder.");
      };
    },
  };

  valid
}

function config_is_valid() -> bool = {
    check_tvec()
  & check_core_roster()
  & check_scratchpads()
  & check_timing()
  & check_memory_classes()
  & check_memory_sequencer()
  & check_revocation()
  & check_mstatus_fields()
  & check_physaddr_bits()
  & check_mem_layout()
  & check_vlen_elen()
  & check_vext_config()
  & check_misc_extension_dependencies()
  & check_extension_param_constraints()
}
