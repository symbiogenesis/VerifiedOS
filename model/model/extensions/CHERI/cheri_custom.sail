// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The profile's capability instructions in **custom opcode space**: the rows
// that are net-new here rather than narrowed from ISAv9, so no upstream clause
// stands behind any of them (isa-profile.md §3).
//
// **They spend one opcode between them, and that is a decision rather than an
// accident.** RISC-V reserves four custom opcodes and this dialect has already
// spent one of them, ISAv9 having put the whole capability surface at
// `0b1011011` (custom-2/rv128). Custom opcode space is what the freeze's single
// measured act makes the candidates compete for (R-15-014a, R-15-067e), so
// every row here takes custom-0 (`0b0001011`) and is separated by `funct3`,
// leaving custom-1 and custom-3 whole for the rows the measurement admits.
// `vmclear` takes `funct3` 001 in the same opcode from
// extensions/platform/vmclear.sail, being platform surface rather than
// capability surface; four rows, one opcode.
//
// The `funct3` assignment is not arbitrary either: the indexed load and store
// carry `ld`'s and `sd`'s own width code in the low bits, so a reader reads the
// width off the same three bits the base ISA puts it in.

// *****************************************************************
// The masked register clear (R-15-069a, R-15-069b).
//
// `cclear h, mask` clears the sixteen registers `mask` selects within the half
// `h` selects, writing each to the all-zeroes granule that decodes as untagged
// NULL (R-15-182), so two of them clear the merged file (R-15-007i).
//
// **It exists for the compartment switch and not the partition switch.** A
// partition switch is covered structurally, the restore being total over every
// register a partition can name (R-07-015, R-15-214); a cross-compartment call
// is covered by nothing, and the switcher's scrub of some two dozen registers
// per call and per return is on the platform's only inter-compartment path. The
// dictionary encoding does not answer it, because it is a *byte* instrument: a
// stereotyped clear of a fixed register is site-invariant and so is already one
// dictionary slot, but two dozen slots still issue two dozen times. What this
// removes it removes from the **bound** and not from the mean, the clear being
// unconditional and its worst case therefore its every case.
//
// It is the one instruction on the machine that can only ever *destroy*
// authority, so monotonicity is trivial rather than argued; and its latency is
// independent of the mask's population as well as of the operand values, so it
// joins the `Zkt` list with one entry in the timing-annotated model (M0.9).
//
// ISAv9's own `CClearRegs` is not what this is, and its deletion upstream is
// not inherited: that instruction addressed the quadrants of a *split* file,
// which a merged register file makes meaningless, and its low bit named DDC.
// This one runs over the merged file and names no default data capability
// (R-15-069b, R-15-001c).
//
// **The field layout is S-type, unchanged.** The two register fields and the
// split immediate sit where a store puts them; what differs is that the
// instruction reads them as a constant rather than as registers, because the
// mask names the destinations and so no destination register is named. The
// mask is the twelve immediate bits and the low four of the `rs2` field, the
// half selector is that field's top bit, and the `rs1` field is reserved: an
// encoding with a non-zero `rs1` decodes to nothing and therefore traps
// (R-15-014).

union clause instruction = CClear : (bits(1), bits(16))

mapping clause encdec = CClear(h, mask)
  <-> mask[11 .. 5] @ h @ mask[15 .. 12] @ 0b00000 @ 0b000 @ mask[4 .. 0] @ 0b0001011

function clause execute CClear(h, mask) = {
  let half : range(0, 16) = if h == 0b1 then 16 else 0;
  foreach (i from 0 to 15) {
    // The register is named as an offset from `x0` rather than built out of an
    // index, because the width of a register index is configuration-dependent
    // upstream (`base_E_enabled`) and this arithmetic must not be.
    if mask[i] == bitone then C(zreg + (half + i)) = null_cap
  };
  RETIRE_SUCCESS
}

mapping clause assembly = CClear(h, mask)
  <-> "cclear" ^ spc() ^ hex_bits_1(h) ^ sep() ^ hex_bits_16(mask)

// *****************************************************************
// The capability indexed load and store (R-15-007e, R-15-007f, R-15-007g).
//
// `cld rd, cs1[rs2 << scale]` and `csd rs3, cs1[rs2 << scale]`: the authorising
// capability is checked at **base plus scaled index** and the access is
// performed there, with no intermediate capability materialized at any point.
//
// **It is the one row in the profile that is *less* capability semantics rather
// than more.** `cincoffset` may produce a capability outside the representable
// region, a case the Sail model, the CHERI-TAL soundness metatheorem, and the
// Cerise universal contract each carry; a single indexed access never
// constructs that intermediate, so the case *leaves* the dereference path
// rather than being discharged on it. At this dialect's 128-byte exactness
// threshold that case is the common one on an indexed dereference rather than
// the large-object one, which is what makes the narrowing worth more here than
// it would be at 128 bits (§4.1, R-15-007c).
//
// Its ground is bytes: the offset-then-dereference pair it replaces is already
// fused, so the issue slot is collected and what remains is the four bytes of
// image and of fetch bandwidth the pair still occupies. The fusion pair is
// therefore **narrowed, not deleted** — the sequence stays legal and stays
// emitted wherever this form does not apply (R-15-031a).
//
// **Membership is doubleword and its store form, because that is what the
// register enumerates.** A `clw` or `clh` would be inheritance from the base
// ISA's width ladder, and nothing enters this profile by inheritance
// (R-15-007j): a curator wanting one adds a row to the register first.
//
// The scale is a two-bit field, so the admitted shifts are 0 through 3, which
// is `Zba`'s own `sh1add`…`sh3add` ladder plus the unscaled case. **Which of
// them the backend emits is the composition-time selection R-15-007g names**;
// the width of the field is what the freeze fixes. The high five bits of the
// `funct7` field are reserved and decode to nothing.
//
// The store form reads its source register out of the `rd` slot, which is what
// a three-register store has to do in an R-type layout and is exactly how RVV
// encodes `vs3` in its own stores.

union clause instruction = CIndexedLoad  : (bits(2), regidx, regidx, regidx)
union clause instruction = CIndexedStore : (bits(2), regidx, regidx, regidx)

mapping clause encdec = CIndexedLoad(scale, rs2, cs1, rd)
  <-> 0b00000 @ scale @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b011 @ encdec_reg(rd) @ 0b0001011

mapping clause encdec = CIndexedStore(scale, rs2, cs1, rs3)
  <-> 0b00000 @ scale @ encdec_reg(rs2) @ encdec_reg(cs1) @ 0b111 @ encdec_reg(rs3) @ 0b0001011

// The scaled index, as an offset from the authorising capability's address.
// `data_read` and `data_write` check the authority at address-plus-offset and
// access it there (sys/mem_access.sail, core/addr_checks.sail), which is the
// whole of *no intermediate capability materialized*: there is no derivation
// step for a representability question to arise in.
function scaled_index(rs2 : regidx, scale : bits(2)) -> xlenbits =
  X(rs2) << unsigned(scale)

function clause execute CIndexedLoad(scale, rs2, cs1, rd) =
  match data_read(cs1, scaled_index(rs2, scale), 8, Load(Data), false, false) {
    Ok(data) => { X(rd) = data; RETIRE_SUCCESS },
    Err(e)   => e,
  }

function clause execute CIndexedStore(scale, rs2, cs1, rs3) =
  match data_write(cs1, scaled_index(rs2, scale), 8, X(rs3), Store(Data), false, false) {
    Ok(_)  => RETIRE_SUCCESS,
    Err(e) => e,
  }

mapping clause assembly = CIndexedLoad(scale, rs2, cs1, rd)
  <-> "cld" ^ spc() ^ reg_name(rd) ^ sep() ^ cap_reg_name(cs1) ^ "[" ^ reg_name(rs2)
      ^ spc() ^ "<<" ^ spc() ^ hex_bits_2(scale) ^ "]"

mapping clause assembly = CIndexedStore(scale, rs2, cs1, rs3)
  <-> "csd" ^ spc() ^ reg_name(rs3) ^ sep() ^ cap_reg_name(cs1) ^ "[" ^ reg_name(rs2)
      ^ spc() ^ "<<" ^ spc() ^ hex_bits_2(scale) ^ "]"
