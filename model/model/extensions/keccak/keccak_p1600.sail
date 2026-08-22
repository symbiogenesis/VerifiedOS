// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The frozen Keccak-*p*[1600] permutation (R-15-056, R-15-056a, R-15-058).
//
// This file is the **permutation** and nothing else: a pure function from 25
// lanes of 64 bits to 25 lanes of 64 bits, with the round count as its only
// other argument. The instruction that carries it is beside it in
// [keccak_insts.sail](keccak_insts.sail), and the split is the point. R-15-058
// makes the fixed-permutation invariant a fresh Sail statement disciplined
// against FIPS 202 and the NIST ACVP vectors, and an invariant about a
// *function* is stated against the standard's own definition at any geometry,
// where an invariant about an instruction is stated at whatever VLEN the model
// was built at. So the known-answer tests in
// [unit_tests/test_keccak.sail](../../unit_tests/test_keccak.sail) run against
// this function directly and are geometry-independent, and the instruction owes
// only that it wires the element group to it.
//
// **Both round counts are defined here and neither is added later**
// (R-15-056a). Keccak-*p*[1600,24] is SHA-3 and SHAKE; Keccak-*p*[1600,12] is
// TurboSHAKE and KangarooTwelve. FIPS 202 defines Keccak-*p*[*b*,*n*] as the
// **last** *n* rounds of Keccak-*f*[*b*], so the 12-round form is rounds 12
// through 23 of the same twenty-four round constants rather than a second
// constant table, which is why `first_round` below is arithmetic and not a
// second `match`. Freezing both is what makes the re-pin an exchange of
// encoding under unchanged semantics rather than a widening that would reopen
// the permutation lemma and the fixed-latency claim at ratification time
// (R-15-057, R-15-057a).
//
// **The tables here are indexed by the round number and by the lane, and by
// nothing else, which is what keeps them off the leakage argument.** R-15-055's
// ground for the adopted vector crypto is that table-free primitives have no
// cache-timing substrate; a table whose index is a loop counter is not that
// substrate, because the access sequence is a program constant and no operand
// reaches it. Every value-dependent operation below is XOR, AND, NOT, or a
// rotation by a constant, so the permutation is constant-time by shape rather
// than by declaration, and its latency is one entry in the timing-annotated
// model (core/timing.sail, R-15-053, R-15-056a).

// The state is 25 lanes of 64 bits. FIPS 202 indexes a lane by the pair
// (*x*, *y*) with *x* the column and *y* the row; this model flattens it to
// *x* + 5*y*, which is also the order the 200-byte string of the standard's
// own conversion puts the lanes in, so element *i* of the vector element group
// is lane *i* of the state with no reordering anywhere.
type keccak_state = vector(25, bits(64))

// The twenty-four round constants of FIPS 202 Algorithm 5 (*iota*), written in
// round order and read through `keccak_rc` below. Indexed by the round number
// and by nothing else.
let keccak_round_constants : vector(24, bits(64)) = [
  0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
  0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
  0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
  0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
  0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
  0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]

// **A Sail vector literal is `dec`-ordered, so its first element is its highest
// index**, the model defaulting to that order for generic vectors as it does for
// bitvectors. The model's own S-box carries the same subtraction for the same
// reason (`sbox_lookup` in extensions/K/types_kext.sail), and it is done here
// once rather than at each use so that the table above stays written in the
// order a reader checks it against FIPS 202 in. Reading the table directly is
// the transcription defect this accessor exists to make impossible, and
// `test_keccak_tables_are_well_formed` pins both ends of it.
val keccak_rc : range(0, 23) -> bits(64)
function keccak_rc(i) = keccak_round_constants[23 - i]

// A twenty-five-lane constant written in the standard's lane order, read into
// the lane-indexed state this model computes over. Same reversal, same reason:
// element *i* of the vector element group is lane *i* of the state, so a
// lane-indexed state and a `dec`-ordered literal are not the same vector.
val keccak_state_of_literal : keccak_state -> keccak_state
function keccak_state_of_literal(v) = {
  var out : keccak_state = vector_init(zeros());
  foreach (j from 0 to 24) {
    out[j] = v[24 - j]
  };
  out
}

// The rotation offsets of FIPS 202 Algorithm 2 (*rho*), transcribed as the
// standard's own table: the outer match is *x* and the inner is *y*, so a
// reader checks a row against the published one without re-deriving the
// triangular-number recurrence that generates it.
val keccak_rho : (range(0, 4), range(0, 4)) -> range(0, 63)
function keccak_rho(x, y) = match x {
  0 => match y { 0 =>  0, 1 => 36, 2 =>  3, 3 => 41, _ => 18 },
  1 => match y { 0 =>  1, 1 => 44, 2 => 10, 3 => 45, _ =>  2 },
  2 => match y { 0 => 62, 1 =>  6, 2 => 43, 3 => 15, _ => 61 },
  3 => match y { 0 => 28, 1 => 55, 2 => 25, 3 => 21, _ => 56 },
  _ => match y { 0 => 27, 1 => 20, 2 => 39, 3 =>  8, _ => 14 },
}

// The three modular index steps *theta*, *pi* and *chi* take over the five
// columns. They are written as total matches rather than as `%` so that every
// index into the 25-lane state is a `range(0, 4)` the type checker carries
// rather than a value a runtime assertion would have to narrow: a lane index
// out of range is then not a state this function has.
val keccak_next5 : range(0, 4) -> range(0, 4)
function keccak_next5(x) = match x { 0 => 1, 1 => 2, 2 => 3, 3 => 4, _ => 0 }

val keccak_prev5 : range(0, 4) -> range(0, 4)
function keccak_prev5(x) = match x { 0 => 4, 1 => 0, 2 => 1, 3 => 2, _ => 3 }

// (2*x + 3*y) mod 5, the row *pi* sends lane (*x*, *y*) to. The argument spans
// 0 to 20 because *x* and *y* each span 0 to 4.
val keccak_mod5 : range(0, 20) -> range(0, 4)
function keccak_mod5(n) = match n {
   0 => 0,  1 => 1,  2 => 2,  3 => 3,  4 => 4,
   5 => 0,  6 => 1,  7 => 2,  8 => 3,  9 => 4,
  10 => 0, 11 => 1, 12 => 2, 13 => 3, 14 => 4,
  15 => 0, 16 => 1, 17 => 2, 18 => 3, _  => 4,
}

// One round of FIPS 202 Algorithm 7, in the standard's own five steps and in
// the standard's own order. Nothing is fused: *rho* and *pi* are one loop
// because *pi* is a permutation of the lanes *rho* has already rotated and
// separating them would need a third state array, which is a transcription of
// the two steps and not a merge of them.
val keccak_round : (keccak_state, bits(64)) -> keccak_state
function keccak_round(input, rc) = {
  var a = input;

  // theta
  var c : vector(5, bits(64)) = vector_init(zeros());
  foreach (x from 0 to 4) {
    c[x] = a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20]
  };
  var d : vector(5, bits(64)) = vector_init(zeros());
  foreach (x from 0 to 4) {
    d[x] = c[keccak_prev5(x)] ^ (c[keccak_next5(x)] <<< 1)
  };
  foreach (x from 0 to 4) {
    foreach (y from 0 to 4) {
      a[x + 5 * y] = a[x + 5 * y] ^ d[x]
    }
  };

  // rho and pi
  var b : keccak_state = vector_init(zeros());
  foreach (x from 0 to 4) {
    foreach (y from 0 to 4) {
      b[y + 5 * keccak_mod5(2 * x + 3 * y)] = a[x + 5 * y] <<< keccak_rho(x, y)
    }
  };

  // chi
  foreach (x from 0 to 4) {
    foreach (y from 0 to 4) {
      a[x + 5 * y] = b[x + 5 * y] ^ (~(b[keccak_next5(x) + 5 * y]) & b[keccak_next5(keccak_next5(x)) + 5 * y])
    }
  };

  // iota
  a[0] = a[0] ^ rc;

  a
}

// The permutation at either frozen round count (R-15-056a). The round count is
// a type-level argument constrained to the two the fork defines, so a third one
// is not a value this function can be called at: R-15-057a's *unassigned values
// illegal* is held by the decode guard for the encoding and by this signature
// for the semantics, and neither leaves the other to catch it.
val keccak_p1600 : forall 'r, 'r in {12, 24}. (keccak_state, int('r)) -> keccak_state
function keccak_p1600(input, rounds) = {
  var a = input;
  // Keccak-*p*[1600, n] is the **last** n rounds of Keccak-*f*[1600], so the
  // 12-round form starts at round 12 of the same constant table (FIPS 202
  // §3.3). Starting it at round 0 instead would be a permutation that is not
  // TurboSHAKE's and would still pass every test written about round counts
  // rather than about answers, which is why the known-answer vector for the
  // 12-round form is in the harness beside the 24-round one.
  let first_round : range(0, 12) = 24 - rounds;
  foreach (i from first_round to 23) {
    a = keccak_round(a, keccak_rc(i))
  };
  a
}
