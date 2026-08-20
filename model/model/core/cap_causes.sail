// =======================================================================================
// Ported from the CHERI-RISC-V Sail model (CTSRD-CHERI/sail-cheri-riscv @ bb07488d,
// src/cheri_types.sail), which is subject to the BSD two-clause licence in
// model/LICENCE.cheri.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The capability violation causes and the register they name.
//
// A capability violation raises one cause code in `mcause` and reports its
// detail in `mtval`: the violation type in the low five bits and the register
// that raised it above them. The codes are ISAv9's, frozen with the profile,
// and there is no bespoke CHERI cause or trap-value bank beside them
// (R-15-073a, R-15-014).

// Register identifiers as a capability fault reports them: the 32 registers of
// the merged file, plus PCC, which has no index in the file because it is not
// in it.
type capreg_idx = bits(6)
let PCC_IDX : capreg_idx = 0b100000
let DDC_IDX : capreg_idx = 0b100001

// The index a fault reports for a general-purpose register.
function capreg_idx_of_regidx(Regidx(r) : regidx) -> capreg_idx = zero_extend(r)

enum CapEx = {
  CapEx_None,
  CapEx_LengthViolation,
  CapEx_TagViolation,
  CapEx_SealViolation,
  CapEx_TypeViolation,
  CapEx_UserDefViolation,
  CapEx_UnalignedBase,
  CapEx_GlobalViolation,
  CapEx_PermitExecuteViolation,
  CapEx_PermitLoadViolation,
  CapEx_PermitStoreViolation,
  CapEx_PermitLoadCapViolation,
  CapEx_PermitStoreCapViolation,
  CapEx_PermitStoreLocalCapViolation,
  CapEx_AccessSystemRegsViolation,
  CapEx_PermitCInvokeViolation,
  CapEx_PermitSetCIDViolation,
}

function CapExCode(ex : CapEx) -> bits(5) =
  match ex {
    CapEx_None                          => 0b00000,
    CapEx_LengthViolation               => 0b00001,
    CapEx_TagViolation                  => 0b00010,
    CapEx_SealViolation                 => 0b00011,
    CapEx_TypeViolation                 => 0b00100,
    CapEx_UserDefViolation              => 0b01000,
    CapEx_UnalignedBase                 => 0b01011,
    CapEx_GlobalViolation               => 0b10000,
    CapEx_PermitExecuteViolation        => 0b10001,
    CapEx_PermitLoadViolation           => 0b10010,
    CapEx_PermitStoreViolation          => 0b10011,
    CapEx_PermitLoadCapViolation        => 0b10100,
    CapEx_PermitStoreCapViolation       => 0b10101,
    CapEx_PermitStoreLocalCapViolation  => 0b10110,
    CapEx_AccessSystemRegsViolation     => 0b11000,
    CapEx_PermitCInvokeViolation        => 0b11001,
    CapEx_PermitSetCIDViolation         => 0b11100,
  }

function string_of_capex(ex : CapEx) -> string =
  match ex {
    CapEx_None                          => "None",
    CapEx_LengthViolation               => "LengthViolation",
    CapEx_TagViolation                  => "TagViolation",
    CapEx_SealViolation                 => "SealViolation",
    CapEx_TypeViolation                 => "TypeViolation",
    CapEx_UserDefViolation              => "UserDefViolation",
    CapEx_UnalignedBase                 => "UnalignedBounds",
    CapEx_GlobalViolation               => "GlobalViolation",
    CapEx_PermitExecuteViolation        => "PermitExecuteViolation",
    CapEx_PermitLoadViolation           => "PermitLoadViolation",
    CapEx_PermitStoreViolation          => "PermitStoreViolation",
    CapEx_PermitLoadCapViolation        => "PermitLoadCapViolation",
    CapEx_PermitStoreCapViolation       => "PermitStoreCapViolation",
    CapEx_PermitStoreLocalCapViolation  => "PermitStoreLocalCapViolation",
    CapEx_AccessSystemRegsViolation     => "AccessSystemRegsViolation",
    CapEx_PermitCInvokeViolation        => "PermitCInvokeViolation",
    CapEx_PermitSetCIDViolation         => "PermitSetCIDViolation",
  }

// The `mtval` payload of a capability violation.
function capex_tval(capEx : CapEx, regnum : capreg_idx) -> xlenbits =
  zero_extend(regnum @ CapExCode(capEx))
