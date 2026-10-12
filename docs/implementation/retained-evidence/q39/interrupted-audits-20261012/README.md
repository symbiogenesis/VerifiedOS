# Interrupted compiler audit evidence

The integrator committed the pending triage and stop decision as `82fceaca`
before sending `SIGTERM` to the four original checker processes at 07:25:15 UTC
on 12 October 2026. [The action journal](checker-control.json) records the exact
PID-bound identities and signals. No original driver or wrapper was signalled.
[The decision record](../../../contained-compiler-port-decisions.md#shelve-the-incomplete-audits-after-checkpoint-and-release-triage)
states why activity did not establish the user's required confidence for a pause.

[The terminal summary](terminal-summary.json) records the four original producer
completions, final native paths and retained hashes. Each original producer
finished at exit 1 after its checker returned `-15`; the four original
fresh-kernel receipts are retained verbatim and bound by
[the manifest](manifest.json). These are interruption receipts, with no successful
kernel, complete assumption classification or final qualification credited.

The fresh-kernel receipts record the four-token `opam exec` launcher prefix;
the process capture records the child checker arguments. The literal arrays
differ. Removing only that explicit prefix reproduces the original child NUL
argument hash recorded by the guarded action journal for each checker.

The original seven successful compilation stages remain in their unchanged
receipts with `passed: false` and `kernel: null`. Their historical public snapshots
remain in [the pending-audit bundle](../pending-audits-20261012/README.md).
The stopped checkers' in-memory work supplies no accepted resume checkpoint;
diagnostic log prefixes do not certify completed libraries or declarations.

Native archives, proof objects, compiler executables, original helper revisions,
source worktrees, switches and locked dependencies remain at their bound paths.
The public records contain metadata, not a backup of those inputs. Compilation
reuse requires current validation of its entire bound population; a new checker
attempt still requires a complete audit. Neither an interruption nor a compiled
object authorizes the complete default-reuse tier.

[The scout-retirement journal](triage-retirement.json) records non-forced removal
of the two stopped, clean, integrated read-only triage worktrees and their local
branches. Their useful captures remain retained; no native compiler input or
output path was moved or deleted.

Q39 and Q43 remain open. Their remaining attended-work ranges are conditional
acceptance allowances; the unresolved diagnosis and unattended audit duration
have no measured completion estimate. No new port, prover upgrade, proof repair
or complete qualification run is commissioned by shelving these attempts.
