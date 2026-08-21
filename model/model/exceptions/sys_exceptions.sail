// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// The exception model, over the machine trap capabilities.
//
// `MTCC` and `MEPCC` hold what `mtvec` and `mepc` held, as capabilities rather
// than as integers (R-15-073): the trap vector is MTCC's address and the
// handler executes under MTCC's authority, while the interrupted PCC is saved
// whole in MEPCC and `mret` returns to it. The integer CSRs remain as *views*
// of those two addresses, which is how ISAv9 carries them and what keeps the
// M0.4 oracle a differential reference; the views are what R-15-073's "in
// place of" finally deletes.

type ext_exception = unit

// `mret` is permitted by the access-system-registers permission on the
// executing PCC, which is what privilege is here (R-15-003).
function ext_check_xret_priv () : unit -> bool = cap_access_system_regs(PCC)

// On a trap, MEPCC comes to hold PCC with the faulting address. PCC is not
// sealed on the way in: what a trap installs is the handler's authority, and
// what it saves is the authority it interrupted.
function handle_trap_extension(pc : xlenbits, _u : option(unit)) -> unit = {
  let (representable, mepcc) = setCapAddr(PCC, pc);
  assert(representable, "MEPCC should always be representable");
  MEPCC = mepcc;
  scr_write_callback(0b11111, MEPCC)
}

// used for traps and ECALL
function prepare_trap_vector(cause : Mcause) -> xlenbits = {
  // The address is used rather than an offset: the low bits carrying the mode
  // are part of the value `mtvec` would have held.
  match tvec_addr(Mk_Mtvec(capAddrBits(MTCC)), cause) {
    Some(epc) => { nextPCC = MTCC; epc },
    None()    => internal_error(__FILE__, __LINE__, "Invalid tvec mode")
  }
}

// MRET handling involves three functions:
//
// get_mepc:            used to read the value of the mret target  (no control flow transfer)
// set_mepc:            used to write a value of the mret target   (no control flow transfer)
// prepare_xret_target: used to get the value for control transfer to the mret target

function get_mepc() -> xlenbits = align_pc(capAddrBits(MEPCC))

function set_mepc(value : xlenbits) -> xlenbits = {
  let target = legalize_xepc(value);
  // Writing the integer view moves MEPCC's address, which clears the tag if
  // the result is unrepresentable or if MEPCC held a sealed capability: an
  // integer write cannot forge authority (R-15-007h).
  MEPCC = setCapAddrChecked(MEPCC, target);
  scr_write_callback(0b11111, MEPCC);
  target
}

function prepare_xret_target() -> xlenbits = {
  // A sentry unseals into the executing PCC, which is what makes a return
  // capability usable exactly once as a control-flow target and nowhere else
  // (R-15-008, R-15-071). Any other sealed type stays sealed and faults at the
  // next fetch rather than here.
  let epcc = MEPCC;
  let epcc = if isSentry(epcc) then unsealCap(epcc) else epcc;
  nextPCC = epcc;
  align_pc(capAddrBits(epcc))
}

// other trap-related CSRs

function get_mtvec() -> xlenbits = capAddrBits(MTCC)

function set_mtvec(value : xlenbits) -> xlenbits = {
  let mtv = legalize_tvec(Mk_Mtvec(capAddrBits(MTCC)),
                          value,
                          plat_mtvec_direct_mode_supported,
                          plat_mtvec_direct_base_alignment_exp,
                          plat_mtvec_vectored_mode_supported,
                          plat_mtvec_vectored_base_alignment_exp);
  MTCC = setCapAddrChecked(MTCC, mtv.bits);
  scr_write_callback(0b11100, MTCC);
  mtv.bits
}

// Ensure that the trap vector's mode field contains a supported value on
// reset. This would matter if these fields are read-only for the DUT.
function reset_tvec() -> unit = {
  var mtv = Mk_Mtvec(capAddrBits(MTCC));
  if plat_mtvec_direct_mode_supported then {
    mtv[Mode] = trapVectorMode(TV_Direct)
  } else if plat_mtvec_vectored_mode_supported then {
    mtv[Mode] = trapVectorMode(TV_Vector)
  };
  MTCC = setCapAddrChecked(MTCC, mtv.bits);
}

mapping clause csr_name_map = 0x305  <-> "mtvec"
mapping clause csr_name_map = 0x341  <-> "mepc"

function clause is_CSR_accessible(0x305, _) = true // mtvec
function clause is_CSR_accessible(0x341, _) = true // mepc

function clause read_CSR(0x305) = get_mtvec()
function clause read_CSR(0x341) = get_mepc()

function clause write_CSR(0x305, value) = { Ok(set_mtvec(value)) }
function clause write_CSR(0x341, value) = { Ok(set_mepc(value)) }
