// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Enum with all extensions possibly supported by the model.
scattered enum extension

// Name of extension.  The current primary consumer of these names is
// the device tree support, which uses lower case.  Since the ISA
// naming strings are case-insensitive anyway, the names are lowercase.
val extensionName : extension <-> string
scattered mapping extensionName

// Function used to determine if an extension is supported in the current configuration.
val hartSupports : extension -> bool
scattered function hartSupports

// Function used to determine if an extension is currently enabled in the model.
// This means an extension is supported, *and* any necessary bits are set in the
// relevant CSRs (misa, mstatus, etc.) to enable its use. It is possible for some
// extensions to be supported in hardware, but temporarily disabled via a CSR, in
// which case this function should return false.
// Note: when adding a new extension, adjust the `currentlyEnabled_measure` below.
val currentlyEnabled : extension -> bool
scattered function currentlyEnabled

// Note, these are sorted according to the canonical ordering vaguely described
// in the `Subset Naming Convention` section of the unprivileged spec.

// Integer Multiplication and Division; not Machine!
enum clause extension = Ext_M
mapping clause extensionName = Ext_M <-> "m"
function clause hartSupports(Ext_M) = config extensions.M.supported
// Atomic Instructions
enum clause extension = Ext_A
mapping clause extensionName = Ext_A <-> "a"
function clause hartSupports(Ext_A) = config extensions.A.supported

// Bit Manipulation
enum clause extension = Ext_B
mapping clause extensionName = Ext_B <-> "b"
function clause hartSupports(Ext_B) = config extensions.B.supported
// Vector Operations
enum clause extension = Ext_V
mapping clause extensionName = Ext_V <-> "v"
function clause hartSupports(Ext_V) = sizeof(vlen_exp) >= 7 & vector_support_level >= Full
// Supervisor and User are not extensions this model can name: there
// is one privilege mode (R-15-003).

// Cache block size is 64 bytes
enum clause extension = Ext_Zic64b
mapping clause extensionName = Ext_Zic64b <-> "zic64b"
function clause hartSupports(Ext_Zic64b) = config extensions.Zic64b.supported
function clause currentlyEnabled(Ext_Zic64b) = hartSupports(Ext_Zic64b)
// Cache-Block Zero Instructions
enum clause extension = Ext_Zicboz
mapping clause extensionName = Ext_Zicboz <-> "zicboz"
function clause hartSupports(Ext_Zicboz) = config extensions.Zicboz.supported
// Integer Conditional Operations
enum clause extension = Ext_Zicond
mapping clause extensionName = Ext_Zicond <-> "zicond"
function clause hartSupports(Ext_Zicond) = config extensions.Zicond.supported
// Extension for Control and Status Register (CSR) Instructions
enum clause extension = Ext_Zicsr
mapping clause extensionName = Ext_Zicsr <-> "zicsr"
function clause hartSupports(Ext_Zicsr) = config extensions.Zicsr.supported

// Multiplication and Division: Multiplication only
enum clause extension = Ext_Zmmul
mapping clause extensionName = Ext_Zmmul <-> "zmmul"
function clause hartSupports(Ext_Zmmul) = config extensions.Zmmul.supported

// Atomic Memory Operations
enum clause extension = Ext_Zaamo
mapping clause extensionName = Ext_Zaamo <-> "zaamo"
function clause hartSupports(Ext_Zaamo) = config extensions.Zaamo.supported
// Byte and Halfword Atomic Memory Operations
enum clause extension = Ext_Zabha
mapping clause extensionName = Ext_Zabha <-> "zabha"
function clause hartSupports(Ext_Zabha) = config extensions.Zabha.supported
// The Atomic Compare-and-Swap extension `Zacas` is gone (R-15-026, R-15-027).
// It is not a supported-flag reading false: no `AMOCAS` operand, encoding,
// execute path or PMA level remains for a configuration to re-enable, so the
// exclusion is a property of this model and survives being handed any
// configuration at all.
// Extension for 16-byte Misaligned Atomicity
enum clause extension = Ext_Zama16b
mapping clause extensionName = Ext_Zama16b <-> "zama16b"
function clause hartSupports(Ext_Zama16b) = config extensions.Zama16b.supported
function clause currentlyEnabled(Ext_Zama16b) = hartSupports(Ext_Zama16b)


// Bit Manipulation: Address generation
enum clause extension = Ext_Zba
mapping clause extensionName = Ext_Zba <-> "zba"
function clause hartSupports(Ext_Zba) = config extensions.Zba.supported
// Bit Manipulation: Basic bit-manipulation
enum clause extension = Ext_Zbb
mapping clause extensionName = Ext_Zbb <-> "zbb"
function clause hartSupports(Ext_Zbb) = config extensions.Zbb.supported
// Bit Manipulation: Carry-less multiplication
enum clause extension = Ext_Zbc
mapping clause extensionName = Ext_Zbc <-> "zbc"
function clause hartSupports(Ext_Zbc) = config extensions.Zbc.supported
// Bit Manipulation: Bit-manipulation for Cryptography
enum clause extension = Ext_Zbkb
mapping clause extensionName = Ext_Zbkb <-> "zbkb"
function clause hartSupports(Ext_Zbkb) = config extensions.Zbkb.supported
// Bit Manipulation: Carry-less multiplication for Cryptography
enum clause extension = Ext_Zbkc
mapping clause extensionName = Ext_Zbkc <-> "zbkc"
function clause hartSupports(Ext_Zbkc) = config extensions.Zbkc.supported
// Bit Manipulation: Crossbar permutations
enum clause extension = Ext_Zbkx
mapping clause extensionName = Ext_Zbkx <-> "zbkx"
function clause hartSupports(Ext_Zbkx) = config extensions.Zbkx.supported
// Bit Manipulation: Single-bit instructions
enum clause extension = Ext_Zbs
mapping clause extensionName = Ext_Zbs <-> "zbs"
function clause hartSupports(Ext_Zbs) = config extensions.Zbs.supported

// Main memory supports all atomics in Zaamo
enum clause extension = Ext_Ziccamoa
mapping clause extensionName= Ext_Ziccamoa <-> "ziccamoa"
function clause hartSupports(Ext_Ziccamoa) = config extensions.Ziccamoa.supported
// `Ziccamoc`, main memory supporting the atomics in `Zacas`, is gone with the
// atomics it names: it is a claim about a form no configuration of this model
// can issue, so it has no referent rather than a false value. `Ziccamoa`
// above is a different extension and stays, its subject being the `Zaamo`
// atomics the profile does admit (R-15-024).
// Instruction-Fetch Atomicity
enum clause extension = Ext_Ziccif
mapping clause extensionName = Ext_Ziccif <-> "ziccif"
function clause hartSupports(Ext_Ziccif) = config extensions.Ziccif.supported
function clause currentlyEnabled(Ext_Ziccif) = hartSupports(Ext_Ziccif)
// Main memory misaligned accesses
enum clause extension = Ext_Zicclsm
mapping clause extensionName = Ext_Zicclsm <-> "zicclsm"
function clause hartSupports(Ext_Zicclsm) = config extensions.Zicclsm.supported
function clause currentlyEnabled(Ext_Zicclsm) = hartSupports(Ext_Zicclsm)

// Data Independent Execution Latency
enum clause extension = Ext_Zkt
mapping clause extensionName = Ext_Zkt <-> "zkt"
function clause hartSupports(Ext_Zkt) = config extensions.Zkt.supported
function clause currentlyEnabled(Ext_Zkt) = hartSupports(Ext_Zkt)

// Total Store Ordering
//
// The one row in this registry that is not read from a configuration key, and
// the absence of the key is the requirement rather than an oversight. The
// architectural memory model *is* Ztso, adopted normatively in place of RVWMO
// (R-15-004, R-15-243), and every ring proof is restated under it; a
// `extensions.Ztso.supported` key would make the memory model a composition
// parameter and admit a composition of this machine that is not this machine.
// It is a bring-up property and not a later addition (R-18-006), so it is
// declared here, from the first emission, hardwired.
//
// What it buys the model today is naming: `hartSupports` is what the generated
// `riscv,isa` string and `riscv,isa-extensions` array are built from
// (postlude/device_tree.sail), so an attested devicetree now says which memory
// model the hart implements where it said nothing. The ordering itself is a
// microarchitectural property of the store buffer and the fabric beneath it, and
// stating it is an RTL-against-Sail obligation rather than something this model
// can exhibit (R-15-016): a single-hart, single-copy model has no execution that
// separates TSO from sequential consistency.
enum clause extension = Ext_Ztso
mapping clause extensionName = Ext_Ztso <-> "ztso"
function clause hartSupports(Ext_Ztso) = true
function clause currentlyEnabled(Ext_Ztso) = hartSupports(Ext_Ztso)


// Standard Vector Extensions
// Minimum Vector Length Standard Extensions
enum clause extension = Ext_Zvl32b
mapping clause extensionName = Ext_Zvl32b <-> "zvl32b"
function clause hartSupports(Ext_Zvl32b) = sizeof(vlen_exp) >= 5
enum clause extension = Ext_Zvl64b
mapping clause extensionName = Ext_Zvl64b <-> "zvl64b"
function clause hartSupports(Ext_Zvl64b) = sizeof(vlen_exp) >= 6
enum clause extension = Ext_Zvl128b
mapping clause extensionName = Ext_Zvl128b <-> "zvl128b"
function clause hartSupports(Ext_Zvl128b) = sizeof(vlen_exp) >= 7
enum clause extension = Ext_Zvl256b
mapping clause extensionName = Ext_Zvl256b <-> "zvl256b"
function clause hartSupports(Ext_Zvl256b) = sizeof(vlen_exp) >= 8
enum clause extension = Ext_Zvl512b
mapping clause extensionName = Ext_Zvl512b <-> "zvl512b"
function clause hartSupports(Ext_Zvl512b) = sizeof(vlen_exp) >= 9
enum clause extension = Ext_Zvl1024b
mapping clause extensionName = Ext_Zvl1024b <-> "zvl1024b"
function clause hartSupports(Ext_Zvl1024b) = sizeof(vlen_exp) >= 10
// The ladder upstream stops at 1024 because upstream stops there. This
// profile's V class is VLEN=4096 and its M class VLEN=1024 (R-15-113), so
// a truncated ladder would leave a V-class build reporting `zvl1024b` as
// its widest guarantee in the generated `riscv,isa` string and in the
// attested devicetree, which is a machine describing itself as narrower
// than it is. Both rungs read false at every geometry this model is built
// at today, so nothing observable moves until M0.8's V-class half lands.
enum clause extension = Ext_Zvl2048b
mapping clause extensionName = Ext_Zvl2048b <-> "zvl2048b"
function clause hartSupports(Ext_Zvl2048b) = sizeof(vlen_exp) >= 11
enum clause extension = Ext_Zvl4096b
mapping clause extensionName = Ext_Zvl4096b <-> "zvl4096b"
function clause hartSupports(Ext_Zvl4096b) = sizeof(vlen_exp) >= 12
// Vector Extensions for Embedded Processors
enum clause extension = Ext_Zve32f
mapping clause extensionName = Ext_Zve32f <-> "zve32f"
function clause hartSupports(Ext_Zve32f) = sizeof(elen_exp) >= 5 & vector_support_level >= Float_single
enum clause extension = Ext_Zve32x
mapping clause extensionName = Ext_Zve32x <-> "zve32x"
function clause hartSupports(Ext_Zve32x) = sizeof(elen_exp) >= 5 & vector_support_level >= Integer
enum clause extension = Ext_Zve64d
mapping clause extensionName = Ext_Zve64d <-> "zve64d"
function clause hartSupports(Ext_Zve64d) = sizeof(elen_exp) >= 6 & vector_support_level >= Float_double
enum clause extension = Ext_Zve64f
mapping clause extensionName = Ext_Zve64f <-> "zve64f"
function clause hartSupports(Ext_Zve64f) = sizeof(elen_exp) >= 6 & vector_support_level >= Float_single
enum clause extension = Ext_Zve64x
mapping clause extensionName = Ext_Zve64x <-> "zve64x"
function clause hartSupports(Ext_Zve64x) = sizeof(elen_exp) >= 6 & vector_support_level >= Integer
// Vector BF16 Converts
enum clause extension = Ext_Zvfbfmin
mapping clause extensionName = Ext_Zvfbfmin <-> "zvfbfmin"
function clause hartSupports(Ext_Zvfbfmin) = config extensions.Zvfbfmin.supported
// Vector BF16 widening mul-add
enum clause extension = Ext_Zvfbfwma
mapping clause extensionName = Ext_Zvfbfwma <-> "zvfbfwma"
function clause hartSupports(Ext_Zvfbfwma) = config extensions.Zvfbfwma.supported
// Vector Extension for Half-Precision Floating-Point
enum clause extension = Ext_Zvfh
mapping clause extensionName = Ext_Zvfh <-> "zvfh"
function clause hartSupports(Ext_Zvfh) = config extensions.Zvfh.supported
// Vector Extension for Minimal Half-Precision Floating-Point
enum clause extension = Ext_Zvfhmin
mapping clause extensionName = Ext_Zvfhmin <-> "zvfhmin"
function clause hartSupports(Ext_Zvfhmin) = config extensions.Zvfhmin.supported

// Vector Basic Bit-manipulation
enum clause extension = Ext_Zvbb
mapping clause extensionName = Ext_Zvbb <-> "zvbb"
function clause hartSupports(Ext_Zvbb) = config extensions.Zvbb.supported
// Vector Carryless Multiplication
enum clause extension = Ext_Zvbc
mapping clause extensionName = Ext_Zvbc <-> "zvbc"
function clause hartSupports(Ext_Zvbc) = config extensions.Zvbc.supported
// Vector Cryptography Bit-manipulation
enum clause extension = Ext_Zvkb
mapping clause extensionName = Ext_Zvkb <-> "zvkb"
function clause hartSupports(Ext_Zvkb) = config extensions.Zvkb.supported
// Vector GCM/GMAC
enum clause extension = Ext_Zvkg
mapping clause extensionName = Ext_Zvkg <-> "zvkg"
function clause hartSupports(Ext_Zvkg) = config extensions.Zvkg.supported
// NIST Suite: Vector AES Block Cipher
enum clause extension = Ext_Zvkned
mapping clause extensionName = Ext_Zvkned <-> "zvkned"
function clause hartSupports(Ext_Zvkned) = config extensions.Zvkned.supported
// NIST Suite: Vector SHA-2 Secure Hash (SHA-256 only)
enum clause extension = Ext_Zvknha
mapping clause extensionName = Ext_Zvknha <-> "zvknha"
function clause hartSupports(Ext_Zvknha) = config extensions.Zvknha.supported
// NIST Suite: Vector SHA-2 Secure Hash (SHA-256 and SHA-512)
enum clause extension = Ext_Zvknhb
mapping clause extensionName = Ext_Zvknhb <-> "zvknhb"
function clause hartSupports(Ext_Zvknhb) = config extensions.Zvknhb.supported
// Vector Data Independent Execution Latency
enum clause extension = Ext_Zvkt
mapping clause extensionName = Ext_Zvkt <-> "zvkt"
function clause hartSupports(Ext_Zvkt) = config extensions.Zvkt.supported
function clause currentlyEnabled(Ext_Zvkt) = hartSupports(Ext_Zvkt)
// The following extensions are superset/shorthand extensions. They cannot be
// directly configured in the config file and are automatically supported when
// all their required subset extensions are supported.
enum clause extension = Ext_Zvkn
mapping clause extensionName = Ext_Zvkn <-> "zvkn"
function clause hartSupports(Ext_Zvkn) =
  hartSupports(Ext_Zvkned) &
  hartSupports(Ext_Zvknhb) &
  hartSupports(Ext_Zvkb)   &
  hartSupports(Ext_Zvkt)
function clause currentlyEnabled(Ext_Zvkn) = hartSupports(Ext_Zvkn)
// NIST Algorithm Suite with carryless multiply
enum clause extension = Ext_Zvknc
mapping clause extensionName = Ext_Zvknc <-> "zvknc"
function clause hartSupports(Ext_Zvknc) = hartSupports(Ext_Zvkn) & hartSupports(Ext_Zvbc)
function clause currentlyEnabled(Ext_Zvknc) = hartSupports(Ext_Zvknc)
// NIST Algorithm Suite with GCM
enum clause extension = Ext_Zvkng
mapping clause extensionName = Ext_Zvkng <-> "zvkng"
function clause hartSupports(Ext_Zvkng) = hartSupports(Ext_Zvkn) & hartSupports(Ext_Zvkg)
function clause currentlyEnabled(Ext_Zvkng) = hartSupports(Ext_Zvkng)

// The supervisor-level extensions are gone with supervisor mode
// (R-15-003) and the address-translation modes with the MMU
// (R-15-002, R-15-038): Ssccptr, Sscounterenw, Sstvala, Sstvecd,
// Ssu64xl, Svbare, Sv32/39/48/57, Svade, Svadu, Svnapot, Svpbmt,
// Svrsw60t59b and Svvptc all named a mode or a walker that no longer
// exists.

// When adding a new extension X, we need to make sure that if X being supported
// depends on Y being supported, then the value associated to X is _greater_ than
// the value associated to Y. The default value is 0.

function hartSupports_measure(ext : extension) -> int =
  match ext {
    Ext_Zvkn => 1, // > Zvkned

    Ext_Zvknc => 2, // > Zvkn
    Ext_Zvkng => 2, // > Zvkn

    _ => 0,
  }

termination_measure hartSupports(ext) = hartSupports_measure(ext)

// When adding a new extension X, we need to make sure that if X being enabled
// depends on Y being enabled, then the value associated to X is _greater_ than
// the value associated to Y. The default value is 2, so that if it does not
// depend on anything or only on extensions A, B, C, D, F, M, S, Zve32x, Zvl* or Zicsr,
// nothing needs to be done.

function currentlyEnabled_measure(ext : extension) -> int =
  match ext {
    Ext_A => 0,
    Ext_B => 0,
    Ext_M => 0,
    Ext_Zicsr => 0,
    Ext_Zvl128b => 0,
    Ext_Zvl32b => 0,
    Ext_Zvl64b => 0,

    Ext_Zaamo => 1, // > A
    Ext_Zve32x => 1, // > Zvl32b

    // Note: even though these match the default case, making them explicit to
    // annotate the chain of dependencies
    Ext_Zvbb => 2, // > Zve32x
    Ext_Zve32f => 2, // > Zve32x
    Ext_Zve64x => 2, // > Zve32x

    Ext_Zvbc => 3, // > Zve64x
    Ext_Zve64f => 3, // > Zve64x
    Ext_Zvfbfmin => 3, // > Zve32f
    Ext_Zvkb => 3, // > Zvbb
    Ext_Zvknhb => 3, // > Zve64x

    Ext_Zve64d => 4, // > Zve64f
    Ext_Zvfbfwma => 4, // > Zvfbfmin
    Ext_Zvfh => 4, // > Zve32f

    Ext_V => 5, // > Zve64d
    Ext_Zvfhmin => 5, // > Zvfh

    _ => 2
  }

termination_measure currentlyEnabled(ext) = currentlyEnabled_measure(ext)

let extensions_ordered_for_isa_string = [
  // Single letter extensions.
  Ext_M,
  Ext_A,
  // Ext_G,
  // Ext_Q,
  Ext_B,
  // Ext_P,
  Ext_V,

  // Z extensions, ordered by category and then alphabetically.
  // Zi
  Ext_Zic64b,
  Ext_Zicboz,
  Ext_Ziccamoa,
  Ext_Ziccif,
  Ext_Zicclsm,
  Ext_Zicond,
  Ext_Zicsr,

  // Zm
  Ext_Zmmul,

  // Za
  Ext_Zaamo,
  Ext_Zabha,
  Ext_Zama16b,

  // Zf, Zd, and Zq have no members: scalar floating point is excluded
  // entirely (R-15-039).

  // Zb
  Ext_Zba,
  Ext_Zbb,
  Ext_Zbc,
  Ext_Zbkb,
  Ext_Zbkc,
  Ext_Zbkx,
  Ext_Zbs,

  // Zk
  Ext_Zkt,

  // Zt
  Ext_Ztso,

  // Zvb
  Ext_Zvbb,
  Ext_Zvbc,

  // Zve
  Ext_Zve32f,
  Ext_Zve32x,
  Ext_Zve64d,
  Ext_Zve64f,
  Ext_Zve64x,

  // Zvfbf
  Ext_Zvfbfmin,
  Ext_Zvfbfwma,

  // Zvfh
  Ext_Zvfh,
  Ext_Zvfhmin,

  // Zvk
  Ext_Zvkb,
  Ext_Zvkg,
  Ext_Zvkn,
  Ext_Zvknc,
  Ext_Zvkned,
  Ext_Zvkng,
  Ext_Zvknha,
  Ext_Zvknhb,
  Ext_Zvkt,

  // Zvl
  Ext_Zvl32b,
  Ext_Zvl64b,
  Ext_Zvl128b,
  Ext_Zvl256b,
  Ext_Zvl512b,
  Ext_Zvl1024b,
  Ext_Zvl2048b,
  Ext_Zvl4096b,

  // Machine mode extensions, ordered alphabetically.
]
