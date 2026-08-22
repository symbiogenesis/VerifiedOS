// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// `vmclear`, the vector/matrix all-state clear (R-15-069d, R-15-069e).
//
// One unconditional, mask-independent pass over the whole of the unit state the
// partition switch zeroizes and does not save: the vector register file, the
// vector CSRs, the matrix unit's architectural state, and the class's
// software-managed scratchpad (R-07-014a, R-07-014c).
//
// **It is admitted on cycles, and on the bound rather than the mean.** The
// sequence it replaces is a `cbo.zero` and `cclear` loop whose per-class trip
// count the kernel proof and the §11 table would otherwise carry as a term; the
// clear is unconditional, so what one instruction removes it removes from the
// worst case and not from an average over how much of the unit the outgoing
// partition happened to touch (R-15-069b, R-15-069e). That is also why there is
// no mask and no operand: a `vmclear` that could be told *what* to clear would
// have a trip count again.
//
// It takes no operand the clear could depend on and names no destination
// register, the class's unit-state inventory naming them all, so its latency is
// one fixed per-class entry in the timing-annotated model (M0.9, R-15-053).
//
// **The inventory is enumerated here rather than gestured at, and the two
// members the core classes brought are enumerated the same way.** It is stated
// the way `fence.t` states its flush set
// (extensions/platform/fence_t.sail):
//
//   - The **vector register file** is `v0`–`v31` at the class's VLEN, cleared
//     below through the same `init_vregs` reset uses. Its width is the class's,
//     so the clear is per-class in cycles and identical in content.
//   - The **vector CSRs** are `vl`, `vtype` and `vcsr`, cleared below to the
//     values reset gives them. `vstart` is not among them, being excluded
//     (R-15-039a), and no scalar rounding mode or accrued-flag CSR is either,
//     scalar floating point being deleted and rounding static (R-15-083).
//   - The **class's software-managed scratchpad** is the region the address map
//     declares for this hart's class (sys/pma.sail, R-15-165, R-15-167), cleared
//     below in whole 4 KiB chunks, which divide it exactly because every PMA
//     region is 4 KiB-aligned in base and size
//     (postlude/validate_config.sail). A class declaring none contributes no
//     chunk rather than a skipped step, which is what keeps the pass
//     unconditional: the trip count is a composition constant and never a
//     function of what the outgoing partition touched.
//   - The **matrix unit's architectural state** is empty, and that is an
//     enumeration result rather than a milestone's residue. R-15-117 keeps
//     de-quantization and block-scale application in software on the same
//     class's vector unit, so no block-scale register enters the frozen matrix
//     ISA; the ACE/SME architectural tile file is evaluated and **not imported**
//     for the same reason, a dedicated tile state being context to save, state
//     to zeroize, and Sail and switch-proof surface
//     ([architectural-alternatives.md](../../../../docs/architectural-alternatives.md));
//     and R-15-118's coprocessor line leaves the unit no state of its own to
//     hold operands in, every byte it moves being core-issued against an
//     explicit capability operand. What is left for a partition to dirty is the
//     scratchpad the array streams through, which is the member above. So the
//     matrix half of the inventory is *nothing*, and this paragraph is what says
//     so rather than a clause that clears nothing without explaining why.
//
// The one thing the inventory still owes is the matrix unit's **instruction**
// surface, and it is owed by the profile rather than by this file: the frozen
// profile books the matrix extension as a unit and names no instruction, no
// mnemonic, and no encoding for it, where every other bespoke row beside it
// names all three (isa-profile.md §3, R-15-009, R-15-116). Nothing enters the
// profile by inheritance (R-15-007j), so there is no instruction here to admit
// and the encoding below does not change when one is.
//
// **On a vectorless class the encoding traps like every other unallocated
// encoding** (R-15-014), which is what the decode guard below says: a class with
// no vector unit has no unit state to clear, and an instruction that quietly
// retired having cleared nothing would report success for a zeroize that did not
// happen.
//
// **The guard is `hartSupports` and not `currentlyEnabled`, and the difference
// is load-bearing rather than stylistic.** The register's word is *class*, which
// is a static property of the hart; `currentlyEnabled(Ext_Zve32x)` folds in
// `mstatus.VS != Off`, which is dynamic state the executing partition can write
// (core/sys_regs.sail). Gating on the dynamic predicate would make the switch's
// zeroize conditional on a bit the outgoing partition controls: a partition
// could dirty the vector unit, write `VS` back to `Off`, and leave a `vmclear`
// to trap on the switch that was supposed to erase it, which is residue
// surviving a switch by the partition's own choice (R-07-014a, R-15-214). It
// would also make the clear conditional in the sense R-15-069c rejects, since
// the switcher would have to read `VS` before issuing it and the cost would
// again be a function of what the outgoing partition did.
//
// Nothing here writes `mstatus`. `VS` is the extension-context gate a lazy
// save-restore uses, this platform has no lazy anything, and the switch's
// restore over every register a partition can name covers it structurally
// (R-07-015); an instruction that cleared unit state *and* edited machine status
// would be doing two jobs, one of them the switch's.
//
// The encoding is custom-0 `funct3` 001, beside `cclear`'s 000 and below the
// indexed access's width-coded 011 and 111 (extensions/CHERI/cheri_custom.sail).
// Every other field is zero and reserved, so a non-zero field decodes to nothing
// and traps. The four rows in that opcode spend one between them, which is the
// point: custom opcode space is what the freeze's single measured act makes the
// remaining candidates compete for, so custom-1 and custom-3 stay whole
// (R-15-014a, R-15-067e).

union clause instruction = VMClear : unit

mapping clause encdec = VMClear()
  <-> 0b0000000 @ 0b00000 @ 0b00000 @ 0b001 @ 0b00000 @ 0b0001011
  when hartSupports(Ext_Zve32x)

// The scratchpad half of the pass (R-07-014c, R-15-165, R-15-167).
//
// **It is a physical write and carries no capability**, which is forced rather
// than convenient: the instruction takes no operand, so there is no authority
// for it to be checked against, and the range it covers is the composition's
// rather than a program's. That is the same footing the register-file half
// stands on, `init_vregs` writing the file without anything authorizing it, and
// in RTL it is the same reset-wire array clear (R-15-069e).
//
// **The write clears the validity tag of every granule it covers for free**,
// tag clearing being a property of the write path rather than an instruction
// (R-15-007r): the plain `mem_write_value` passes `default_meta`, so a
// scratchpad holding capabilities is left holding neither the data nor the
// authority. That is the disclosure half of the zeroize discipline and it needs
// no clause of its own here (R-15-060, R-15-182).
//
// The chunk is the memory interface's own widest access, so how many granules a
// call clears is that interface's business and not this file's, exactly as it is
// for the discharge pass over the second class (sys/memory_sequencer.sail).
// A failed chunk is not retried and does not stop the pass: a `vmclear` that
// could take a different number of steps depending on what it found would have
// the trip count R-15-069e admits it for removing, and the composition that
// could produce one is refused before it runs (postlude/validate_config.sail).
private function vmclear_scratchpad() -> unit =
  match this_core_class() {
    None()  => (),
    Some(c) => {
      let (base, size) = scratchpad_extent_of(c);
      let chunk  = sizeof(max_mem_access);
      let chunks = unsigned(size) / chunk;
      foreach (i from 0 to (chunks - 1)) {
        let paddr = Physaddr(base + to_bits_truncate(64, i * chunk));
        match mem_write_ea(paddr, chunk, Store(Data), false, false) {
          Err(_, _) => (),
          Ok(_)     =>
            match mem_write_value(paddr, chunk, zeros(), Store(Data), false, false) {
              Ok(_)     => (),
              Err(_, _) => (),
            },
        }
      }
    },
  }

// The CSR half is cleared to the values `reset_sys` writes rather than to zeroes
// (sys/sys_control.sail), and `vtype` is why the distinction is not pedantic: an
// all-zeroes `vtype` is a *valid* configuration, SEW=8 at LMUL=1, so a clear
// that wrote zeroes would leave the successor partition a usable vector
// configuration it never selected. `vill` is what "no configuration" is spelled
// as, so that is what a cleared `vtype` holds.
//
// Every CSR the clear writes reports through the commit-trace callback, because
// the corpus adjudicates on that trace and unit state that changed without
// saying so is a change the rig cannot see (M0.12).
function clause execute VMClear() = {
  init_vregs();
  vmclear_scratchpad();

  vl               = zeros();
  vtype[vill]      = 0b1;
  vtype[reserved]  = zeros();
  vtype[vma]       = 0b0;
  vtype[vta]       = 0b0;
  vtype[vsew]      = 0b000;
  vtype[vlmul]     = 0b000;
  vcsr[vxrm]       = 0b00;
  vcsr[vxsat]      = 0b0;

  csr_write_callback("vl", vl);
  csr_write_callback("vtype", vtype.bits);
  csr_write_callback("vcsr", zero_extend(vcsr.bits));
  csr_write_callback("vxsat", zero_extend(vcsr[vxsat]));
  csr_write_callback("vxrm", zero_extend(vcsr[vxrm]));

  RETIRE_SUCCESS
}

mapping clause assembly = VMClear() <-> "vmclear"
