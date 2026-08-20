// The `mstatus` SXL/UXL reset test this file used to hold went with the
// fields: those are the effective XLEN of supervisor and user mode, and
// there is one mode (R-15-003). What replaces it is the property that
// deletion establishes and a later edit could silently regress.

// `misa` must advertise neither supervisor nor user mode after reset.
$[test]
function test_misa_has_no_privileged_modes() -> unit = {
  reset_misa();
  assert(misa[S] == 0b0);
  assert(misa[U] == 0b0);
}

// A trap leaves the hart with interrupts disabled and the previous
// enable saved, and that is now the whole of the privilege transition.
$[test]
function test_trap_saves_only_the_interrupt_enable() -> unit = {
  reset_tvec();
  mstatus[MIE] = 0b1;
  mstatus[MPIE] = 0b0;
  let _ = trap_handler(Exception(E_M_EnvCall()), zeros(), None(), None());
  assert(mstatus[MIE] == 0b0);
  assert(mstatus[MPIE] == 0b1);
}
