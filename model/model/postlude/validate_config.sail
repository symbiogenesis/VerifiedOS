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
  match (pma.mem_type, pma.memory_class) {
    (MainMemory, None()) => {
      print_endline("Main memory region starting at " ^ bits_str(region.base) ^ " declares no `memory_class`; the static memory plan places every array on one of the two latency classes.");
      return false;
    },
    (IOMemory, Some(c)) => {
      print_endline("IO memory region starting at " ^ bits_str(region.base) ^ " declares `memory_class` " ^ to_str(c) ^ "; the latency classes are main-memory media and a device endpoint is on neither.");
      return false;
    },
    (_, _) => (),
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
    pmas_ok & clint_ok & imsic_ok & revocation_window_ok
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

function config_is_valid() -> bool = {
    check_tvec()
  & check_memory_classes()
  & check_revocation()
  & check_mstatus_fields()
  & check_physaddr_bits()
  & check_mem_layout()
  & check_vlen_elen()
  & check_vext_config()
  & check_misc_extension_dependencies()
  & check_extension_param_constraints()
}
