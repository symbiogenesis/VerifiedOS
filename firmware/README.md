# Firmware

The boot chain's firmware sources and the harness that checks them. The
[boot-handoff contract](../docs/implementation/contracts/boot-handoff.md) states
what they owe and the predicate the harness decides; this page says what each
file is and what it is not.

| Path | What it is | What it is not |
| --- | --- | --- |
| [include/vos_boot.h](include/vos_boot.h) | The boot image layout, the measurement encoding, the handoff record and the bring-up composition's constants; the implementation owner the contract's tables are checked against | A production composition: the attested devicetree owes the production values |
| [include/vos_keccak.h](include/vos_keccak.h), [crypto/keccak.c](crypto/keccak.c) | Keccak-f[1600] and SHAKE256 in integer C, the one primitive the release computes | A constant-time, masked or reduction-level artifact; no binary carries those claims |
| [rot/boot_verify.c](rot/boot_verify.c) | The RoT's measured release of the boot core into the M-mode stage, in the contract's order | A signature verifier: it calls the one it is bound to, and no SLH-DSA verifier exists yet |
| [mmode/handoff.s](mmode/handoff.s) | The M-mode stage's kernel handoff, lowered by hand to the assembler dialect | The M-mode firmware's installation of a composed graph (R-07-028), which MModeFirmware.v states and nothing yet executes |
| [harness/rot_stage_main.c](harness/rot_stage_main.c) | The host driver that runs the release with main SRAM as buffers, and the fixture signature verifier | Firmware; the fixture verifier is not a signature scheme |
| [harness/kernel_entry_fixture.s](harness/kernel_entry_fixture.s) | A kernel-entry fixture that checks the handoff state and reports through HTIF, with the bring-up kernel layout | M4.4's kernel |
| [harness/rot_inputs.s](harness/rot_inputs.s) | A probe that reads the RoT's lifecycle state, entropy verdict and floor under the RoT composition | Firmware |

**Where each runs today.** The C compiles for the host only: no compiler reaches
the purecap dialect until M1.2f's backend and M1.7's target path, so the harness
runs the release host-compiled in place of the RoT hart and says so in every
report. The two assembly programs run on the golden emulator, the M-mode stage
and fixture under `verifiedos.json` and the probe under `verifiedos-rot.json`.

**Checks.** `python tools/run.py boot-handoff run` builds everything with
warnings as errors and both sanitizers, and runs the contract's cases against the
golden emulator; it needs `run.py model build` first. `python tools/run.py
boot-handoff layout` checks the contract's tables and the assembled image against
`vos_boot.h` without a toolchain.

The C is written to stay within what the target will need: no allocation, no
library call and no loop bound read from the image beyond a length already
checked against the composition. Every file here is original and carries
`Apache-2.0` under [COPYRIGHT.md](../COPYRIGHT.md)'s map.
