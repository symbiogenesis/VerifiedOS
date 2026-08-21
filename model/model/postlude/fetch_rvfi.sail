// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

private function rvfi_fetch() -> FetchResult = {
  rvfi_inst_data[rvfi_order] = retire_count;
  rvfi_pc_data[rvfi_pc_rdata] = zero_extend(get_arch_pc());
  // The trace's mode field reports the one mode there is.
  rvfi_inst_data[rvfi_mode] = zero_extend(0b11);
  rvfi_inst_data[rvfi_ixl] = zero_extend(misa[MXL]);

  // First allow extensions to check pc
  match ext_fetch_check_pc(PC, PC, min_instruction_bytes) {
    Some(e) => return F_Ext_Error(e),
    None()  => (),
  };

  // Then check PC alignment: instructions are 32 bits wide and 4-byte aligned.
  if   PC[1 .. 0] != 0b00
  then return F_Error(E_Fetch_Addr_Align(), PC);

  let i = rvfi_instruction[rvfi_insn];
  rvfi_inst_data[rvfi_insn]   = zero_extend(i);
  if   (i[1 .. 0] != 0b11)
  then return F_RVC(i[15 .. 0]);

  // fetch PC check for the next instruction granule
  let PC_hi = PC + 2;
  match ext_fetch_check_pc(PC, PC_hi, 2) {
    Some(e) => F_Ext_Error(e),
    None()  => F_Base(i),
  }
}
