# Firmware

The boot chain's firmware sources and the harness that checks them. The
[boot-handoff contract](../docs/implementation/contracts/boot-handoff.md) states
what they owe and the predicate the harness decides; this page says what each
file is and what it is not.

| Path | What it is | What it is not |
| --- | --- | --- |
| [include/vos_boot.h](include/vos_boot.h) | The boot image layout, the measurement encoding, the handoff record and the bring-up composition's constants; the implementation owner the contract's tables are checked against | A production composition: the attested devicetree owes the production values |
| [include/vos_keccak.h](include/vos_keccak.h), [crypto/keccak.c](crypto/keccak.c) | Keccak-f[1600] and SHAKE256 in integer C, the one primitive the release computes | A constant-time, masked or reduction-level artifact; no binary carries those claims |
| [crypto/README.md](crypto/README.md), [include/vos_signature.h](include/vos_signature.h) | Bounded scalar C verifiers for SLH-DSA-SHAKE-256s and ML-DSA-87, with an SLH callback for the release policy | Accepted target lowering, binary constant-time, masking or refinement evidence |
| [rot/boot_verify.c](rot/boot_verify.c) | The RoT's measured release of the boot core into the M-mode stage, in the contract's order | The signature implementation: its policy binds either the actual SLH verifier or an explicitly selected test fixture |
| [mmode/handoff.s](mmode/handoff.s) | The M-mode stage's kernel handoff, lowered by hand to the assembler dialect | The M-mode firmware's installation of a composed graph (R-07-028), which MModeFirmware.v states and nothing yet executes |
| [harness/rot_stage_main.c](harness/rot_stage_main.c) | The host driver that runs the release with main SRAM as buffers, selecting real SLH verification or the fixture, with an input-race control for each | Firmware; the fixture verifier is not a signature scheme |
| [harness/kernel_entry_fixture.s](harness/kernel_entry_fixture.s) | A kernel-entry fixture that checks the handoff state and reports through HTIF, with the bring-up kernel layout | M4.4's kernel |
| [harness/rot_inputs.s](harness/rot_inputs.s) | A probe that reads the RoT's lifecycle state, entropy verdict and floor under the RoT composition | Firmware |
| [harness/slh_target.c](harness/slh_target.c) | One translation unit for compiling the existing SHAKE and SLH callback through the selected purecap backend | The complete RoT release stage or a passing target execution claim |
| [harness/rot_release_target.c](harness/rot_release_target.c) | The target measurement, signature decision, placement and handoff-record preparation, with captured results for comparison | The model's missing release/latch doors, ROM/A-B/counting or the separately signed kernel stage |
| [chain/vos_chain.h](chain/vos_chain.h) | The target chain composition's constants, verdicts, records and C entry points, which [the contract's section 9](../docs/implementation/contracts/boot-handoff.md#9-the-target-chain) states and its four implementation lanes share; the chain's own C and assembly land beside it | A change to `include/` or `crypto/`, which M7.1f's staged manifest binds byte for byte; an implementation of any chain stage |
| [chain/mmode.c](chain/mmode.c), [chain/mmode_entry.s](chain/mmode_entry.s) | The chain's M-mode stage: a compiled body that verifies the stage-2 kernel image with ML-DSA-87 under the root its measured image carries, places and measures it by doublewords and checks the item-6 response's binding, beside the hand-lowered entry that derives its capabilities, installs section 6's kernel-entry state and reports refusals through HTIF | The C lowering of `cspecialrw` and `csealentry`; authentication of the item-6 response |
| [chain/rom.c](chain/rom.c), [chain/rom_entry.s](chain/rom_entry.s), [chain/rot_policy.s](chain/rot_policy.s) | The chain's ROM: items 1 to 3, the entropy and root refusals, SLH-DSA verification of the stage-0 runtime image under the lifecycle's root, its placement, item 4 and the state record, with the assembly that reads the devices and the ROM's root table | The metal-mask ROM itself, which no composition gives an aperture |
| [chain/runtime.c](chain/runtime.c), [chain/runtime_entry.s](chain/runtime_entry.s), [chain/chain_common.c](chain/chain_common.c) | The chain's RoT runtime: the bring-up reset table's ready predicates and pet decisions, A/B selection and boot counting, SLH-DSA verification of the selected M-mode image, item 5, the handoff record and the release, and the item-6 service; the assembly is the runtime's only door user | Q33's production reset table; the clearing of the attempt count after a successful boot |
| [chain/preamble.s](chain/preamble.s) | The runtime-only runs' preamble, performing the ROM's two device acts before entering the runtime | Firmware: it stands in for the ROM's device acts in the watchdog cases |
| [chain/target/](chain/target/manifest.json) | The chain campaign's staged inputs, written by `run.py boot-handoff chain-stage` where the contained compiler is: the compiled ROM, runtime, mutant and M-mode streams, the signed images as hex, the disposable public keys and a manifest binding every source, compiler and image identity and section 9.13's freeze; `chain-verify` holds them to the checkout | The contained compiler or any private key |
| [chain/kernel_stage.s](chain/kernel_stage.s) | The kernel-entry fixture laid out as the chain's separately signed stage-2 payload, its eleven checks unchanged | M4.4's kernel |

**Where each runs today.** The boot-handoff harness
runs the release host-compiled in place of the RoT hart and says so in every
report. The two assembly programs run on the golden emulator, the M-mode stage
and fixture under `verifiedos.json` and the probe under `verifiedos-rot.json`.

**Checks.** `python tools/run.py boot-handoff run` builds everything with
warnings as errors and both sanitizers, and runs the contract's cases against the
golden emulator. `--signature-scheme slh256s` binds the actual SLH verifier to
the same cases, including the racing input control. OpenSSL creates disposable
signing keys and signatures in the native output lane; the firmware verifier
makes each release decision. The default `fixture` mode remains separately named.
An explicit `--simulator` requires its `--build-receipt`, checked against the
current model sources; otherwise the command uses the lane's model build and its
successful build receipt. A crash cannot supply a release or refusal verdict.
`python tools/run.py
boot-handoff layout` checks the contract's layout, case and permission tables and
the assembled image against `vos_boot.h`, the harness and the image's constants
without a toolchain, and the contract's chain tables against `chain/vos_chain.h`
and the model's boot-control door declarations.

`boot_handoff.scheduled_mmode` emits the reviewed scheduled composition's exact
timer windows and ASR-free partition execute roots before the final handoff.
The kernel supplies the nonempty descriptor and validates the actual capabilities.
The fixture and its empty descriptor retain their own predicate.

`python tools/run.py boot-handoff signature-target --help` describes the bounded
RoT-profile verifier trial. It requires a real signed boot image, its raw public
key, an explicit contained compiler and a successful model build receipt. The
positive must complete with HTIF success before the corrupt-signature and
wrong-root controls run. A cutoff or timeout records no verdict and leaves those
controls unexecuted. Target code and data stay in the native output lane. The
complete RoT stage still needs its release mechanism, policy lowering and boot
chain joins.

`boot-handoff release-target` compiles the preparation body with the real SLH
verifier through the contained backend. Trusted assembly reads the actual RoT
inputs and supplies bounded buffers; the compiled body exports its verdict,
measurement, placed image and handoff record. Completed attempts use HTIF
success so the emulator saves that capture, while the capture's verdict decides
release or refusal. The harness compares every output byte with the host stage
and starts the main-die fixture only from an accepted target capture. Its finite
campaign covers a valid image, bad magic, an over-length payload field, a version
below the floor, a corrupt signature, a wrong root and a corrupt payload. It does not establish the complete
boot-handoff predicate above: MMIO access and terminal observation use assembly,
and the release callback, item-6 request and remaining firmware stages still
need their compiler and model joins. Timeouts and missing captures fail the
campaign.

The C is written to stay within what the target will need: no allocation, no
library call in the source and no loop bound read from the image beyond a length
already checked against the composition. The harness compiles it at `-O2`, where
the compiler may turn byte loops into `memcpy` or `memset` calls, so the target
build must add `-ffreestanding -fno-builtin`. Every file here is original and
carries `Apache-2.0` under [COPYRIGHT.md](../COPYRIGHT.md)'s map.
