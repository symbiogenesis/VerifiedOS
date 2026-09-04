// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Put the illegal instructions last to use their wildcard match.

// *****************************************************************

mapping clause encdec = ILLEGAL(s) <-> s

function clause execute ILLEGAL(_s) = Illegal_Instruction()

mapping clause assembly = ILLEGAL(s) <-> "illegal" ^ spc() ^ hex_bits_32(s)

// The 16-bit companion of the clause above is gone with the fetch's length
// decision: `C` is excluded and ILEN is fixed at 32, so no parcel reaches a
// decode and `ILLEGAL` above carries every word this machine allocates no
// encoding to, whole (R-15-036, R-15-014, postlude/fetch.sail).

// *****************************************************************

// End definitions
end extension
end extensionName
end hartSupports
end currentlyEnabled
end instruction
end execute
end assembly
end encdec

// Some legal instructions do not have any corresponding assembly, e.g. a `fence`
// carrying a non-zero `rs1` or `rd`. A reserved `fence` is no longer an example:
// reserved `fm` values trap rather than executing as `fm`=0000 (R-15-014,
// R-15-017), so the class that survives is the one the base ISA reserves for a
// *future* extension rather than the one it reserves for none.
function instruction_to_str(insn : instruction) -> string =
  if assembly_forwards_matches(insn) then assembly(insn) else (".insn " ^ bits_str(encdec(insn)))

overload to_str = {instruction_to_str}
