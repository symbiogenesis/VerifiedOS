# The RTL Tree

*What this repository authored for the FPGA, and nothing else. The imported cores are reached through the gitlinks under `upstream/` and no file of any of them is copied in here.*

## 1. The rule this tree keeps

**Authored and curated files only.** A file belongs here when this repository wrote it. An imported file belongs in the pinned submodule it came from, and the way to use one is to name its path, which is what [`tools/run.py rtl`](../tools/vos/cli/rtl.py) does when it composes a file list across the two.

The reason is the one [THIRD-PARTY.md](../THIRD-PARTY.md) already turns on: a vendored tree binds this repository and a pinned submodule does not. Every imported core on this route is permissively licensed and could be vendored, so the rule is not a licence necessity; it is that a tree holding only what we wrote is a tree whose every line is reviewable as ours, and a curation batch's diff against it means what it appears to mean. `model/` is the opposite case and keeps the opposite rule for a stated reason: it is vendored byte-identically from an upstream pin, so its line endings are frozen in [.gitattributes](../.gitattributes) to keep a batch's line counts honest. Here there is no upstream to stay identical to, so that rule would protect nothing, and the tree takes the repository default instead.

**This is not the RTL artifact of record.** That artifact is a versioned, lint-clean, elaborated SoC top, and it does not exist. What is here is the authored half of one scalar core's curation.

## 2. What is here

| File | What it is |
| --- | --- |
| [synthesis-provenance.md](synthesis-provenance.md) | One row per claimed absence, naming what removes it in a build. R-15-103's second half, and the artifact rule K-76 holds against both the absence contract and the package below |
| [vos_c_class_config_pkg.sv](vos_c_class_config_pkg.sv) | The curated C-class synthesis configuration: the record's parameter values, written as literals at the fields the imported core's own configuration record declares |
| [vos_cheri_pkg.sv](vos_cheri_pkg.sv) | The frozen 64+1-bit capability format and its algebra, authored against the Sail model |

One instrument that reads this tree is deliberately not in it. The cross-check below drives the capability package from a SystemVerilog testbench that reads a file, which is a checking harness and not something this repository would synthesize, so it lives beside the tool that runs it in [tools/cheri-equiv/](../tools/cheri-equiv/).

## 3. What each has been held to, and what it has not

Neither package is verified and neither claims to be. What has been run is stated per file so that a reader does not have to infer it:

- **The configuration package elaborates, and the figures are a lane's measurement rather than something this checkout regenerates.** The imported CHERI-CVA6 core builds under Verilator at this configuration with zero errors, and against the imported tree's own stock CHERI configuration it instantiates eleven fewer module kinds and adds none. It is **not** warning-free: the elaboration emits 272 warnings here and 229 at the baseline, which `tools/run.py rtl elaborate` does not print because it shows the elaborator's output only on a non-zero exit and `-Wno-fatal` keeps warnings out of that exit. Two of them are this package's own, an `unsigned'()` cast at a `bit` field in each of `DcacheFlushOnFence` and `DcacheInvalidateOnFlush`, which the lint gate does not reach because its authored set is the capability package alone. Those three figures are evidence of one run of that command in a checkout with both `upstream/cva6-cheri` and `upstream/opentitan` initialized, and they are recorded here and in [the implementation plan](../docs/implementation-checklist.md)'s completion evidence rather than measured on demand: the command reads both gitlinks, and where one is uninitialized, as `upstream/opentitan` is in the primary checkout, it refuses by name with the `git submodule update --init` line that would let it reproduce them.
- **The capability package lints, and it runs.** It compiles clean under every warning a package can answer, and [`tools/run.py rtl crosscheck`](../tools/vos/cli/rtl.py) builds it under Verilator behind a testbench that replays the model's own vectors, so the functions the vectors name are executed rather than merely compiled. Five are named by no vector, and each is a one-line wrapper over one that is: `set_cap_perms`, `clear_tag`, `clear_tag_if_sealed`, `get_cap_base` and `update_cap_with_integer_pc`. Nothing in the *design* instantiates the package at all, and no elaboration of a core reaches it.
- **The capability package's declared parameters are held against the model, and its functions are held against the model's own answers.** Rule K-79 reads the frozen format out of `cap_format.sail` and `cap_common.sail` and holds every width, every derived figure and both packings against it, on the host, before anything is built. The cross-check decides the rest: the model is compiled with a generator that calls its capability functions and prints what they return, and this package has to reproduce every line, the vectors crossing as text so that no adapter sits between the two implementations. Two of its sweeps are exhaustive over their own domain rather than sampled, decode over the whole 19-bit bounds encoding and the narrowing search over every mask a permission bitmap can take.
- **The configuration package is not checked against the model, and neither package is proved against it.** What a cross-check decides is agreement over the vectors it ran, which is a measurement. The Sail model is the definition, the RTL is the third implementation of it after the model and the emulator fork, and the instrument that decides agreement for a *core* is the capability-widened commit trace of the co-simulation gate. Until that runs, no claim here reaches past the format's own algebra.

## 4. What is owed

The capability package carries the format, the permission lattice, the object-type space, encode and decode, the null transform across the memory interface, the bounds decode, the bounds construction `csetbounds` performs, the representable-limit comparison and the fast representability check, the address and offset setters that rest on it, the length, and the malformed predicate. What it does not carry is named here so that a reader does not have to discover a gap by looking for a function:

- **No instruction and no datapath.** This is the format and its algebra; the unit that decodes an opcode into a call on one of these functions is the rest of R1's curation, along with the caches, the store buffer and the platform devices.
- **`CRAM`, `CRRL` and `CSetBoundsExact` are excluded at the architecture rather than owed here** (R-15-007k, R-08-011), so no representable-alignment mask is computed and none is returned. A reader looking for the rounding surface upstream returns should read that absence as a decision.
- **`capToString` has no RTL reading.** It is the model's debug printer.
- **`perms_count` has none either.** It is a helper inside the model's own narrowing search, and the search here counts with `$countones`.
- **The model's three integer-valued accessors have no counterpart**, `getCapBounds`, `getCapTop` and `getCapOffset` being the unbounded-integer twins of `getCapBoundsBits`, `getCapTopBits` and `getCapOffsetBits`. Sail has an integer type and SystemVerilog does not, so the bits-valued form is the only one there is to write; a reader looking for the pair should read the singular as both.

Beyond the format, three pieces of the curation are authoring work that no configuration parameter reaches, and [the provenance record's §4](synthesis-provenance.md#4-what-no-parameter-reaches-and-what-that-costs) is where they are booked: the flat-SRAM replacement for the two caches, the PMP wrapper shells, and the capability-mode signals.

## 5. Running it

```console
$ python tools/run.py rtl provenance                       # the record, parsed
$ python tools/run.py rtl filelist         # the curated arm's file list, composed
$ python tools/run.py rtl lint             # the authored sources
$ python tools/run.py rtl vectors          # the model's own answers, as text
$ python tools/run.py rtl crosscheck       # and this package reproducing them
$ python tools/run.py rtl elaborate        # both configurations, diffed
$ python tools/run.py rtl elaborate --background
$ python tools/run.py rtl wait             # and its verdict when it lands
```

Verilator is pinned, and a version other than the pin is a finding rather than a warning, which is the disposition the two type checkers and the prover already take. Nothing an elaboration writes lands in this tree: a run works in its own lane's directory, derived from the checkout the same way the model's build lanes are.
