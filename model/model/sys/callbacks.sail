// System callbacks.
//
// The page-table-walk callbacks are gone with the walker (R-15-002,
// R-15-038); there is no translation event for a harness to observe.

// Instruction retire callback.
val instret_callback = pure {cpp: "instret_callback"} : (unit) -> unit
function instret_callback() = ()
