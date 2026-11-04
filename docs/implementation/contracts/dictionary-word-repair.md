# Canonical instruction identity in dictionary measurements

This bounded repair belongs to M1.4′'s composer and M1.8b's measurement
instrument in [the plan](../../../PLAN.md). It implements the complete-word
dictionary identity required by the [instruction encoding](../../hardware/isa-profile.md#11-the-instruction-encoding)
and the [freeze measurement contract](freeze-measurement.md#4-the-emitter-provenance-schema).
Implementation starts after this contract is committed.

## Contract and acceptance

- Every assembler instruction site retains the exact unsigned canonical 32-bit
  word it emitted, including resolved registers, immediates and displacements.
  Expanded pseudo-instructions and executable alignment instructions carry the
  same word identity as the bytes written at their sites. Mnemonics remain
  descriptive metadata and never supply dictionary identity.
- The composer accepts a dictionary mapping canonical words to integer indices.
  Keys must be unsigned 32-bit integers. Indices must be distinct integers,
  contiguous from zero and representable at the selected slot width. Boolean,
  string, negative, oversized and ambiguous entries refuse before placement.
  The empty dictionary retains its all-escape behavior. No mnemonic-keyed
  compatibility path remains.
- A repeated exact word takes its one entry at every site. Changing a register
  or immediate takes an escape unless that changed word has its own entry.
  Focused controls compare site words against independently specified machine
  words and the actual assembled bytes, and exercise malformed dictionaries.
- Existing canonical ELF bytes, emitted file schemas and the default empty
  dictionary remain unchanged. This repair produces placement metadata; it
  implements neither encoded bundles nor a Sail/RTL decoder, and supplies no
  compressed-byte or profile-freeze verdict. The decoder's outstanding scope
  remains with [full profile curation](../../../PLAN.md#rtl-track).
- Local feedback uses `python tools/run.py prepare python` for the selected
  Python files and `python tools/run.py test --only compose`, with focused
  assembler controls where needed. The integrator records typecheck, corpus
  validation and the user-managed Host CI and Guest CI handoff. Passing local
  controls supplies no hosted acceptance verdict.
