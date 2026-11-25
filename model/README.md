# Formal Specification of the RISC-V ISA

This tree is a curated derivative of [sail-riscv](https://github.com/riscv/sail-riscv),
the formal specification of the RISC-V architecture written in
[Sail](https://github.com/rems-project/sail) and adopted by RISC-V International,
with capability semantics transplanted from
[sail-cheri-riscv](https://github.com/CTSRD-CHERI/sail-cheri-riscv) for a
purecap-only machine.

The model defines assembly syntax, instruction encodings and execution semantics
for the [VerifiedOS ISA profile](../docs/hardware/isa-profile.md).

## What is Sail?

[Sail](https://github.com/rems-project/sail) is a language for describing the instruction-set architecture
(ISA) semantics of processors: the architectural specification of the behaviour of machine instructions. Sail is an
engineer-friendly language, much like earlier vendor pseudocode, but more precisely defined and with tooling to support a wide range of use-cases.

Given a Sail specification, the tool can type-check it, generate documentation snippets (in LaTeX or AsciiDoc), generate executable emulators, show specification coverage, generate versions of the ISA for relaxed memory model tools, support automated instruction-sequence test generation, generate theorem-prover definitions for
interactive proof (in Rocq), support proof about binary code (in Islaris), and (in progress) generate a reference ISA model in SystemVerilog that can be used for formal hardware verification.

<img width="800" src="https://www.cl.cam.ac.uk/~pes20/sail/overview-sail.png?raw=true">

## Using the Sail RISC-V specification

The Sail components of the model are a Sail project file
[`riscv.sail_project`](model/riscv.sail_project) and several
associated files of Sail source code. The Sail compiler translates
these components into a C++ model (`sail_riscv_model.{h,cpp}`), which
is then wrapped in a C++ harness and compiled into a `sail_riscv_sim`
executable binary to give an RISC-V emulator.

Pass a JSON configuration to the emulator with `--config FILE`. For the
VerifiedOS scalar profile, use [`verifiedos.json`](config/verifiedos.json).
With no configuration file, the emulator uses its compiled-in default.
Use `--print-default-config` to print that JSON or inspect the
[CMake configuration template](config/config.json.in).

The Sail compiler also generates a JSON schema
(`sail_riscv_config_schema.json`) for the configuration file from the
Sail sources; every configuration file is validated against this
schema before use. This file will be in the directory containing the
build artifacts after a build of the model, and the emulator prints it
with the `--print-config-schema` option.

More information on using the emulator is available using its `-h`
help command-line option.

The Sail model can also be used to generate `JSON` and `HTML`
artifacts for documentation. A prototype of their use to annotate the
unprivileged volume of the RISC-V specification is available
[here](https://github.com/Timmmm/riscv-isa-manual).

## Getting started

### Building the model from source

Upstream's [binary releases](https://github.com/riscv/sail-riscv/releases)
build upstream's model rather than this curated one, so this tree is
built from source.

Install [Sail](https://github.com/rems-project/sail/). On Linux you can download a [binary release](https://github.com/rems-project/sail/releases) (strongly recommended), or you can install from source [using opam](https://github.com/rems-project/sail/blob/sail2/INSTALL.md). Then:

```
$ ./build_simulator.sh
```

will build the simulator at `build/c_emulator/sail_riscv_sim`.
Within this repository the model is built with `python tools/run.py model build`
against the locked Sail switch that [the opam guide](../tools/opam/README.md) names.

If you get an error message saying `sail: unknown option '--require-version'.` it's because your Sail compiler is too old. You need the version in [`cmake/sail_required_version.txt`](cmake/sail_required_version.txt) or later.

By default [`build_simulator.sh`](./build_simulator.sh) will download and build [libgmp](https://gmplib.org).
To use a system installation of libgmp, run `env DOWNLOAD_GMP=FALSE ./build_simulator.sh` instead.

### Executing test binaries

The simulator can be used to execute small test binaries.

```
$ build/c_emulator/sail_riscv_sim <elf-file>
```

The [test guide](test/README.md) explains which external programs CMake
downloads, which it registers with CTest, and why the profile sweep runs the
stock RV64 suite separately. The model's [Sail unit tests and native
harnesses](test/unit_tests/README.md) are registered with CTest. Follow the
[repository check schedule](../tools/README.md#check-scheduling-during-fan-out)
when selecting local checks.

### Configuring platform options

Use `--config-override FILE` to override selected fields of the compiled-in
default or the JSON selected by `--config`. Repeat the option to apply multiple
override files.

### Attaching a debugger

See the [remote debugger setup](c_emulator/gdb/README.md) for connecting GDB
or LLDB to the emulator.

## Supported RISC-V ISA features

The `enum clause extension` declarations in
[`core/extensions.sail`](model/core/extensions.sail) are the extensions
these sources capture, each with the `hartSupports` clause that
decides whether a hart supports it. Some name a property of the
implementation rather than instructions, and the shorthand extensions
are supported exactly when their components are. The RV64I base, the
CHERI capability extension and the platform's custom instructions have
no entry there: the capability format, registers and checks are core
([`core/cap_format.sail`](model/core/cap_format.sail)), the capability
instructions are under [`extensions/CHERI`](model/extensions/CHERI), and
[`riscv.sail_project`](model/riscv.sail_project) names every module.

The configurations under [`config`](config) choose among those
extensions: [`verifiedos.json`](config/verifiedos.json) is the profile
configuration, and [`verifiedos-v.json`](config/verifiedos-v.json) and
[`verifiedos-rot.json`](config/verifiedos-rot.json) are its V-class and
Root of Trust compositions. [The frozen instruction-set
profile](../docs/hardware/isa-profile.md) is the admitted set the
curation retains, including the base, the single Machine privilege mode
and the untranslated physical address space.

The emulator keeps upstream's `--enable-experimental-extensions` flag,
but no extension in these sources reads it.

## Example RISC-V instruction specifications

These examples illustrate the instruction declarations in
[`I/base_insts.sail`](model/extensions/I/base_insts.sail).

### ITYPE (or ADDI)

```
/* the instruction clause for the ITYPE instructions */

union clause instruction = ITYPE : (bits(12), regidx, regidx, iop)

/* the encode/decode mapping between instruction elements and 32-bit words */

mapping encdec_iop : iop <-> bits(3) = {
  ADDI  <-> 0b000,
  SLTI  <-> 0b010,
  SLTIU <-> 0b011,
  ANDI  <-> 0b111,
  ORI   <-> 0b110,
  XORI  <-> 0b100
}

mapping clause encdec = ITYPE(imm, rs1, rd, op)
  <-> imm @ encdec_reg(rs1) @ encdec_iop(op) @ encdec_reg(rd) @ 0b0010011

/* the execution semantics for the ITYPE instructions */

$[split op]
function clause execute ITYPE(imm, rs1, rd, op) = {
  let immext : xlenbits = sign_extend(imm);
  X(rd) = match op {
    ADDI  => X(rs1) + immext,
    SLTI  => zero_extend(bool_to_bit(X(rs1) <_s immext)),
    SLTIU => zero_extend(bool_to_bit(X(rs1) <_u immext)),
    ANDI  => X(rs1) & immext,
    ORI   => X(rs1) | immext,
    XORI  => X(rs1) ^ immext
  };
  RETIRE_SUCCESS
}

/* the assembly/disassembly mapping between instruction elements and strings */

mapping itype_mnemonic : iop <-> string = {
  ADDI  <-> "addi",
  SLTI  <-> "slti",
  SLTIU <-> "sltiu",
  XORI  <-> "xori",
  ORI   <-> "ori",
  ANDI  <-> "andi"
}

mapping clause assembly = ITYPE(imm, rs1, rd, op)
  <-> itype_mnemonic(op) ^ spc() ^ reg_name(rd) ^ sep() ^ reg_name(rs1) ^ sep() ^ hex_bits_signed_12(imm)
```

### MRET

```
union clause instruction = MRET : unit

mapping clause encdec = MRET()
  <-> 0b0011000 @ 0b00010 @ 0b00000 @ 0b000 @ 0b00000 @ 0b1110011

// `mret` no longer transfers privilege: with one mode it restores the
// interrupt-enable stack and returns to `mepc`. `sret` is deleted with
// the mode there is no returning to (R-15-003).
function clause execute MRET() = {
  if   not(ext_check_xret_priv())
  then Ext_XRET_Priv_Failure()
  else {
    mstatus[MIE]  = mstatus[MPIE];
    mstatus[MPIE] = 0b1;

    long_csr_write_callback("mstatus", mstatus.bits);

    set_next_pc(prepare_xret_target());
    trap_path_live = false;

    xret_callback(true);
    RETIRE_SUCCESS
  }
}

mapping clause assembly = MRET() <-> "mret"
```

## Sequential execution

The model builds a C++ emulator that can execute RISC-V ELF
files on the platform its configuration describes.

The files in the [`c_emulator`](c_emulator) directory implement ELF
loading, the platform devices, and the physical memory map, and
perform configuration validation before configuring the selected ISA
choices.

### Use for specification coverage measurement in testing

The Sail-generated emulator can measure specification branch
coverage of any executed tests, displaying the results as per-file
tables and as html-annotated versions of the model source.

### Use as test oracle in tandem verification

For tandem verification of random instruction streams, the tools support the
protocols used in [TestRIG](https://github.com/CTSRD-CHERI/TestRIG) to
directly inject instructions into the emulator and produce trace
information in RVFI format. This has been used for cross testing
against spike and the [RVBS](https://github.com/CTSRD-CHERI/RVBS)
specification written in Bluespec SystemVerilog.

## Concurrent execution

Upstream's ISA model is integrated with the operational model of the RISC-V
relaxed memory model, RVWMO (as described in an appendix of the [RISC-V
user-level specification](https://docs.riscv.org/reference/isa/unpriv/mm-eplan.html))
which is one of the reference models used
in the development of the RISC-V concurrency architecture; this is
part of the [RMEM](http://www.cl.cam.ac.uk/users/pes20/rmem) tool.
It is also integrated with the RISC-V axiomatic concurrency model
as part of the [isla-axiomatic](https://isla-axiomatic.cl.cam.ac.uk/) tool.
This tree names Ztso, the architecture's memory model in place of RVWMO, as a
hardwired extension ([`core/extensions.sail`](model/core/extensions.sail)); its
single-hart model has no execution that separates TSO from sequential
consistency, and no RMEM or isla-axiomatic target builds from it.

### Concurrent testing

As part of the University of Cambridge/ INRIA concurrency architecture work, those groups produced and
released a library of approximately 7000 [litmus
tests](https://github.com/litmus-tests/litmus-tests-riscv). The
operational and axiomatic RISC-V concurrency models are in sync for
these tests, and they moreover agree with the corresponding ARM
architected behaviour for the tests in common.

Those tests have also been run on RISC-V hardware, on a SiFive RISC-V
FU540 multicore proto board (Freedom Unleashed), kindly on loan from
Imperas. To date, only sequentially consistent behaviour was observed there.

## Generating theorem-prover definitions

`python tools/run.py model rocq` emits the [canonical machine
term](../docs/assurance/canonical-machine-term.md) for the frozen scalar
composition. The [handwritten support module](handwritten_support/riscv_extras.v)
supplies definitions used by that output. Compiling the emitted term requires
`rocq-sail-stdpp`. The [opam guide](../tools/opam/README.md) records the package
qualification and conditions for including it in a locked switch.

## Directory Structure

```
model
- model                   // Sail specification modules
- handwritten_support     // prover support files
- c_emulator              // supporting platform files for C emulator
- cmake                   // extra build system modules
- config                  // configuration template and profile configurations
- dependencies            // external dependencies
- sail_runtime            // build files for sail runtime
- test                    // CMake test setup, native harnesses and URL references for RISC-V test suites
```

## Licence

The model is made available under the BSD two-clause licence in [LICENCE](./LICENCE).
The capability semantics transplanted from
[sail-cheri-riscv](https://github.com/CTSRD-CHERI/sail-cheri-riscv) and the
capability-helper properties transcribed from
[sail-cheri-riscv-verif](https://github.com/CTSRD-CHERI/sail-cheri-riscv-verif)
keep their BSD two-clause notices in [LICENCE.cheri](./LICENCE.cheri) and
[LICENCE.cheri-verif](./LICENCE.cheri-verif).

## Authors

Originally written by Prashanth Mundkur at SRI International, and further developed by others, especially researchers at the University of Cambridge.

See [`LICENCE`](./LICENCE), [`LICENCE.cheri`](./LICENCE.cheri),
[`LICENCE.cheri-verif`](./LICENCE.cheri-verif) and the Git history of the
upstream repositories and of this one for a complete list of authors.

## Funding

This software was developed by the above within the Rigorous
Engineering of Mainstream Systems (REMS) project, partly funded by
EPSRC grant EP/K008528/1, at the Universities of Cambridge and
Edinburgh.

This software was developed by SRI International and the University of
Cambridge Computer Laboratory (Department of Computer Science and
Technology) under DARPA/AFRL contract FA8650-18-C-7809 ("CIFV"), and
under DARPA contract HR0011-18-C-0016 ("ECATS") as part of the DARPA
SSITH research programme.

This project has received funding from the European Research Council
(ERC) under the European Union’s Horizon 2020 research and innovation
programme (grant agreement 789108, ELVER).
