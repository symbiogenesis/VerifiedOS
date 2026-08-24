# The RTL Tree

*What this repository authored for the FPGA, and nothing else. The imported cores are reached through the gitlinks under `upstream/` and no file of any of them is copied in here.*

## 1. The rule this tree keeps

**Authored and curated files only.** A file belongs here when this repository wrote it. An imported file belongs in the pinned submodule it came from, and the way to use one is to name its path, which is what [`tools/rtl.py`](../tools/rtl.py) does when it composes a file list across the two.

The reason is the one [THIRD-PARTY.md](../THIRD-PARTY.md) already turns on: a vendored tree binds this repository and a pinned submodule does not. Every imported core on this route is permissively licensed and could be vendored, so the rule is not a licence necessity; it is that a tree holding only what we wrote is a tree whose every line is reviewable as ours, and a curation batch's diff against it means what it appears to mean. `model/` is the opposite case and keeps the opposite rule for a stated reason: it is vendored byte-identically from an upstream pin, so its line endings are frozen in [.gitattributes](../.gitattributes) to keep a batch's line counts honest. Here there is no upstream to stay identical to, so that rule would protect nothing, and the tree takes the repository default instead.

**This is not the RTL artifact of record.** That artifact is a versioned, lint-clean, elaborated SoC top, and it does not exist. What is here is the authored half of one scalar core's curation.

## 2. What is here

| File | What it is |
| --- | --- |
| [synthesis-provenance.md](synthesis-provenance.md) | One row per claimed absence, naming what removes it in a build. R-15-103's second half, and the artifact rule K-76 holds against both the absence contract and the package below |
| [vos_c_class_config_pkg.sv](vos_c_class_config_pkg.sv) | The curated C-class synthesis configuration: the record's parameter values, written as literals at the fields the imported core's own configuration record declares |
| [vos_cheri_pkg.sv](vos_cheri_pkg.sv) | The frozen 64+1-bit capability format, authored against the Sail model |

## 3. What each has been held to, and what it has not

Neither package is verified and neither claims to be. What has been run is stated per file so that a reader does not have to infer it:

- **The configuration package elaborates.** The imported CHERI-CVA6 core builds under Verilator at this configuration with zero errors and zero warnings, and against the imported tree's own stock CHERI configuration it instantiates eleven fewer module kinds and adds none.
- **The capability package lints.** It compiles clean under every warning a package can answer. Nothing instantiates it yet, so no elaboration reaches it and no simulation has ever run a line of it.
- **Neither is checked against the model.** The Sail model is the definition, the RTL is the third implementation of it after the model and the emulator fork, and the instrument that decides agreement is the capability-widened commit trace of the co-simulation gate. Until that runs, every function in the capability package is a transcription owed a check.

## 4. What is owed

The capability package carries the format, the permission lattice, the object-type space, encode and decode, the null transform across the memory interface, and the bounds decode. Three things it does not carry, each named because a reader should not have to discover the gap by looking for a function:

- **`setCapBounds`**, the bounds construction. It is the largest single item of [the re-parameterization delta](../docs/rtl-reparameterization-delta.md) and the one function there that is a rewrite against the model rather than a re-parameterization of the imported source.
- **The fast representability check**, and the address, offset and increment setters that rest on it.
- **`getCapLength`**, which the imported source implements with a saturation its own comment calls short of being correct, and which the model states as a wrapping quantity with an assertion over it.

Beyond the format, four pieces of the curation are authoring work that no configuration parameter reaches, and [the provenance record's §4](synthesis-provenance.md#4-what-no-parameter-reaches-and-what-that-costs) is where they are booked: the flat-SRAM replacement for the two caches, the PMP wrapper shells, the capability-mode signals, and the static-only prediction rule.

## 5. Running it

```console
$ python tools/rtl.py provenance                       # the record, parsed
$ wsl -u root -e python3 tools/rtl.py lint             # the authored sources
$ wsl -u root -e python3 tools/rtl.py elaborate        # both configurations, diffed
$ wsl -u root -e python3 tools/rtl.py elaborate --background
$ wsl -u root -e python3 tools/rtl.py wait             # and its verdict when it lands
```

Verilator is pinned, and a version other than the pin is a finding rather than a warning, which is the disposition the two type checkers and the prover already take. Nothing an elaboration writes lands in this tree: a run works in its own lane's directory, derived from the checkout the same way the model's build lanes are.
