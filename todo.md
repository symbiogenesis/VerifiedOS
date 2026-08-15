**Regarding memory constraints: The strongest option is a verified, restricted compressed-instruction profile.** RISC-V C does not inherently weaken CHERI, TAL, W^X, constant-time, or non-interference guarantees; it mainly enlarges the decoder and instruction-fetch proof.

### First: reduce duplication without changing the ISA

Static composition creates opportunities unavailable to conventional systems:

- Whole-system dead-code elimination
- Identical-function and constant folding
- Cross-compartment immutable-code sharing
- Function outlining and tail merging
- Link-time specialization
- One shared service compartment instead of statically linking a library into every application
- Removal of ELF, relocations, symbols, debug data, and unwind metadata from resident memory
- Keeping source closures and proof artifacts in authenticated storage rather than execution SRAM

Immutable executable objects can be mapped through capabilities into multiple compartments without VM or coherence. Each compartment still receives only its declared sentry entry capabilities.

This should happen before adding instruction compression.

### A verified restricted C profile

Rather than accepting the complete RISC-V C extension, define `VerifiedOS-C`: only compressed aliases of already-admitted instructions.

The proof structure would be:

$$
\operatorname{decode}_{C}(16\text{-bit instruction})
  = \text{canonical 32-bit instruction}
$$

CHERI-TAL checks the canonical instruction stream. The hardware proof establishes that executing each compressed encoding is observationally equivalent to executing its canonical instruction.

Exclude compressed forms that complicate assurance disproportionately, such as:

- Indirect control transfers
- Implicit link-register behavior
- Stack-pointer-relative operations, if they complicate capability bounds
- Encodings interacting poorly with CHERI capabilities
- Any instruction whose compressed form changes exception reporting

This preserves all enforcement after decoding. A compressed load still performs the same CHERI bounds, permission, initialization, and revocation checks as its 32-bit form.

### Keep fetch timing fixed

The principal concern is no longer instruction semantics but fetch alignment: a 32-bit instruction can straddle a fetch boundary.

A simple deterministic implementation could:

- Fetch a fixed 64- or 128-bit bundle every cycle
- Decode a fixed maximum number of 16/32-bit instructions
- Carry one bounded alignment fragment between bundles
- Charge every bundle the same fixed latency
- Reject instruction placement that crosses forbidden macro boundaries
- Pad bundles where necessary

There would be no instruction cache, predictor, decompression table, or data-dependent latency. The alignment buffer would be architecturally constrained fixed state, not a cache.

### An even simpler custom encoding

A bespoke dictionary format could be easier to verify than full RISC-V C:

- Each code block contains fixed-width indices into a hardware-fixed instruction dictionary.
- Escape entries carry uncommon full 32-bit instructions.
- Blocks decompress in a fixed number of cycles.
- The dictionary is immutable and part of the ISA specification.
- No adaptive compression, history, or runtime-populated table exists.

This could outperform C for the exact VerifiedOS instruction distribution, but it would create another custom ISA component. A restricted standard C profile is probably the better trust trade.

### Execute-in-place from dense MRAM

If SOT-MRAM is adopted, code need not consume SRAM at all:

- Put immutable executable code in MRAM.
- Keep stacks, heaps, IPC buffers, and mutable state in SRAM.
- Execute directly from fixed-latency MRAM banks.
- Give those banks execute and load authority but no store authority.
- Share one physical code image across compartments.

This preserves W^X more cleanly than decompressing code into writable SRAM. It also uses MRAM for its ideal workload: overwhelmingly read-only data with infrequent authenticated updates.

A particularly strong design would therefore use:

| Memory | Contents |
|---|---|
| SRAM | Registers, stacks, mutable objects, IPC, active scratchpads |
| MRAM | Immutable code, constants, schemas, model weights |
| External authenticated storage | Packages, sources, proofs, inactive generations |

### Static code overlays

For applications too large to remain resident, composition can generate fixed code overlays:

1. The schedule identifies the code required in each phase.
2. A dedicated loader fills an instruction bank before that phase.
3. Hardware verifies its hash and canonical compressed representation.
4. Software never receives store authority to the executable bank.
5. The bank is invalidated before reuse.

This is effectively a statically scheduled instruction store rather than a demand-filled cache. It preserves deterministic timing, but adds considerably more proof machinery than execute-in-place MRAM.

### Recommended order

1. Whole-system dead stripping and immutable-code deduplication.
2. Remove non-runtime package and proof material from SRAM.
3. Execute immutable code directly from MRAM.
4. Add a restricted, formally normalized C profile.
5. Use static overlays only if the first four are insufficient.

Omitting C entirely is probably a false economy. A restricted compressed decoder is a relatively small proof obligation compared with the SRAM capacity it can save, and none of VerifiedOS’s substantive security guarantees needs to be relaxed.

---
Would you like me to draft a VerifiedOS-C spec or estimate expected memory savings from compression?