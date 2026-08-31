// SPDX-License-Identifier: Apache-2.0
//
// The model's own answers about the capability format, printed as text.
//
// This is the model side of the cross-check `tools/run.py rtl crosscheck` runs, and
// the method is M2.1's rather than a new one: compile the curated model's own
// `prelude`, `core/xlen.sail`, `core/cap_format.sail` and `core/cap_common.sail`
// together with this generator, call those functions, print what they return, and
// require the other implementation to reproduce every line. The vectors cross as
// text, so no adapter sits between the two implementations and neither is
// compiled against the other's types.
//
// Nothing here decides anything. It picks inputs and formats answers; every value
// on the right of an arrow is the model's, and a line this file cannot print is a
// line the cross-check does not reach.
//
// **The line format.** One vector per line, `<kind> <inputs> -> <outputs>`, every
// field lowercase hex with no prefix and a width fixed by the field's own bit
// width, so that a reproducing implementation holding each field in a variable of
// that width prints the same digits with a bare `%x`. Blank lines and lines
// opening with `#` are commentary. The kinds:
//
//   dec <tag> <bits>                 the decode, the re-encode, the bounds, the
//                                    length and the malformed predicate
//   sb  <bits> <base> <top>          the narrowing `csetbounds` performs
//   sa  <tag> <bits> <addr>          the address setter and its checked form
//   so  <tag> <bits> <offset>        the offset setter and its checked form
//   io  <tag> <bits> <delta>         the increment form
//   frc <bits> <inc>                 the fast representability check
//   ib  <bits> <addr> <size>         the bounds check
//   pe  <code>                       the permission expansion, and the twelve
//                                    accessors that index what it returns
//   pn  <mask>                       the largest admitted set inside a mask
//   sl  <bits> <otype>               sealing, the reserved types and the sentry edges
//   mb  <tag> <bits>                 the null transform across the memory interface
//   it  <value>                      an integer read as a capability
//   ac  <bits>                       the accessors over the decoded bounds
//
// **Why the tag on a `dec` line is derived rather than chosen.** `getCapLength`
// asserts that a tagged capability has its top at or above its base, and the
// sweep below walks the whole 19-bit bounds encoding, most of whose members are
// reachable only untagged. So each `dec` vector is emitted tagged exactly when
// its own decode is well formed, which keeps the assertion true, exercises the
// tag through decode, and puts the malformed encodings on the untagged side where
// the architecture already puts them.

// *****************************************************************
// Formatting. Fixed width, lowercase, no prefix, and stated per width rather
// than derived, so that the digits a field occupies are a property of the field
// and not of the value in it.

function nib(n : bits(4)) -> string = match n {
  0x0 => "0", 0x1 => "1", 0x2 => "2", 0x3 => "3",
  0x4 => "4", 0x5 => "5", 0x6 => "6", 0x7 => "7",
  0x8 => "8", 0x9 => "9", 0xa => "a", 0xb => "b",
  0xc => "c", 0xd => "d", 0xe => "e", 0xf => "f",
}

function h1(x : bits(4)) -> string = nib(x)

function h2(x : bits(8)) -> string = nib(x[7 .. 4]) ^ nib(x[3 .. 0])

function h3(x : bits(12)) -> string = h1(x[11 .. 8]) ^ h2(x[7 .. 0])

function h9(x : bits(36)) -> string =
  h1(x[35 .. 32]) ^ h2(x[31 .. 24]) ^ h2(x[23 .. 16]) ^ h2(x[15 .. 8]) ^ h2(x[7 .. 0])

function h10(x : bits(37)) -> string = h1(zero_extend(x[36 .. 36])) ^ h9(x[35 .. 0])

function h16(x : bits(64)) -> string =
  h2(x[63 .. 56]) ^ h2(x[55 .. 48]) ^ h2(x[47 .. 40]) ^ h2(x[39 .. 32])
  ^ h2(x[31 .. 24]) ^ h2(x[23 .. 16]) ^ h2(x[15 .. 8]) ^ h2(x[7 .. 0])

function b1(b : bool) -> string = if b then "1" else "0"

function b2v(b : bool) -> bits(1) = if b then 0b1 else 0b0

// *****************************************************************
// Input selection. A maximal-length 36-bit shift register, so that the address
// dimension of a sweep varies without the sweep growing a fourth nested loop and
// without anything here holding a table of addresses it would then be quantifying
// over. The polynomial is x^36 + x^25 + 1.

function lfsr36(s : bits(36)) -> bits(36) = {
  let fb : bits(1) = s[35 .. 35] ^ s[24 .. 24];
  (s << 1) | zero_extend(fb)
}

// The addresses a decode is worth taking at deliberately rather than at random:
// the two ends of the field, the two ends of the implemented space, and the
// carries between them.
function edge_addr(i : int) -> CapAddrBits = match i {
  0 => 0x000000000,
  1 => 0x000000001,
  2 => 0x00000007f,
  3 => 0x07fffffff,
  4 => 0x080000000,
  5 => 0x0ffffffff,
  6 => 0xfffffffff,
  _ => 0x800000000,
}

// Base mantissas at the region boundaries the three-bit correction turns on.
function edge_b(i : int) -> bits(8) = match i {
  0 => 0x00,
  1 => 0x01,
  2 => 0x3f,
  3 => 0x40,
  4 => 0x7f,
  5 => 0x80,
  6 => 0xc0,
  _ => 0xff,
}

// Stored top mantissas, six bits, at the same kind of boundary.
function edge_t(i : int) -> bits(6) = match i {
  0 => 0b000000,
  1 => 0b000001,
  2 => 0b011111,
  3 => 0b100000,
  4 => 0b101010,
  5 => 0b111110,
  6 => 0b111111,
  _ => 0b010101,
}

// *****************************************************************
// The vectors.

function emit_dec(c : CapBits) -> unit = {
  let probe = capBitsToCapability(false, c);
  let (base, top) = getCapBoundsBits(probe);
  let mal : bool = unsigned(top) < unsigned(0b0 @ base);
  let t : bool = not(mal);
  let cap = capBitsToCapability(t, c);
  let len = getCapLength(cap);
  print_endline(
    "dec " ^ b1(t) ^ " " ^ h16(c) ^ " ->"
    ^ " " ^ h2(zero_extend(cap.perms))
    ^ " " ^ h1(cap.otype)
    ^ " " ^ b1(cap.normalized)
    ^ " " ^ h2(zero_extend(cap.E))
    ^ " " ^ h2(cap.B)
    ^ " " ^ h2(cap.T)
    ^ " " ^ h9(cap.address)
    ^ " " ^ h16(capToBits(cap))
    ^ " " ^ h9(base)
    ^ " " ^ h10(top)
    ^ " " ^ h10(to_bits_truncate(cap_len_width, len))
    ^ " " ^ b1(mal)
  )
}

function emit_sb(c : CapBits, base : CapAddrBits, top : CapLenBits) -> unit = {
  let cap = capBitsToCapability(false, c);
  let (exact, out) = setCapBounds(cap, base, top);
  let (dbase, dtop) = getCapBoundsBits(out);
  let len = getCapLength(out);
  print_endline(
    "sb " ^ h16(c) ^ " " ^ h9(base) ^ " " ^ h10(top) ^ " ->"
    ^ " " ^ b1(exact)
    ^ " " ^ b1(out.normalized)
    ^ " " ^ h2(zero_extend(out.E))
    ^ " " ^ h2(out.B)
    ^ " " ^ h2(out.T)
    ^ " " ^ h9(out.address)
    ^ " " ^ h9(dbase)
    ^ " " ^ h10(dtop)
    ^ " " ^ h10(to_bits_truncate(cap_len_width, len))
  )
}

function emit_sa(t : bool, c : CapBits, addr : xlenbits) -> unit = {
  let cap = capBitsToCapability(t, c);
  let (rep, moved) = setCapAddr(cap, addr);
  let checked = setCapAddrChecked(cap, addr);
  print_endline(
    "sa " ^ b1(t) ^ " " ^ h16(c) ^ " " ^ h16(addr) ^ " -> "
    ^ b1(rep) ^ " " ^ h9(moved.address) ^ " " ^ b1(checked.tag)
  )
}

function emit_so(t : bool, c : CapBits, offset : xlenbits) -> unit = {
  let cap = capBitsToCapability(t, c);
  let (rep, moved) = setCapOffset(cap, offset);
  let checked = setCapOffsetChecked(cap, offset);
  print_endline(
    "so " ^ b1(t) ^ " " ^ h16(c) ^ " " ^ h16(offset) ^ " -> "
    ^ b1(rep) ^ " " ^ h9(moved.address) ^ " " ^ b1(checked.tag)
  )
}

function emit_io(t : bool, c : CapBits, delta : xlenbits) -> unit = {
  let cap = capBitsToCapability(t, c);
  let (rep, moved) = incCapOffset(cap, delta);
  print_endline(
    "io " ^ b1(t) ^ " " ^ h16(c) ^ " " ^ h16(delta) ^ " -> "
    ^ b1(rep) ^ " " ^ h9(moved.address)
  )
}

function emit_frc(c : CapBits, i : CapAddrBits) -> unit = {
  let cap = capBitsToCapability(false, c);
  print_endline(
    "frc " ^ h16(c) ^ " " ^ h9(i) ^ " -> " ^ b1(fastRepCheck(cap, i))
  )
}

function emit_ib(c : CapBits, addr : xlenbits, size : CapLenBits) -> unit = {
  let cap = capBitsToCapability(false, c);
  print_endline(
    "ib " ^ h16(c) ^ " " ^ h16(addr) ^ " " ^ h10(size) ^ " -> "
    ^ b1(inCapBounds(cap, addr, unsigned(size)))
  )
}

// The twelve accessors, assembled into the bitmap they index. Emitting them beside
// `perms_expand`'s own answer is what holds the two against each other: an accessor
// reading the wrong position and an expansion row with the wrong bit are the same
// defect seen from two sides, and each is silent to a linter.
function accessor_bitmap(cap : Capability) -> CapPermsBits =
  b2v(cap_access_system_regs(cap)) @ b2v(cap_permit_unseal(cap))
  @ b2v(cap_permit_seal(cap)) @ b2v(cap_permit_execute(cap))
  @ b2v(cap_load_mutable(cap)) @ b2v(cap_load_global(cap))
  @ b2v(cap_store_local_cap(cap)) @ b2v(cap_store_cap(cap))
  @ b2v(cap_load_cap(cap)) @ b2v(cap_permit_store(cap))
  @ b2v(cap_permit_load(cap)) @ b2v(cap_global(cap))

function emit_pe(code : CapPermsCode) -> unit = {
  let cap = { null_cap with perms = code };
  print_endline(
    "pe " ^ h2(zero_extend(code)) ^ " -> "
    ^ h3(perms_expand(code)) ^ " " ^ h3(accessor_bitmap(cap))
  )
}

function emit_pn(want : CapPermsBits) -> unit = {
  let code = perms_narrow(want);
  print_endline(
    "pn " ^ h3(want) ^ " -> " ^ h2(zero_extend(code)) ^ " " ^ h3(perms_expand(code))
  )
}

function emit_sl(c : CapBits, otyp : CapOTypeBits) -> unit = {
  let cap = capBitsToCapability(true, c);
  let sealed = sealCap(cap, otyp);
  print_endline(
    "sl " ^ h16(c) ^ " " ^ h1(otyp) ^ " -> "
    ^ b1(isCapSealed(sealed)) ^ " " ^ b1(hasReservedOType(sealed))
    ^ " " ^ b1(isSentry(sealed))
    ^ " " ^ h16(capToBits(sealed)) ^ " " ^ h16(capToBits(unsealCap(sealed)))
  )
}

function emit_mb(t : bool, c : CapBits) -> unit = {
  let cap = capBitsToCapability(t, c);
  let mem = capToMemBits(cap);
  let back = memBitsToCapability(t, mem);
  print_endline(
    "mb " ^ b1(t) ^ " " ^ h16(c) ^ " -> "
    ^ h16(mem) ^ " " ^ b1(back.tag) ^ " " ^ h16(capToBits(back))
  )
}

function emit_it(v : xlenbits) -> unit = {
  let cap = int_to_cap(v);
  print_endline(
    "it " ^ h16(v) ^ " -> "
    ^ b1(cap.tag) ^ " " ^ h16(capToBits(cap)) ^ " " ^ h9(cap.address)
  )
}

function emit_ac(c : CapBits) -> unit = {
  let cap = capBitsToCapability(false, c);
  print_endline(
    "ac " ^ h16(c) ^ " -> "
    ^ h9(to_bits_truncate(cap_addr_width, getCapCursor(cap)))
    ^ " " ^ h16(capAddrBits(cap))
    ^ " " ^ h16(getCapBaseBits(cap))
    ^ " " ^ h10(getCapTopBits(cap))
    ^ " " ^ h16(getCapOffsetBits(cap))
    ^ " " ^ h16(cap_to_integer_pc(cap))
  )
}

// *****************************************************************
// The sweeps.

// Every one of the 2^19 bounds encodings, each at its own address. The exponent
// field, the base mantissa and the stored top mantissa are walked exhaustively,
// which is the totality R-15-007a's representation-correctness obligation states
// decode over; the address, the permission code and the object type ride the
// index, so the sweep varies them without becoming a fourth and fifth loop.
function sweep_decode_total() -> unit = {
  var seed : bits(36) = 0x0a5c3f19d;
  foreach (ef from 0 to 31) {
    foreach (b from 0 to 255) {
      foreach (tt from 0 to 63) {
        seed = lfsr36(seed);
        let enc : EncCapability = struct {
          perms   = to_bits_truncate(cap_perms_code_width, b + tt),
          otype   = to_bits_truncate(cap_otype_width, b + ef),
          E       = to_bits_truncate(cap_E_width, ef),
          B       = to_bits_truncate(cap_mantissa_width, b),
          T       = to_bits_truncate(cap_mantissa_width - 2, tt),
          address = seed,
        };
        emit_dec(encCapToBits(enc))
      }
    }
  }
}

// The same decode at the addresses and mantissas the sweep above reaches only by
// accident, which is what the three-bit region correction and the wrap correction
// turn on.
function sweep_decode_edges() -> unit = {
  foreach (ef from 0 to 31) {
    foreach (bi from 0 to 7) {
      foreach (ti from 0 to 7) {
        foreach (ai from 0 to 7) {
          let enc : EncCapability = struct {
            perms   = to_bits_truncate(cap_perms_code_width, ef),
            otype   = to_bits_truncate(cap_otype_width, bi + ti),
            E       = to_bits_truncate(cap_E_width, ef),
            B       = edge_b(bi),
            T       = edge_t(ti),
            address = edge_addr(ai),
          };
          emit_dec(encCapToBits(enc))
        }
      }
    }
  }
}

// The bases a power-of-two narrowing is worth taking at: zero, aligned to its own
// length, one past that, two deliberately unaligned addresses, the base whose top
// lands exactly on the top of the implemented space, and one that puts the
// requested top above it.
function sb_base(j : int, k : int) -> CapAddrBits = match j {
  0 => zeros(),
  1 => to_bits_truncate(cap_addr_width, pow2(k)),
  2 => to_bits_truncate(cap_addr_width, pow2(k) + 1),
  3 => 0x080000003,
  4 => 0x0fffffff0,
  5 => to_bits_truncate(cap_addr_width, pow2(cap_addr_width) - pow2(k)),
  6 => 0x0abcdef01,
  _ => to_bits_truncate(cap_addr_width, pow2(cap_addr_width) - 1),
}

function thr_base(j : int) -> CapAddrBits = match j {
  0 => 0x080000103,
  1 => 0x000000000,
  _ => 0x0fffff000,
}

// The corners of the domain the containment property does not cover: a requested
// top below its own base, and a requested top at or above 2^cap_addr_width.
function wrap_base(j : int) -> CapAddrBits = match j {
  0 => 0xfffffffff,
  1 => 0xfffffffff,
  2 => 0x800000000,
  3 => 0x000000001,
  4 => 0xc00000000,
  5 => 0x0ffffffff,
  6 => 0xfffffff00,
  _ => 0x555555555,
}

function wrap_top(j : int) -> CapLenBits = match j {
  0 => 0b0 @ 0x000000001,
  1 => 0b0 @ 0x000000000,
  2 => 0b0 @ 0x000000000,
  3 => 0b1 @ 0xfffffffff,
  4 => 0b1 @ 0x000000000,
  5 => 0b1 @ 0x800000000,
  6 => 0b0 @ 0x000000010,
  _ => 0b1 @ 0x555555554,
}

function sweep_setbounds() -> unit = {
  let c0 = capToBits(root_data_cap);
  // Every power of two the address space admits, at eight bases each.
  foreach (k from 0 to cap_addr_width) {
    foreach (j from 0 to 7) {
      let base = sb_base(j, k);
      let top : CapLenBits = (0b0 @ base) + to_bits_truncate(cap_len_width, pow2(k));
      emit_sb(c0, base, top)
    }
  };
  // Across the byte-exact threshold, which the frozen widths put at 128 bytes,
  // and well past it, at three bases.
  foreach (j from 0 to 2) {
    let base = thr_base(j);
    foreach (len from 0 to 400) {
      let top : CapLenBits = (0b0 @ base) + to_bits_truncate(cap_len_width, len);
      emit_sb(c0, base, top)
    }
  };
  // A spread of magnitudes at pseudo-random bases, so that the exponent choice,
  // the rounding and the exactness verdict are exercised off the boundaries the
  // two sweeps above aim at.
  var seed : bits(36) = 0x123456789;
  foreach (i from 0 to 19999) {
    seed = lfsr36(seed);
    let base : CapAddrBits = seed;
    seed = lfsr36(seed);
    let sh = unsigned(seed[4 .. 0]);
    let len : CapLenBits = (0b0 @ seed) >> sh;
    emit_sb(c0, base, (0b0 @ base) + len)
  };
  // The domain nothing states: a requested top above 2^cap_addr_width, and a
  // requested top below its own base. The containment property holds at or below
  // 2^cap_addr_width and not above it, where the decoded top wraps below the
  // decoded base; the model does exactly that and it is unreachable with a tag,
  // `CSetBounds` computing `inBounds` and clearing the tag on precisely the test
  // that fails there. The domain is swept deliberately rather than avoided, so
  // that the two implementations are held to each other where the algebra's own
  // property does not hold and a divergence would otherwise go unexercised.
  foreach (i from 0 to 4999) {
    seed = lfsr36(seed);
    let base : CapAddrBits = seed;
    seed = lfsr36(seed);
    let top : CapLenBits = seed[0 .. 0] @ seed;
    emit_sb(c0, base, top)
  };
  // The same domain at its own corners, where the exponent choice sees a length
  // that wrapped rather than a length.
  foreach (j from 0 to 7) {
    emit_sb(c0, wrap_base(j), wrap_top(j))
  };
  // The exponent-increment branch's own corner, and it is narrow enough that a
  // sweep off entropy alone does not reach it: the branch fires with **neither**
  // mantissa having lost significance only where the base and the top are both
  // aligned to a large power of two and the top is below the base, and there the
  // base's own lost-significance clause is the only thing deciding the exactness
  // verdict. Everywhere else that clause is redundant, because a top that lost
  // significance has already made the answer inexact and a base that lost any
  // lower bit has already set the flag the clause would set. A vector population
  // that misses this corner cannot tell the clause from its absence, which is
  // measured rather than argued: without these lines a package that reads the
  // recomputed base mantissa instead of the one the clause names reproduces every
  // other vector in this file.
  foreach (k from 24 to cap_max_E) {
    foreach (m from 1 to 15) {
      let base : CapAddrBits = to_bits_truncate(cap_addr_width, m * pow2(k));
      foreach (n from 0 to 7) {
        let top : CapLenBits = to_bits_truncate(cap_len_width, n * pow2(k));
        emit_sb(c0, base, top)
      }
    }
  }
}

// One capability per probe, built the way the architecture builds one.
function make_cap(base : CapAddrBits, len : CapLenBits) -> CapBits = {
  let (_, c) = setCapBounds(root_data_cap, base, (0b0 @ base) + len);
  capToBits(c)
}

// The addresses a move is worth taking at: the two ends of the region it names,
// one either side of each, an unrelated address, and one above the implemented
// space, which is the case `addrInRange` exists for.
function move_target(j : int, base : CapAddrBits, top : CapLenBits,
                     seed : bits(36)) -> xlenbits = match j {
  0 => zero_extend(base),
  1 => zero_extend(base) - 1,
  2 => zero_extend(base) + 1,
  3 => zero_extend(top),
  4 => zero_extend(top) - 1,
  5 => zero_extend(top) + 1,
  6 => zero_extend(seed),
  _ => 0x0000001000000000,
}

// The increments a representability check is worth taking at: nothing, one step
// either way, the two edges of the representable region the exponent gives, and
// two unrelated ones.
function rep_target(j : int, e : int, seed : bits(36)) -> CapAddrBits = match j {
  0 => zeros(),
  1 => to_bits_truncate(cap_addr_width, 1),
  2 => ones(),
  3 => to_bits_truncate(cap_addr_width, pow2(e + cap_mantissa_width) - 1),
  4 => to_bits_truncate(cap_addr_width, pow2(e + cap_mantissa_width)),
  5 => to_bits_truncate(cap_addr_width, 0 - pow2(e + cap_mantissa_width)),
  6 => seed,
  _ => not_vec(seed),
}

function sweep_moves() -> unit = {
  var seed : bits(36) = 0x0fedcba98;
  foreach (i from 0 to 1999) {
    seed = lfsr36(seed);
    let base : CapAddrBits = seed;
    seed = lfsr36(seed);
    let sh = unsigned(seed[4 .. 0]);
    let len : CapLenBits = (0b0 @ seed) >> sh;
    let c = make_cap(base, len);
    let cap = capBitsToCapability(false, c);
    let (dbase, dtop) = getCapBoundsBits(cap);
    let tagged : bool = (i % 2) == 0;
    foreach (j from 0 to 7) {
      let a = move_target(j, dbase, dtop, seed);
      emit_sa(tagged, c, a);
      emit_so(tagged, c, a);
      emit_io(tagged, c, a)
    };
    foreach (j from 0 to 7) {
      emit_frc(c, rep_target(j, unsigned(cap.E), seed))
    };
    foreach (j from 0 to 7) {
      let a = move_target(j, dbase, dtop, seed);
      let sz : CapLenBits = if (j % 2) == 0 then zeros()
                            else to_bits_truncate(cap_len_width, 1 + (j * 7));
      emit_ib(c, a, sz)
    }
  }
}

// The permission lattice, the object-type space, the memory transform and the
// accessors over the decoded bounds. Each of these is a table or a one-line function
// that the bounds sweeps above never call, so without them the largest hand-copied
// block in the package, `perms_expand`'s sixteen rows, would be held by nothing on
// this side of the format at all.
function sweep_lattice() -> unit = {
  // Every permission codepoint, against its own expansion and against the twelve
  // accessors that index it.
  foreach (i from 0 to 31) {
    emit_pe(to_bits_truncate(cap_perms_code_width, i))
  };
  // And `perms_narrow` over **every** mask the expanded bitmap can take, which is
  // the whole of the domain `candperm` hands it: the search is a 32-way
  // largest-admitted-subset over a 12-bit input, so exhaustive is 4096 lines.
  foreach (i from 0 to 4095) {
    emit_pn(to_bits_truncate(cap_perms_width, i))
  };
  var seed : bits(36) = 0x0c0ffee12;
  foreach (i from 0 to 31) {
    seed = lfsr36(seed);
    let c : CapBits = seed[27 .. 0] @ seed;
    foreach (j from 0 to 15) {
      emit_sl(c, to_bits_truncate(cap_otype_width, j))
    }
  };
  foreach (i from 0 to 1999) {
    seed = lfsr36(seed);
    let hi : bits(36) = seed;
    seed = lfsr36(seed);
    let v : bits(64) = hi[27 .. 0] @ seed;
    emit_mb((i % 2) == 0, v);
    emit_it(v);
    emit_ac(v)
  }
}

function main() -> unit = {
  print_endline("# vectors emitted by tools/cheri-equiv/gen_vectors.sail against");
  print_endline("# the curated model's core/cap_format.sail and core/cap_common.sail");
  print_endline("# fields are lowercase hex, width fixed by the field's bit width");
  sweep_decode_total();
  sweep_decode_edges();
  sweep_setbounds();
  sweep_moves();
  sweep_lattice()
}
