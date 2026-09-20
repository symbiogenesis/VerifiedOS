# The RTL Tree

*What this repository authored for the FPGA, and nothing else. The imported cores are reached through the gitlinks under `upstream/` and no file of any of them is copied in here.*

## 1. The rule this tree keeps

**Authored and generated files only, and no imported one.** A file belongs here when this repository wrote it or when a generator here writes it from an artifact this repository owns. An imported file belongs in the pinned submodule it came from, and the way to use one is to name its path, which is what [`tools/run.py rtl`](../tools/vos/cli/rtl.py) does when it composes a file list across the two.

**A generated source is not an authored one and the difference is the repair.** An authored source is edited; a generated one is regenerated, and rule K-88 holds its bytes against what its generator writes from the artifact that owns the facts in it. The table below says which each file is.

The reason is the one [THIRD-PARTY.md](../THIRD-PARTY.md) already turns on: a vendored tree binds this repository and a pinned submodule does not. Every imported core on this route is permissively licensed and could be vendored, so the rule is not a licence necessity; it is that a tree holding only what we wrote is a tree whose every line is reviewable as ours, and a curation batch's diff against it means what it appears to mean. `model/` is the opposite case and keeps the opposite rule for a stated reason: it is vendored byte-identically from an upstream pin, so its line endings are frozen in [.gitattributes](../.gitattributes) to keep a batch's line counts honest. Here there is no upstream to stay identical to, so that rule would protect nothing, and the tree takes the repository default instead.

**This is not the RTL artifact of record.** That artifact is a versioned, lint-clean, elaborated SoC top, and it does not exist. What is here is the authored half of one scalar core's curation and the map-facing half of the top that would carry it: the address map, the decode over it, and the capability format the datapath computes in. Standalone UART, block and route modules exist, with the simulation boundary stated below. There is no integrated core-facing SoC top or bus.

## 2. What is here

| File | Kind | What it is |
| --- | --- | --- |
| [synthesis-provenance.md](synthesis-provenance.md) | authored | One row per claimed absence, naming what removes it in a build. R-15-103's second half, and the artifact rule K-76 holds against both the absence contract and the package below |
| [vos_c_class_config_pkg.sv](vos_c_class_config_pkg.sv) | authored | The curated C-class synthesis configuration: the record's parameter values, written as literals at the fields the imported core's own configuration record declares |
| [vos_cheri_pkg.sv](vos_cheri_pkg.sv) | authored | The frozen 64+1-bit capability format and its algebra, authored against the Sail model |
| [vos_cva6_cheri_pkg.sv](vos_cva6_cheri_pkg.sv) | authored | The imported datapath's capability package re-pointed at the frozen format: the imported package's name and API identifiers over `vos_cheri_pkg`, carrying the model's capability cause set and `mtval` layout. The first row of [`tools/run.py rtl`](../tools/vos/cli/rtl.py)'s substitution table, standing at the imported package's line of the manifest |
| [vos_soc_map_pkg.sv](vos_soc_map_pkg.sv) | generated | The SoC address map: every declared region with its own PMA bits and every declared aperture with its extent, emitted from [the frozen profile's composition](../model/config/verifiedos.json) by [vos/socmap.py](../tools/vos/socmap.py) and held against it by K-88 |
| [vos_soc_decode.sv](vos_soc_decode.sv) | authored | The SoC top's address decode over that map: which region contains an access, whether that region's PMA permits it, which aperture claims it, and the one case it reports rather than decides |

The additional scalar and device sources have these scoped owners:

| File | Kind | Scope |
| --- | --- | --- |
| [vos_scalar_width_pkg.sv](vos_scalar_width_pkg.sv) | authored | Frozen transport/store rotation under [the scalar staging contract](../docs/hardware/scalar-width-transform-contract.md) |
| [vos_uart.sv](vos_uart.sv) | authored | Bounded polled character backend, no physical UART timing |
| [vos_block_device.sv](vos_block_device.sv) | authored | Logical PIO/progress/reset/tear interface to a synchronous external medium |
| [vos_device_route.sv](vos_device_route.sv) | authored | DTB/error routing over the composed map |

`rtl device-regs` emits the build-local register package from the pinned UART
owner and the logical block contract. [The device contracts](../docs/hardware/platform-device-contracts.md)
own these interfaces. Standalone lint and simulation supply no complete SoC,
physical storage/UART or RTL/Sail refinement result.

One instrument that reads this tree is deliberately not in it. The cross-check below drives the capability package from a SystemVerilog testbench that reads a file, which is a checking harness and not something this repository would synthesize, so it lives beside the tool that runs it in [tools/cheri-equiv/](../tools/cheri-equiv/).

## 3. What each has been held to, and what it has not

No file here is verified and none claims to be. What has been run is stated per file so that a reader does not have to infer it:

- **The curated configuration is an elaboration input, not a current whole-core success.** The current build combines the frozen capability adapter with guarded width, metadata, exception, permission and mode staging. Standalone checks pass; curated core elaboration stops at four unresolved names, the single-root reader, the seal-entry arm and the two mode instructions, which [the staging contract](../docs/hardware/scalar-width-transform-contract.md) records as decisions it does not take. Name resolution is as far as that run reaches, so the member reads behind it are unmeasured rather than absent, and the contract enumerates the residue it leaves to [the delta's](../docs/hardware/rtl-reparameterization-delta.md) own deletion rows. Historical configuration-only receipts are retained in the implementation completion evidence and cannot qualify this changed source set.
- **The address map is a function of the composition and nothing here decides a placement.** Every base, every size and every permission in the map package is read out of [the frozen profile's composition](../model/config/verifiedos.json), which is what R-15-002b makes the artifact that fixes them; K-88 holds the tracked bytes against what the emitter writes, on the host, at every landing. Its apertures are found by shape rather than by a list of names, so a window a composition gains arrives without an edit, which is the defect K-94 already reports one language over in the model's own whole-map check. One declared window is outside it: the revocation sidecar's extent is a model constant rather than a configuration key, so it is carried as a base alone and named as such.
- **The decode module lints and decides three questions of four.** It answers which region contains a whole access, whether that region's own PMA permits it, and which aperture claims it, at the same reading `pmaCheck` takes in the model (`model/model/sys/mem.sail`): a fetch against `executable`, a load against `readable`, a store against `writable`. Its kind input encodes those three and nothing else, and the encoding that names none of them, both bits asserted at once, is **refused rather than decided**: a main-memory region is executable and writable together, so a decode reading the malformed input as a conjunction of the two permissions would admit it wherever the kernel's own code and data live. The fourth, unclaimed device-region routing, is owned by the platform device contract and implemented by `vos_device_route`: ordinary DTB reads in the composed lower ROM interval reach ROM; other unclaimed IO errors. The decoder itself continues to report the case. Sail fallback alignment and the complete SoC comparison remain open.
- **The capability package lints, and it runs.** It compiles clean under every warning a package can answer, and [`tools/run.py rtl crosscheck`](../tools/vos/cli/rtl.py) builds it under Verilator behind a testbench that replays the model's own vectors, so the functions the vectors name are executed rather than merely compiled. Five are named by no vector, and each is a one-line wrapper over one that is: `set_cap_perms`, `clear_tag`, `clear_tag_if_sealed`, `get_cap_base` and `update_cap_with_integer_pc`. The curated build selects the package, but the complete core still fails elaboration at other interfaces.
- **The capability package's declared parameters are held against the model, and its functions are held against the model's own answers.** Rule K-79 reads the frozen format out of `cap_format.sail` and `cap_common.sail` and holds every width, every derived figure and both packings against it, on the host, before anything is built. The cross-check decides the rest: the model is compiled with a generator that calls its capability functions and prints what they return, and this package has to reproduce every line, the vectors crossing as text so that no adapter sits between the two implementations. Two of its sweeps are exhaustive over their own domain rather than sampled, decode over the whole 19-bit bounds encoding and the narrowing search over every mask a permission bitmap can take.
- **The adapter and scalar-width package pass their standalone checks.** The curated-only substitution and transformation contracts bind exact selected inputs and retain source-to-staged diffs. The scalar probe checks the transport/register/PCC widths and every bit/lane of store rotation. No compatibility alias fills the remaining functional interfaces; full core elaboration and instruction refinement remain open.
- **The configuration package is not checked against the model, and no file here is proved against it.** What a cross-check decides is agreement over the vectors it ran, which is a measurement. The Sail model is the definition, the RTL is the third implementation of it after the model and the emulator fork, and the instrument that decides agreement for a *core* is the capability-widened commit trace of the co-simulation gate. Until that runs, no claim here reaches past the format's own algebra and the map's own arithmetic.

## 4. What is owed

The capability package carries the format, the permission lattice, the object-type space, encode and decode, the null transform across the memory interface, the bounds decode, the bounds construction `csetbounds` performs, the representable-limit comparison and the fast representability check, the address and offset setters that rest on it, the length, and the malformed predicate. What it does not carry is named here so that a reader does not have to discover a gap by looking for a function:

- **No instruction and no datapath.** This is the format and its algebra; the unit that decodes an opcode into a call on one of these functions is the rest of R1's curation, along with the caches, the store buffer and the platform devices. The datapath now reaches the format by its own name through the adapter, and what is owed at every site that read a deleted member is the curation of that site, not a member: an adapter that grew one back would elaborate the datapath against a format the model does not state.
- **`CRAM`, `CRRL` and `CSetBoundsExact` are excluded at the architecture rather than owed here** (R-15-007k, R-08-011), so no representable-alignment mask is computed and none is returned. A reader looking for the rounding surface upstream returns should read that absence as a decision.
- **`capToString` has no RTL reading.** It is the model's debug printer.
- **`perms_count` has none either.** It is a helper inside the model's own narrowing search, and the search here counts with `$countones`.
- **The model's three integer-valued accessors have no counterpart**, `getCapBounds`, `getCapTop` and `getCapOffset` being the unbounded-integer twins of `getCapBoundsBits`, `getCapTopBits` and `getCapOffsetBits`. Sail has an integer type and SystemVerilog does not, so the bits-valued form is the only one there is to write; a reader looking for the pair should read the singular as both.

Beyond the format, three pieces of the curation are authoring work that no configuration parameter reaches, and [the provenance record's §4](synthesis-provenance.md#4-what-no-parameter-reaches-and-what-that-costs) is where they are booked: the flat-SRAM replacement for the two caches, the PMP wrapper shells, and the capability-mode signals.

**The SoC top itself is owed and its two halves are owed for different reasons**, which is why the map-facing half is here and the rest is not:

- **The core-facing half waits on the curated datapath.** A top binds the core's port list, and [the delta's §2.2](../docs/hardware/rtl-reparameterization-delta.md) books that list as sites the width collapse and the mode deletion move: the top-level data and `PCLEN` ports follow `CLEN` onto `XLEN` and the `int_mode` and `clr_cap_level` wires go. So a top authored against the imported core today is a top the datapath curation rewrites, and what is authored here is the half that faces the map instead.
- **The device-facing half waits on an elaboration this repository cannot take.** The three devices arrive as route-(c) references through their own gitlink, [the provenance record's §4b](synthesis-provenance.md#4b-the-platform-devices-route-and-what-the-reference-carries-that-this-design-does-not) records the disposition, and what would hold an instantiation of one to the reference's own port list is an elaboration. `run.py rtl elaborate` refuses by name while `upstream/opentitan` is uninitialized, which it is in the primary checkout.
- **Nothing holds the decode against the model.** The format has a cross-check because the model prints what its own functions return; the map has no such generator yet, so the decode module's agreement with `pmaCheck` is an unmeasured claim rather than a measured one.

## 5. Running it

```console
$ python tools/run.py rtl provenance                       # the record, parsed
$ python tools/run.py rtl filelist         # the curated arm's file list, composed
$ python tools/run.py rtl lint             # this repository's own sources under rtl/
$ python tools/run.py rtl vectors          # the model's own answers, as text
$ python tools/run.py rtl crosscheck       # and this package reproducing them
$ python tools/run.py rtl widthcheck       # frozen widths and store rotations
$ python tools/run.py rtl device-regs      # register package from its owners
$ python tools/run.py rtl devicescheck     # standalone device/routing simulation
$ python tools/run.py rtl elaborate        # both configurations, diffed
$ python tools/run.py rtl elaborate --background
$ python tools/run.py rtl wait             # and its verdict when it lands
```

Verilator is pinned, and a version other than the pin is a finding rather than a warning, which is the disposition the two type checkers and the prover already take. Nothing an elaboration writes lands in this tree: a run works in its own lane's directory, derived from the checkout the same way the model's build lanes are.
