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
  if vector_support_level >= Float_single & not(config extensions.F.supported : bool) then {
    valid = false;
    print_endline("Zve*f is enabled but F is disabled: supporting Zve*f requires F.");
  };
  if vector_support_level >= Float_double then {
    if (elen_exp : nat) < 6 then {
      valid = false;
      print_endline("Zve*d is enabled but ELEN is 2^" ^ dec_str(elen_exp) ^ ": ELEN must be >= 2^6");
    };
    if not(hartSupports(Ext_D)) then {
      valid = false;
      print_endline("Zve*d is enabled but D is disabled: supporting Zve*d requires D.");
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
  if (config extensions.Zvfh.supported : bool) & (not(hartSupports(Ext_Zve32f)) | not(config extensions.Zfhmin.supported : bool)) then {
    valid = false;
    print_endline("Zvfh is enabled but Zve32f and/or Zfhmin are disabled: Zvfh requires Zve32f and Zfhmin.");
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
    let sig_supported : bool = config platform.simple_interrupt_generator.supported;
    let sig_ok   = not(sig_supported) |
                   within_configured_pma_memory("simple interrupt generator (platform.simple_interrupt_generator)", Some(IOMemory),
                                                to_bits_checked(config platform.simple_interrupt_generator.base : int),
                                                zero_extend(plat_sig_size));
    pmas_ok & clint_ok & sig_ok
  }

private function check_misc_extension_dependencies() -> bool = {
  var valid : bool = true;
  if (config extensions.F.supported : bool) & (config extensions.Zfinx.supported : bool) then {
    valid = false;
    print_endline("The F and Zfinx extensions are mutually exclusive and cannot be supported simultaneously.");
  };
  // See https://github.com/riscv/sail-riscv/issues/1508 for the next two checks.
  if (config extensions.Zabha.supported : bool) & not((config extensions.Zaamo.supported : bool) | (config extensions.A.supported : bool)) then {
    valid = false;
    print_endline("The Zabha extension is enabled but Zaamo and A are disabled: supporting Zabha requires Zaamo or A.");
  };
  if (config extensions.Zacas.supported : bool) & not((config extensions.Zaamo.supported : bool) | (config extensions.A.supported : bool)) then {
    valid = false;
    print_endline("The Zacas extension is enabled but Zaamo and A are disabled: supporting Zacas requires Zaamo or A.");
  };
  if (config extensions.Zfinx.supported : bool) & not(config extensions.Zicsr.supported : bool) then {
    valid = false;
    print_endline("The Zfinx extensions is enabled but Zicsr is disabled: supporting Zfinx requires Zicsr.");
  };
  if (config extensions.Zdinx.supported : bool) & not(config extensions.Zfinx.supported : bool) then {
    valid = false;
    print_endline("The Zdinx extensions is enabled but Zfinx is disabled: supporting Zdinx requires Zfinx.");
  };
  if (config extensions.Zhinx.supported : bool) & not(config extensions.Zfinx.supported : bool) then {
    valid = false;
    print_endline("The Zhinx extensions is enabled but Zfinx is disabled: supporting Zhinx requires Zfinx.");
  };
  if (config extensions.Zhinxmin.supported : bool) & not(config extensions.Zfinx.supported : bool) then {
    valid = false;
    print_endline("The Zhinxmin extensions is enabled but Zfinx is disabled: supporting Zhinxmin requires Zfinx.");
  };
  if (config extensions.Zfbfmin.supported : bool) & not(config extensions.F.supported : bool) then {
    valid = false;
    print_endline("The Zfbfmin extension is enabled but F is disabled: supporting Zfbfmin requires F.");
  };
  if (config extensions.Zvfbfmin.supported : bool) & not(hartSupports(Ext_Zve32f)) then {
    valid = false;
    print_endline("The Zvfbfmin extension is enabled but Zve32f is disabled: supporting Zvfbfmin requires Zve32f.")
  };
  if (config extensions.Zvfbfwma.supported : bool) & (not(config extensions.Zfbfmin.supported : bool) | not(config extensions.Zvfbfmin.supported : bool)) then {
    valid = false;
    print_endline("The Zvfbfwma extension is enabled but either Zfbfmin or Zvfbfmin is disabled: supporting Zvfbfwma requires Zfbfmin and Zvfbfmin.")
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

private function check_mmio_devices() -> bool = {
  var valid : bool = true;
  if plat_sig_base[1 .. 0] != zeros() then {
    valid = false;
    print_endline("platform.simple_interrupt_generator.base is not 4-byte aligned.");
  };
  valid
}

private function check_mstatus_fields() -> bool = {
  var valid : bool = true;

  let legal_fs : ExtContextPolicy = config base.mstatus.fs_legal_states;
  if (config extensions.Zfinx.supported : bool) then {
    if legal_fs != ExtContext_Off then {
      valid = false;
      print_endline("The Zfinx extension is enabled but `base.mstatus.fs_legal_states` is not set to `ExtContext_Off`: `mstatus.FS` needs to be read-only zero (i.e. `base.mstatus.fs_legal_states` should be set to `ExtContext_Off`).")
    }
  } else if (config extensions.F.supported : bool) then {
    if legal_fs == ExtContext_Off then {
      valid = false;
      print_endline("The F extension is enabled but `base.mstatus.fs_legal_states` is set to `ExtContext_Off`, which makes `mstatus.FS` read-only zero: it cannot be read-only zero.")
    }
  } else if legal_fs != ExtContext_Off then {
    valid = false;
    print_endline("The F extension is not enabled, but `base.mstatus.fs_legal_states` is not set to `ExtContext_Off`; i.e. `mstatus.FS` is not read-only zero: it should be read-only zero.");
  };

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
  } else if physaddr_bits_nat > 34 & xlen == 32 then {
    print_endline("`memory.physaddr_bits` is " ^ dec_str(physaddr_bits) ^ " but cannot be greater than 34 for RV32.");
    false
  } else if physaddr_bits_nat < 13 then {
    print_endline("`memory.physaddr_bits` is " ^ dec_str(physaddr_bits) ^ " but values smaller than 13 are not supported.");
    false
  } else { true }
}

function config_is_valid() -> bool = {
    check_tvec()
  & check_mstatus_fields()
  & check_physaddr_bits()
  & check_mem_layout()
  & check_mmio_devices()
  & check_vlen_elen()
  & check_vext_config()
  & check_misc_extension_dependencies()
  & check_extension_param_constraints()
}
