// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The channel codes the FEC decoders are written over, as a composition
// declaration (R-15-119a).
//
// **This file is the shape and holds none of the numbers, and that is the whole
// of what it is for.** The LDPC base graph and lifting size and the polar
// reliability sequence and rate-matching schedule are 3GPP TS 38.212's normative
// tables. Each reaches a composition from the copy its builder holds under that
// standard's own in-house carve-out, and **no normative 3GPP table is a tracked
// file of this repository**, this one included: what a row below carries is a
// *selector* naming which of the standard's tables a code uses, an index the
// composition assigns out of its own copy, and never an adjacency, a lifting-size
// set, a reliability sequence, or a rate-matching schedule. An auditor's check is
// a search of the tree rather than a reading of it.
//
// **No configuration in this tree declares a code**, and that is forced twice
// over rather than an omission. A tracked configuration carrying one would be the
// reproduction the table-free arm declines, and the values are the builder's in
// any case. So the list is empty in every shipped composition, the shape is here,
// and the properties that exercise the surface install a code of their own and
// restore what they found, exactly as the scratchpad properties install a region
// (unit_tests/test_matrix_scratchpad.sail, R-15-108).
//
// **The realization geometry is not here**, and the split is R-15-119a's own: the
// unit count, the decoder parallelism, the maximum lifted block length the
// datapath is sized for, the deterministic iteration bound and the polar list
// width are this machine's rather than the standard's, so they are declared with
// every other datapath figure on the core class (core/core_class.sail) and
// selected by R-15-108's exploration. What TS 38.212 fixes is an input to that
// search and never an axis of it.

// The two code families, and the whole of the generation floor: LDPC and polar
// and nothing else, so the legacy turbo and convolutional decoders are not a
// value this enumeration can take (R-15-119, R-15-129). A third arm is what a
// 2G/3G/4G downgrade would need and there is deliberately nowhere to write one.
enum FecFamily = {
  FecFamily_Ldpc,
  FecFamily_Polar,
}

mapping fec_family_str : FecFamily <-> string = {
  FecFamily_Ldpc  <-> "ldpc",
  FecFamily_Polar <-> "polar",
}
overload to_str = {fec_family_str}

// The declared widths. Each bound says what a selector may be and never what it
// is, for the reason the core-class table's bounds do: a validator asserting a
// range over a number TS 38.212 has already decided would be the reproduction
// this arm declines, arriving through a check instead of through a table.
type fec_selector = range(0, 255)
type fec_lifting  = range(0, 1024)

// One row is one code the composition's decoders are wired for.
//
// **The record is symmetric and the two families are not**, which is the same
// asymmetry the core-class table carries and is held the same way: a row declares
// zero for every field belonging to the other family, under the model's
// zero-is-absent idiom, and the validator refuses anything else
// (postlude/validate_config.sail).
//
//   - `base_graph` / `lifting_size`. The LDPC side. TS 38.212 fixes the two base
//     graphs and the lifting sizes their sets admit; a row names which, and a
//     protograph code without a lifting size is not lifted, so an LDPC row
//     declares a positive one.
//   - `reliability_sequence` / `rate_matching`. The polar side. The standard
//     specifies the code, its reliability sequence and its rate matching, and
//     specifies no decoder at all, which is why the successive-cancellation list
//     width sits on the core class beside the parallelism and not here: a list
//     width is a receiver's own error-rate-for-area trade rather than a table's
//     value (R-15-119a).
struct FecCode = {
  family               : FecFamily,
  base_graph           : fec_selector,
  lifting_size         : fec_lifting,
  reliability_sequence : fec_selector,
  rate_matching        : fec_selector,
}

// A `register` rather than a `let` for the reason `core_roster` is one: a
// property that installs a code has to be able to, and there is no other way to
// exercise a surface no shipped configuration declares a code for.
register fec_codes : list(FecCode) = config platform.fec_codes

function fec_code_count(codes : list(FecCode)) -> nat =
  match codes {
    [||]      => 0,
    _ :: rest => 1 + fec_code_count(rest),
  }

// The code a descriptor's index names, or none. The index is the composition's
// own ordinal into the list above and is the one thing an FEC instruction says
// about a code, which is what keeps the mnemonics, the operand forms and the
// encoding invariant over every parameter a builder supplies (R-15-119a): a
// descriptor names *which* code and never *what* the code is.
function fec_code_at(codes : list(FecCode), i : int) -> option(FecCode) =
  match codes {
    [||]          => None(),
    code :: rest  =>
      if i < 0 then None()
      else if i == 0 then Some(code)
      else fec_code_at(rest, i - 1),
  }
