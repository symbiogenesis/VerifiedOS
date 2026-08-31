// =======================================================================================
// This Sail RISC-V architecture model, comprising all files and
// directories except where otherwise noted is subject the BSD
// two-clause license in the LICENSE file.
//
// SPDX-License-Identifier: BSD-2-Clause
// =======================================================================================

// Generators for Device-Tree source corresponding to the model
// configuration.
// NOTE: These assume a valid model configuration.

// Generates the value for the "riscv,isa-base" property.
private function generate_isa_base() -> string = {
  "rv" ^ dec_str(xlen) ^ "i"
}

// Generates an ISA string in the appropriate format.

enum ISA_Format = {Canonical_Lowercase, DeviceTree_ISA_Extensions}

// Some notes from the "ISA Extension Naming Convections" section of
// the manual; some aspects do not apply to the
// DeviceTree_ISA_Extensions generator.
//
// * The first letter following the "Z" conventionally indicates the
//   most closely related alphabetical extension category,
//   IMAFDQLCBKJTPVH.  If multiple "Z" extensions are named, they
//   should be ordered first by category, then alphabetically within a
//   category: for example, "Zicsr_Zifencei_Ztso".
//
// * All multi-letter extensions, including those with the "Z" prefix, must be
//   separated from other multi-letter extensions by an underscore, e.g.,
//   "RV32IMACZicsr_Zifencei" (but see the next point).
//
// * An underscore between the single letter extensions and the first
//   multi-letter extension is optional, e.g., "RV32IMAC_Zicsr_Zifencei".
//   The canonical generator below includes it.
//
// * Standard supervisor-level extensions (prefixed with either 'Ss' or
//   'Sv') should be listed after standard unprivileged extensions, and
//   like other multi-letter extensions, must be separated from other
//   multi-letter extensions by an underscore. If multiple
//   supervisor-level extensions are listed, they should be ordered
//   alphabetically.
//
// * Standard machine-level extensions (prefixed with the letters "Sm")
//   should be listed after standard lesser-privileged extensions, and
//   like other multi-letter extensions, must be separated from other
//   multi-letter extensions by an underscore. If multiple
//   machine-level extensions are listed, they should be ordered
//   alphabetically.
//
// Once the Sail configuration supports extension version numbers, we could
// add them to the generated isa string.
//
// The device-tree specification for the ISA string is at:
// https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/Documentation/devicetree/bindings/riscv/extensions.yaml
//
// As the above document uses lower-case, the generator below does too.

private function ext_wrap(ext : extension, fmt : ISA_Format) -> string = {
  if not(hartSupports(ext)) then return "";
  let s = extensionName(ext);
  match fmt {
    Canonical_Lowercase =>
      // Single letter extensions are concatenated without a separator.
      if string_length(s) == 1 then s else "_" ^ s,
    DeviceTree_ISA_Extensions =>
      ", \"" ^ s ^ "\"",
  }
}

private function generate_isa_string(fmt : ISA_Format) -> string = {
  var isa_string : string = match fmt {
    Canonical_Lowercase => "rv" ^ dec_str(xlen) ^ "i",
    DeviceTree_ISA_Extensions => "\"i\"",
  };

  // The default Order dec means we start from the end
  foreach (i from (length(extensions_ordered_for_isa_string) - 1) downto 0)
    isa_string = isa_string ^ ext_wrap(extensions_ordered_for_isa_string[i], fmt);

  isa_string
}

// Generates the full Device-Tree configuration for the model.

// The latency class a region is placed on, as a property of the region's own
// node (core/memory_class.sail, R-15-247). It is emitted for every main-memory
// node and for none other, which the validator has already established, so a
// node without it in a generated tree is an IO region and not an unplaced array.
private function generate_dts_memory_class(pma : PMA_Region) -> string =
  match pma.attributes.memory_class {
    None()  => "",
    Some(c) => "    verifiedos,memory-class = \"" ^ memory_class_str(c) ^ "\";\n",
  }

// The datapath whose software-managed scratchpad a region is, as a property of
// the region's own node (sys/pma.sail, R-15-165, R-15-167). It is emitted for a
// scratchpad and for nothing else, so a node carrying it is a scratchpad and a
// node without it is main memory, which is the distinction the two properties
// make between them: `verifiedos,memory-class` is on every array and on no
// scratchpad, and this is on every scratchpad and on no array.
//
// **The base is here and not in the class node.** The class node already
// declares the size R-15-113 gives the class, and a class node carrying the base
// as well would be one attested artifact writing the placement twice. What the
// kernel needs is the link, and the link is this property: it reads its class
// out of `mhartid` against the roster and finds the memory node naming that
// class, which puts the decode beside the thing it decodes exactly as
// `verifiedos,class-index` does for the roster.
private function generate_dts_scratchpad(pma : PMA_Region) -> string =
  match pma.attributes.scratchpad {
    None()  => "",
    Some(c) => "    verifiedos,scratchpad = \"" ^ core_class_str(c) ^ "\";\n",
  }

private function generate_dts_memories(pmas : list(PMA_Region)) -> string =
  match pmas {
    [||] => "",
    pma :: rest => {
      if pma.include_in_device_tree then {
        let base_hi = unsigned(pma.base >> 32);
        let base_lo = unsigned(pma.base[31 .. 0]);
        let size_hi = unsigned(pma.size >> 32);
        let size_lo = unsigned(pma.size[31 .. 0]);

          "  memory@" ^ string_drop(hex_str(unsigned(pma.base)), 2) ^ " {\n"
        ^ "    device_type = \"memory\";\n"
        ^ "    reg = <" ^ hex_str(base_hi) ^ " " ^ hex_str(base_lo)
        ^ " " ^ hex_str(size_hi) ^ " " ^ hex_str(size_lo) ^ ">;\n"
        ^ generate_dts_memory_class(pma)
        ^ generate_dts_scratchpad(pma)
        ^ "  };\n"
        ^ generate_dts_memories(rest)
      } else generate_dts_memories(rest)
    }
  }

// A 64-bit constant as the two devicetree cells it takes. The retention corner
// is stated in microseconds and a minutes-to-hours spread does not fit in one
// cell (R-15-247m), and neither does a refresh sweep stated in cycles at a
// gigahertz spine, so the pair is written out here rather than truncated at the
// point of use, the same way every `reg` above is written.
private function generate_dts_u64(value : int) -> string = {
  let bits64 : bits(64) = to_bits_truncate(64, value);
  hex_str(unsigned(bits64 >> 32)) ^ " " ^ hex_str(unsigned(bits64[31 .. 0]))
}

// The per-class constants R-15-247m measures, in the attested devicetree that
// requirement puts them in.
//
// `verifiedos,qualified` is the load-bearing property of this node and not a
// footnote on it. R-15-247m admits no density figure as an architectural input
// ahead of the measurement, and a tree carrying provisional numbers with nothing
// separating them from measured ones is exactly how a placeholder becomes one.
// So the qualification state is attested beside the constants, and every tree
// this repository generates today says `<0>`.
private function generate_dts_memory_class_node(c : MemoryClass) -> string = {
  let k = memory_class_constants(c);
    "    class-" ^ memory_class_str(c) ^ " {\n"
  ^ "      verifiedos,qualified = <" ^ (if k.qualified then "1" else "0") ^ ">;\n"
  ^ "      verifiedos,usable-density-mbit-per-mm2 = <" ^ dec_str(k.usable_density_mbit_per_mm2) ^ ">;\n"
  ^ "      verifiedos,banks = <" ^ dec_str(k.banks) ^ ">;\n"
  ^ "      verifiedos,retention-floor-us = <" ^ generate_dts_u64(k.retention_floor_us) ^ ">;\n"
  ^ "      verifiedos,retention-ceiling-us = <" ^ generate_dts_u64(k.retention_ceiling_us) ^ ">;\n"
  ^ "      verifiedos,read-cycles = <" ^ dec_str(k.read_cycles) ^ ">;\n"
  ^ "      verifiedos,write-cycles = <" ^ dec_str(k.write_cycles) ^ ">;\n"
  ^ "      verifiedos,refresh-cycles = <" ^ dec_str(k.refresh_cycles) ^ ">;\n"
  ^ "      verifiedos,discharge-cycles = <" ^ dec_str(k.discharge_cycles) ^ ">;\n"
  ^ "    };\n"
}

// The node carries no `#address-cells`/`#size-cells` pair, which `dtc` would
// call unnecessary and is: its children are constants and not address ranges,
// so neither child has a `reg` for those cells to describe.
private function generate_dts_memory_classes() -> string =
    "  memory-classes {\n"
  ^ generate_dts_memory_class_node(FirstClass)
  ^ generate_dts_memory_class_node(SecondClass)
  ^ "  };\n"

// The core-class table, in the attested devicetree R-09-007 puts it in: a static
// devicetree declares core classes and islands, there being no UEFI, no ACPI,
// and nothing to discover them from.
//
// `verifiedos,frozen` is the load-bearing property here for the reason
// `verifiedos,qualified` is in the memory-class node above. R-15-113's figures
// are a reference instantiation and R-15-108's exploration is what selects them;
// a tree carrying them with nothing separating them from selected values is how
// a placeholder becomes an architectural input. Every tree this repository
// generates today says `<0>`.
//
// `verifiedos,class-index` is what decodes the roster property below, so the
// mapping travels with the thing it decodes rather than living in a comment
// somebody has to find (core/core_class.sail).
private function generate_dts_core_class_node(c : CoreClass) -> string = {
  let d = core_class_datapath(c);
    "    class-" ^ core_class_str(c) ^ " {\n"
  ^ "      verifiedos,class-index = <" ^ dec_str(core_class_to_index(c)) ^ ">;\n"
  ^ "      verifiedos,frozen = <" ^ (if d.frozen then "1" else "0") ^ ">;\n"
  ^ "      verifiedos,vlen-exp = <" ^ dec_str(d.vlen_exp) ^ ">;\n"
  ^ "      verifiedos,elen-exp = <" ^ dec_str(d.elen_exp) ^ ">;\n"
  ^ "      verifiedos,lanes = <" ^ dec_str(d.lanes) ^ ">;\n"
  ^ "      verifiedos,matrix-int8-dim = <" ^ dec_str(d.matrix_int8_dim) ^ ">;\n"
  ^ "      verifiedos,matrix-bf16-dim = <" ^ dec_str(d.matrix_bf16_dim) ^ ">;\n"
  ^ "      verifiedos,scratchpad-bytes = <" ^ generate_dts_u64(d.scratchpad_bytes) ^ ">;\n"
  ^ "      verifiedos,issue-width = <" ^ dec_str(d.issue_width) ^ ">;\n"
  ^ "      verifiedos,pipeline-depth = <" ^ dec_str(d.pipeline_depth) ^ ">;\n"
  ^ "      verifiedos,keccak-unit = <" ^ (if d.keccak_unit then "1" else "0") ^ ">;\n"
  // The FEC decoders' realization geometry, which is a datapath figure of this
  // class exactly as the matrix dimensions and the scratchpad size above are, so
  // it lands here for the same reason (R-15-119a, R-09-007). The channel codes
  // themselves are **not** here and their absence is the point: a code set is a
  // selector into TS 38.212 that the composition declares and the validator
  // refuses a wrong one, and R-09-007's enumeration of what this tree carries
  // names core classes, islands, the NoC schedule, OPP tables, and radio
  // calibration and limit values, none of which a code set is.
  ^ "      verifiedos,fec-parallelism = <" ^ dec_str(d.fec_parallelism) ^ ">;\n"
  ^ "      verifiedos,fec-max-block = <" ^ dec_str(d.fec_max_block) ^ ">;\n"
  ^ "      verifiedos,fec-iterations = <" ^ dec_str(d.fec_iterations) ^ ">;\n"
  ^ "      verifiedos,fec-polar-list = <" ^ dec_str(d.fec_polar_list) ^ ">;\n"
  ^ "      verifiedos,replicated = <" ^ (if d.replicated then "1" else "0") ^ ">;\n"
  ^ "    };\n"
}
// No count is emitted here. The roster is in the same tree, three properties up,
// and a class's count is the number of its entries (R-15-113), so a count beside
// it would be the same fact written twice in one document, which is the defect
// this repository is built to catch rather than one to commit in its own
// attested artifact. A reader wanting the count counts the roster, exactly as
// `core_class_count` does.

private function generate_dts_core_classes() -> string =
    "  core-classes {\n"
  ^ generate_dts_core_class_node(CoreClass_C)
  ^ generate_dts_core_class_node(CoreClass_V)
  ^ generate_dts_core_class_node(CoreClass_M)
  ^ generate_dts_core_class_node(CoreClass_S)
  ^ generate_dts_core_class_node(CoreClass_RoT)
  ^ "  };\n"

// The roster, as one flat cell array of `<hartid class-index island flags>`
// quads rather than as sixteen `cpu` nodes.
//
// The shape is forced twice over. A devicetree property carries cells or a
// string and not both, so the class column is the index the node above emits;
// and this tree is written into a 4 KiB ROM region, where a `cpu` node per hart
// carrying an ISA string would not fit. A `cpu` node also asserts a hart this
// emulator runs, and it runs one (R-15-005: one model, one build, one hart), so
// sixteen of them would describe cores that are not here. What the roster is
// instead is the table `mhartid` indexes: the kernel selects its per-hart state,
// the core's class, and the island binding out of it at boot (R-15-052b), and
// one binary does that unmodified on every class (R-07-012).
//
// `flags` is bit 0 pinned (R-15-114) and bit 1 FEC units (R-15-119).
// The chunks are comma-separated because a devicetree source says so: juxtaposed
// cell arrays are not a concatenation in that grammar, they are a syntax error,
// which `dtc` is what says so about.
private function generate_dts_roster_entries(roster : list(CoreRosterEntry), first : bool) -> string =
  match roster {
    [||]          => "",
    entry :: rest =>
        (if first then " " else ", ")
      ^ "<" ^ dec_str(entry.hartid)
      ^ " " ^ dec_str(core_class_to_index(entry.class))
      ^ " " ^ dec_str(entry.island)
      ^ " " ^ dec_str((if entry.pinned then 1 else 0) + (if entry.fec_units then 2 else 0))
      ^ ">"
      ^ generate_dts_roster_entries(rest, false)
  }

private function generate_dts_core_roster() -> string =
  "    verifiedos,core-roster =" ^ generate_dts_roster_entries(core_roster, true) ^ ";\n"

// The class and island of the hart this tree is for, on its own node. The
// roster above carries the whole die's binding; these two say which row is this
// core's, so a kernel that has not walked the roster yet still knows what it is
// running on.
private function generate_dts_this_core() -> string =
  match this_core_entry() {
    None()      => "",
    Some(entry) =>
        "      verifiedos,core-class = \"" ^ core_class_str(entry.class) ^ "\";\n"
      ^ "      verifiedos,island = <" ^ dec_str(entry.island) ^ ">;\n"
  }

// Generates a `riscv,<prefix>-block-size` property line if the corresponding
// cache-block extension is supported. The size is 2^plat_cache_block_size_exp
// bytes, the same value used by the Zicboz instruction semantics.
private function generate_cbo_block_size(prefix : string, ext : extension) -> string = {
  if hartSupports(ext)
  then "      riscv," ^ prefix ^ "-block-size = <" ^ dec_str(2 ^ plat_cache_block_size_exp) ^ ">;\n"
  else ""
}

// The four cells a `reg` takes under `soc`, whose `#address-cells` and
// `#size-cells` are both two. Every device node below carries the window its
// aperture declares and carries it in these four cells, so the spelling is one
// function rather than one per node: the placement R-15-002b makes a stated
// constraint on this tree is stated the same way wherever it is stated, and a
// node that has stopped stating it is a call that is missing rather than four
// lines that read almost like the four above them.
private function generate_dts_reg(base : physaddrbits, size : physaddrbits) -> string =
    "      reg = <" ^ hex_str(unsigned(base >> 32))
  ^ " " ^ hex_str(unsigned(base[31 .. 0]))
  ^ " " ^ hex_str(unsigned(size >> 32))
  ^ " " ^ hex_str(unsigned(size[31 .. 0])) ^ ">;\n"

// The machine-level interrupt file's window (R-15-064, R-15-065).
//
// **The `compatible` is this platform's own and not `riscv,imsics`.** What is
// here is the pending array and the sender's write-only doorbell; the
// supervisor and guest/VS files, the delivery-enable, threshold and
// top-pending-selection machinery, and the whole indirect interface are
// excluded (isa-profile.md §5.2), so the standard binding would name a device
// this die does not have. The identity count is not emitted: it is the width of
// the array's own register rather than a composition parameter, and a tree
// stating it would be reading the model's geometry out of an attested artifact
// (sys/platform.sail).
private function generate_dts_imsic() -> string =
  if not(plat_have_imsic) then ""
  else
    "    imsic@" ^ string_drop(hex_str(unsigned(plat_imsic_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,imsic\";\n"
  ^ generate_dts_reg(plat_imsic_base, plat_imsic_size)
  ^ "    };\n"

// The revocation sidecar's window (R-08-005a).
//
// **The window's size is the model's and the interval is the composition's**,
// which is why the two arrive here by different routes: the bitmap's width is
// fixed by the plane it covers (core/revocation.sail) and there is no key for
// it, while the revocable interval is declared. Both are here because
// core/platform_config.sail already calls the interval map and the window
// *attested-devicetree constants* and neither was in this tree; the kernel
// revocation path is the reader, and it needs the interval to know which
// addresses the plane answers about.
private function generate_dts_revocation() -> string =
  if not(plat_have_revocation) then ""
  else
    "    revocation@" ^ string_drop(hex_str(unsigned(plat_revocation_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,revocation\";\n"
  ^ generate_dts_reg(plat_revocation_base, to_bits(physaddrbits_len, revocation_bitmap_bytes))
  ^ "      verifiedos,interval-base = <" ^ generate_dts_u64(unsigned(plat_revocation_interval_base)) ^ ">;\n"
  ^ "      verifiedos,interval-size = <" ^ generate_dts_u64(unsigned(plat_revocation_interval_size)) ^ ">;\n"
  ^ "    };\n"

// The three devices beside the core (R1c-i): the SoC boot ROM, the serial port
// and the block device.
//
// **Each node is a placement and carries nothing else, because a placement is
// all the composition declares.** No register entry gives a serial port or a
// block device a register interface, so there is no baud rate, no FIFO depth,
// no block size and no capacity to attest, and a node inventing one would put an
// architectural input into the artifact a relying party appraises the part from.
// What each does carry is the `reg` R-15-002b asks of it, so the SoC top written
// over this map has a map to be written over (R1c-ii) and an auditor reading the
// tree finds the aperture rather than an address nothing accounts for.
//
// The boot ROM's node is the one that is not in the MMIO region: it is the upper
// half of the ROM region the attested tree is itself written into, and its
// extent exists so that the two do not share a base (postlude/validate_config.sail).
private function generate_dts_boot_rom() -> string =
  if not(plat_have_boot_rom) then ""
  else
    "    boot-rom@" ^ string_drop(hex_str(unsigned(plat_boot_rom_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,boot-rom\";\n"
  ^ generate_dts_reg(plat_boot_rom_base, plat_boot_rom_size)
  ^ "    };\n"

private function generate_dts_uart() -> string =
  if not(plat_have_uart) then ""
  else
    "    serial@" ^ string_drop(hex_str(unsigned(plat_uart_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,uart\";\n"
  ^ generate_dts_reg(plat_uart_base, plat_uart_size)
  ^ "    };\n"

private function generate_dts_blkdev() -> string =
  if not(plat_have_blkdev) then ""
  else
    "    block@" ^ string_drop(hex_str(unsigned(plat_blkdev_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,block-device\";\n"
  ^ generate_dts_reg(plat_blkdev_base, plat_blkdev_size)
  ^ "    };\n"

// The refresh and discharge sequencer's node (R-15-247h). Two things belong in
// an attested tree and both are here: the register slave's window, so a reader
// knows where the door is that no requester may open (sys/platform.sail), and
// the cadence table it runs, which is the schedule R-15-198's sequence table
// steps through and R-15-247g fixes at composition.
//
// The derived figures are emitted beside the declared ones deliberately. The
// sweep and the mode-transition dwell are what the attestation is *about*, a
// tree carrying only the per-phase interval would leave every reader to
// recompute them, and computing them here at emission is what stops the two
// from ever disagreeing (sys/memory_sequencer.sail).
private function generate_dts_memory_sequencer() -> string =
  if not(plat_have_memory_sequencer) then ""
  else
    "    memory-sequencer@" ^ string_drop(hex_str(unsigned(plat_memory_sequencer_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,memory-sequencer\";\n"
  ^ generate_dts_reg(plat_memory_sequencer_base, plat_memory_sequencer_size)
  ^ "      verifiedos,banks = <" ^ dec_str(memory_sequencer_banks()) ^ ">;\n"
  ^ "      verifiedos,banks-per-refresh-phase = <" ^ dec_str(plat_memory_sequencer_refresh_banks_per_phase) ^ ">;\n"
  ^ "      verifiedos,refresh-phase-cycles = <" ^ dec_str(plat_memory_sequencer_refresh_phase_cycles) ^ ">;\n"
  ^ "      verifiedos,refresh-phases = <" ^ dec_str(memory_sequencer_refresh_phases()) ^ ">;\n"
  ^ "      verifiedos,refresh-period-cycles = <" ^ generate_dts_u64(memory_sequencer_refresh_period_cycles()) ^ ">;\n"
  ^ "      verifiedos,banks-per-discharge-phase = <" ^ dec_str(plat_memory_sequencer_discharge_banks_per_phase) ^ ">;\n"
  ^ "      verifiedos,discharge-phase-cycles = <" ^ dec_str(plat_memory_sequencer_discharge_phase_cycles) ^ ">;\n"
  ^ "      verifiedos,discharge-phases = <" ^ dec_str(memory_sequencer_discharge_phases()) ^ ">;\n"
  ^ "      verifiedos,mode-exit-cycles = <" ^ generate_dts_u64(memory_sequencer_mode_exit_cycles()) ^ ">;\n"
  ^ "    };\n"

// The Root of Trust's four peripherals (R-09-001, sys/rot.sail).
//
// **What puts a device window in this tree is R-15-002b and not R-09-007.** That
// entry's enumeration of what the static devicetree declares names core classes,
// islands, the NoC schedule, OPP tables, and radio calibration and limit values,
// and a device window is none of the five; R-15-002b makes every MMIO aperture's
// placement *a stated constraint on the attested devicetree*, which is the
// sentence a `reg` here answers to, and the memory sequencer's node already
// rides its own requirement rather than the enumeration (R-15-247h). Each node
// below therefore carries its window under R-15-002b and its constants under the
// entry that fixes them, and none of them widens R-09-007's list.
//
// **The emulation seed is not here and its absence is the requirement.** Every
// draw from the single entropy root is secret nondeterminism, which R-16-017
// records as a sealed commitment and never as a value, and an attested
// devicetree is exactly the artifact designed to leave the device that its
// criterion names. What the tree carries is the source count and the sample
// budget, which are facts about the root's construction; the seed is an emulation
// fact and a real part has none (sys/rot.sail).
private function generate_dts_otp() -> string =
  if not(plat_have_otp) then ""
  else
    "    otp@" ^ string_drop(hex_str(unsigned(plat_otp_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,otp\";\n"
  ^ generate_dts_reg(plat_otp_base, plat_otp_size)
  // The lifecycle state, which R-09-037 has the RoT extend into the measured
  // chain as its first extension and the reference integrity manifest carry the
  // production value of. The enumeration's size and the relation's arity travel
  // with it, so a reader of the tree knows how many states there are and how
  // many edges join them without reading the model (R-09-032).
  ^ "      verifiedos,lifecycle-state = \"" ^ lifecycle_state_str(otp_lifecycle) ^ "\";\n"
  ^ "      verifiedos,lifecycle-states = <" ^ dec_str(lifecycle_state_count) ^ ">;\n"
  ^ "      verifiedos,lifecycle-edges = <" ^ dec_str(lifecycle_edge_count()) ^ ">;\n"
  // R-15-078's gate, in the attested artifact a relying party appraises the part
  // from: *no DM transaction reaches the fabric in the production state*.
  ^ "      verifiedos,debug-module-gated = <" ^ (if debug_module_fabric_gated() then "1" else "0") ^ ">;\n"
  ^ "      verifiedos,fuse-words = <" ^ dec_str(otp_fuse_words) ^ ">;\n"
  ^ "    };\n"

private function generate_dts_trng() -> string =
  if not(plat_have_trng) then ""
  else
    "    trng@" ^ string_drop(hex_str(unsigned(plat_trng_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,entropy-root\";\n"
  ^ generate_dts_reg(plat_trng_base, plat_trng_size)
  // The two figures R-15-241e and R-15-241b make properties of the root's
  // construction: how many attributed sources reach the one conditioner, and
  // over how many samples the start-up health tests run. The conditioner count
  // is written out rather than left implicit because *the one conditioner* is
  // the half of R-15-241e a reader would otherwise have to infer from its
  // absence.
  ^ "      verifiedos,noise-sources = <" ^ dec_str(plat_rot_noise_sources) ^ ">;\n"
  ^ "      verifiedos,conditioners = <1>;\n"
  ^ "      verifiedos,startup-samples = <" ^ dec_str(plat_rot_startup_samples) ^ ">;\n"
  ^ "    };\n"

private function generate_dts_monotonic() -> string =
  if not(plat_have_monotonic) then ""
  else
    "    monotonic-counters@" ^ string_drop(hex_str(unsigned(plat_monotonic_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,monotonic-counters\";\n"
  ^ generate_dts_reg(plat_monotonic_base, plat_monotonic_size)
  // The arity and nothing else. R-10-013's enumeration is closed by conferral
  // and its four members are named in the model (sys/rot.sail); a tree
  // repeating their names would be the enumeration written twice inside one
  // attested artifact, which is what the roster's own count is kept out of the
  // core-class nodes for.
  ^ "      verifiedos,counters = <" ^ dec_str(monotonic_counter_count) ^ ">;\n"
  ^ "    };\n"

private function generate_dts_watchdog() -> string =
  if not(plat_have_watchdog) then ""
  else
    "    watchdog@" ^ string_drop(hex_str(unsigned(plat_watchdog_base)), 2) ^ " {\n"
  ^ "      compatible = \"verifiedos,watchdog\";\n"
  ^ generate_dts_reg(plat_watchdog_base, plat_watchdog_size)
  // The two bounds, in the watchdog's own slow-clock ticks. **No ratio to the
  // spine is emitted and none exists**: R-15-196 makes the RoT's independent
  // slow clock one of exactly three genuinely asynchronous boundaries, none
  // modeled as fixed-latency, so a `clock-frequency` or a divisor here would
  // attest a crossing this platform states one-sided bounds over instead
  // (R-15-240, R-11-017).
  ^ "      verifiedos,early-ticks = <" ^ generate_dts_u64(plat_rot_watchdog_early) ^ ">;\n"
  ^ "      verifiedos,late-ticks = <" ^ generate_dts_u64(plat_rot_watchdog_late) ^ ">;\n"
  ^ "    };\n"

function generate_dts() -> string = {
  let clock_freq : nat = plat_clock_frequency;

  // `hex_str` is used for the unit-addresses of the `memory@` and `clint@` nodes
  // instead of `hex_bits_str` since they cannot have leading zeros.  These addresses
  // also cannot have a '0x' prefix which explains the `string_drop(., 2)`.

  "/dts-v1/;\n"
^ "\n"
^ "/ {\n"
^ "  #address-cells = <2>;\n"
^ "  #size-cells = <2>;\n"
^ "  compatible = \"ucbbar,spike-bare-dev\";\n"
^ "  model = \"ucbbar,spike-bare\";\n"
^ "  chosen {\n"
^ "    bootargs = \"console=hvc0 earlycon=sbi\";\n"
^ "  };\n"
^ "  cpus {\n"
^ "    #address-cells = <1>;\n"
^ "    #size-cells = <0>;\n"
^ "    timebase-frequency = <" ^ dec_str(clock_freq / plat_insns_per_tick) ^ ">;\n"
         // Before the `cpu` node rather than after it, because a devicetree
         // source puts every property of a node ahead of its subnodes and `dtc`
         // refuses the other order outright.
^ generate_dts_core_roster()
         // The node name and `reg` follow `mhartid` rather than being written
         // as zero. The identity is a composition constant fixed by the roster
         // (R-15-052b), so a tree hardwiring it would describe hart zero to a
         // machine that is some other hart. The label stays `CPU0` because it is
         // a DTS label rather than an identity and `&CPU0_intc` below names it.
^ "    CPU0: cpu@" ^ string_drop(hex_str(plat_hartid), 2) ^ " {\n"
^ "      device_type = \"cpu\";\n"
^ "      reg = <" ^ dec_str(plat_hartid) ^ ">;\n"
^ "      status = \"okay\";\n"
^ "      compatible = \"riscv\";\n"
^ "      riscv,isa-base = \"" ^ generate_isa_base() ^ "\";\n"
         // NOTE: The "riscv,isa" property is marked deprecated but is
         // probably still widely used.
^ "      riscv,isa = \"" ^ generate_isa_string(Canonical_Lowercase) ^ "\";\n"
^ "      riscv,isa-extensions = " ^ generate_isa_string(DeviceTree_ISA_Extensions) ^ ";\n"
         // There is no MMU, so no `mmu-type` property is emitted: the
         // device-tree binding treats its absence as "none".
^ generate_cbo_block_size("cboz", Ext_Zicboz)
^ generate_dts_this_core()
^ "      clock-frequency = <" ^ dec_str(clock_freq) ^ ">;\n"
^ "      CPU0_intc: interrupt-controller {\n"
^ "        #address-cells = <2>;\n"
^ "        #interrupt-cells = <1>;\n"
^ "        interrupt-controller;\n"
^ "        compatible = \"riscv,cpu-intc\";\n"
^ "      };\n"
^ "    };\n"
^ "  };\n"
^ generate_dts_core_classes()
^ generate_dts_memories(pma_regions)
^ generate_dts_memory_classes()

^ "  soc {\n"
^ "    #address-cells = <2>;\n"
^ "    #size-cells = <2>;\n"
^ "    compatible = \"ucbbar,spike-bare-soc\", \"simple-bus\";\n"
^ "    ranges;\n"
         // In address order, and every declared aperture is here: R-15-002b
         // makes the placement of each a stated constraint on this tree, so a
         // window declared in the composition with no node below it is an
         // aperture this artifact does not state (K-94).
^ generate_dts_boot_rom()
^ "    clint@" ^ string_drop(hex_str(unsigned(plat_clint_base)), 2) ^ " {\n"
^ "      compatible = \"riscv,clint0\";\n"
^ "      interrupts-extended = <&CPU0_intc 3 &CPU0_intc 7>;\n"
^ generate_dts_reg(plat_clint_base, plat_clint_size)
^ "    };\n"
^ generate_dts_imsic()
^ generate_dts_revocation()
^ generate_dts_memory_sequencer()
^ generate_dts_otp()
^ generate_dts_trng()
^ generate_dts_monotonic()
^ generate_dts_watchdog()
^ generate_dts_uart()
^ generate_dts_blkdev()
^ "  };\n"
^ "  htif {\n"
^ "    compatible = \"ucb,htif0\";\n"
^ "  };\n"
^ "};\n"
}

// Generate a canonical ISA string for the configuration.
function generate_canonical_isa_string() -> string =
  generate_isa_string(Canonical_Lowercase)
