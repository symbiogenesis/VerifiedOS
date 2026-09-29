# Formal Specification of the RISC-V ISA

This repository contains a formal specification of the RISC-V architecture, written in
[Sail](https://github.com/rems-project/sail). It has been adopted by RISC-V International.

The model specifies assembly language formats of the instructions, the corresponding
encoders and decoders, and the instruction semantics.

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

When running this emulator on a RISC-V ELF binary (`test.elf`), the
emulator can also be a provided a configuration file in JSON format
(named `dut_config.json` above). If no configuration file is
provided, a default RV64 configuration is assumed; this default
configuration can be printed using the `--print-default-config` option
to the `sail_riscv_sim` emulator. A _template_ for the configuration
files that are used to test the model is
[here](config/config.json.in); this template will need to be edited to
match a desired configuration.

The Sail compiler also generates a JSON schema
(`sail_riscv_config_schema.json`) for the configuration file from the
Sail sources; every configuration file is validated against this
schema before use. This file will be in the directory containing the
build artifacts after a build of the model, and is also available in
the [binary releases](#using-the-binary-releases) of the model.

More information on using the emulator is available using its `-h`
help command-line option.

The Sail model can also be used to generate `JSON` and `HTML`
artifacts for documentation. A prototype of their use to annotate the
unprivileged volume of the RISC-V specification is available
[here](https://github.com/Timmmm/riscv-isa-manual).

## Getting started

### Using the binary releases

Recent released versions of the model have binaries for the `x86_64`
and ARM `aarch64` Linux platforms, available
[here](https://github.com/riscv/sail-riscv/releases). The executable
model is at `bin/sail_riscv_sim`. Sample model configurations are
under the `share/sail-riscv/config` directory, and the configuration
schema is available under
`share/sail-riscv/sail_riscv_config_schema.json`. A custom
configuration can be created by copying one of the sample
configurations and editing it as needed (see also
[below](#configuring-platform-options)).

### Building the model from source

Install [Sail](https://github.com/rems-project/sail/). On Linux you can download a [binary release](https://github.com/rems-project/sail/releases) (strongly recommended), or you can install from source [using opam](https://github.com/rems-project/sail/blob/sail2/INSTALL.md). Then:

```
$ ./build_simulator.sh
```

will build the simulator at `build/c_emulator/sail_riscv_sim`.

If you get an error message saying `sail: unknown option '--require-version'.` it's because your Sail compiler is too old. You need version 0.20.2 or later.

By default [`build_simulator.sh`](./build_simulator.sh) will download and build [libgmp](https://gmplib.org).
To use a system installation of libgmp, run `env DOWNLOAD_GMP=FALSE ./build_simulator.sh` instead.

### Executing test binaries

The simulator can be used to execute small test binaries.

```
$ build/c_emulator/sail_riscv_sim <elf-file>
```

Test suites targeting RV32, RV64, and RVV (RISC-V Vector Extension) are downloaded automatically when enabled.
The standard `riscv-tests` suite is enabled by default, while vector extension tests
can be enabled via CMake options such as `-DENABLE_RISCV_VECTOR_TESTS_V128_E32=ON`.
All enabled test suites can be executed using `make test` or `ctest` in the build directory
(see [`test/README.md`](test/README.md) for more information).

### Configuring platform options

The model is configured using a JSON file specifying various tunable
options. The default configuration used for the model can be examined
using the `--print-default-config` option. To
use a custom configuration, save the default configuration into a
file, edit it as needed, and pass it to the simulator using the
`--config` option.

To override only a small subset of options while using the default configuration
or a custom configuration file as a base, the `--config-override` option can be
used. This option allows one or more additional JSON configuration files to be specified,
whose fields take precedence over those in the base configuration.

### Attaching a debugger

The simulator can offer a `gdbserver`-like endpoint for debuggers like
GDB and LLDB. See [here](c_emulator/gdb/README.md) for more
information.

## Supported RISC-V ISA features

The `enum clause extension` declarations in
[`core/extensions.sail`](model/core/extensions.sail) are the extensions
these sources capture, each followed by the `hartSupports` clause that
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

These are verbatim excerpts from the model file containing the base instructions, [I/base_insts.sail](model/extensions/I/base_insts.sail), with a few comments added.

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

mapping clause encdec = ITYPE(imm, rs1, rd, op) <-> imm @ encdec_reg(rs1) @ encdec_iop(op) @ encdec_reg(rd) @ 0b0010011

/* the execution semantics for the ITYPE instructions */

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

### SRET

```
union clause instruction = SRET : unit

mapping clause encdec = SRET()
  <-> 0b0001000 @ 0b00010 @ 0b00000 @ 0b000 @ 0b00000 @ 0b1110011

function clause execute SRET() = {
  let sret_illegal : bool = match cur_privilege {
    User       => true,
    Supervisor => not(currentlyEnabled(Ext_S)) | mstatus[TSR] == 0b1,
    Machine    => not(currentlyEnabled(Ext_S))
  };
  if   sret_illegal
  then Illegal_Instruction()
  else if not(ext_check_xret_priv (Supervisor))
  then Ext_XRET_Priv_Failure()
  else {
    set_next_pc(exception_handler(cur_privilege, CTL_SRET(), PC));
    RETIRE_SUCCESS
  }
}

mapping clause assembly = SRET() <-> "sret"
```

## Sequential execution

The model builds a C++ emulator that can execute RISC-V ELF
files and provides platform support sufficient to boot
Linux, FreeBSD and seL4.

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

The ISA model is integrated with the operational model of the RISC-V
relaxed memory model, RVWMO (as described in an appendix of the [RISC-V
user-level specification](https://docs.riscv.org/reference/isa/unpriv/mm-eplan.html))
which is one of the reference models used
in the development of the RISC-V concurrency architecture; this is
part of the [RMEM](http://www.cl.cam.ac.uk/users/pes20/rmem) tool.
It is also integrated with the RISC-V axiomatic concurrency model
as part of the [isla-axiomatic](https://isla-axiomatic.cl.cam.ac.uk/) tool.

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

Sail aims to support the generation of idiomatic theorem prover
definitions across multiple tools. Of those, this tree builds Rocq alone.
There is no Isabelle, HOL4 or Lean target and no handwritten Lem or Lean
library under one, because a dormant target's support is model state that
goes stale where no typechecker can see it.

These theorem-prover translations can target multiple monads for
different purposes. The first is a state monad with nondeterminism and
exceptions, suitable for reasoning in a sequential setting, assuming
that effectful expressions are executed without interruptions and with
exclusive access to the state.

For reasoning about concurrency, where instructions execute
out-of-order, speculatively, and non-atomically, there is a free
monad over an effect datatype of memory actions. This monad is also
used as part of the aforementioned concurrency support via the RMEM
tool.

The files under [`handwritten_support`](./handwritten_support) provide the library
definitions Rocq needs. Building the Rocq output also needs the `rocq-sail-stdpp`
library, which the project's switches do not carry;
[the opam guide](../tools/opam/README.md) says when to add it back.

## Directory Structure

```
sail-riscv
- model                   // Sail specification modules
- handwritten_support     // prover support files
- c_emulator              // supporting platform files for C emulator
- cmake                   // extra build system modules
- dependencies            // external dependencies
- sail_runtime            // build files for sail runtime
- test                    // CMake test setup and URL references for RISC-V test suites
```

## Licence

The model is made available under the BSD two-clause licence in [LICENCE](./LICENCE).

## Authors

Originally written by Prashanth Mundkur at SRI International, and further developed by others, especially researchers at the University of Cambridge.

See [`LICENCE`](./LICENCE) and Git blame for a complete list of authors.

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
