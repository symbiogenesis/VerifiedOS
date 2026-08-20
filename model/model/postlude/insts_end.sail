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

// *****************************************************************

mapping clause encdec_compressed = C_ILLEGAL(s) <-> s

function clause execute C_ILLEGAL(_s) = Illegal_Instruction()

mapping clause assembly = C_ILLEGAL(s) <-> "c.illegal" ^ spc() ^ hex_bits_16(s)

// *****************************************************************

// The wildcard the capability-mode decode falls through to, which is how a
// capability-mode fetch says "this encoding is not one of mine" and defers to
// the ordinary decode (postlude/decode_ext.sail). It is never executed.

union clause instruction = NOT_CAPMODE : word

mapping clause encdec_capmode = NOT_CAPMODE(s) <-> s

function clause execute NOT_CAPMODE(s) = {
  internal_error(__FILE__, __LINE__, "NOT_CAPMODE should never be executed: " ^ bits_str(s));
  RETIRE_SUCCESS
}

mapping clause assembly = NOT_CAPMODE(s) <-> "not_capmode" ^ spc() ^ hex_bits_32(s)

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
end encdec_compressed
end encdec_capmode

// Some legal instructions do not have any corresponding assembly, e.g. reserved fences.
function instruction_to_str(insn : instruction) -> string =
  if assembly_forwards_matches(insn) then assembly(insn) else (".insn " ^ bits_str(encdec(insn)))

overload to_str = {instruction_to_str}
