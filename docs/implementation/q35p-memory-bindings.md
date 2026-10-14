# Canonical memory and tag binding qualification

Q35p remains open. The [retained refusal](retained-evidence/close3-q35p-20261013/refusal.json) identifies a missing granule-keyed tag operation in the canonical concurrency outcome interface. No model primitive, support definition, statement, assumption, compiler flag or lock changed.

The trial reads base `bd5e0b024d1b3f80139f9b513b55f6664e17466c` in its dedicated memory lane. Its [manifest](retained-evidence/close3-q35p-20261013/manifest.json) binds the reproducer, emitted readings, diagnostics, input identities and license notices. The recorded Sail journal ran from `2026-10-14T03:37:47.936968Z` to `2026-10-14T03:45:21.885040Z`, with 435.1 active seconds against twelve candidate checks or thirty minutes. Five small harness checks establish the correct outcome instantiations; two expose missing standard-prelude scaffolding, two successful emissions use the prompt interface, and the fifth emits the canonical concurrency interface. No source adapter candidate was checked or adopted. The first unsupported semantic boundary ends this trial before the numeric budget.

## Seven binding readings

The [small Sail reproducer](retained-evidence/close3-q35p-20261013/bindings.sail.txt) contains the exact two model owners and their existing error definitions, with an explicit prelude and address-width scaffold. Its [main output](retained-evidence/close3-q35p-20261013/bindings.v.txt) and [types output](retained-evidence/close3-q35p-20261013/bindings_types.v.txt) retain the locked Sail's bytes. Here `M` is `ConcurrencyInterface.Defs.monad exception`, the instruction outcome monad; it is neither the prompt monad nor the sequential state monad.

| Binding | Existing Sail/emulator result and caller | Emitted reading |
| --- | --- | --- |
| `read_mem#` | Polymorphic request token, 32/64-bit address and nonnegative byte count to data bits; the emulator's ordinary `sail_mem_read` branch calls it | `read_mem_ : ... -> M (mword (8 * n))`; its Q35f body calls the existing `internal_error` |
| `read_mem_ifetch#` | Same result, selected by the emulator's instruction-fetch branch | `read_mem_ifetch_ : ... -> M (mword (8 * n))`; same refusal body |
| `read_mem_exclusive#` | Same result, selected by the emulator's exclusive-read branch | `read_mem_exclusive_ : ... -> M (mword (8 * n))`; same refusal body |
| `write_mem#` | Request token, address, positive byte count and data to success `bool`; ordinary emulator write branch | `write_mem_ : ... -> M bool`; same refusal body |
| `write_mem_exclusive#` | Same result, exclusive emulator write branch | `write_mem_exclusive_ : ... -> M bool`; same refusal body |
| `__read_tag` | Impure `bits(64) -> bool`, bound to `read_tag_bool`; `__ReadRAM_Meta` passes the zero-extended granule index | Its call remains `read_tag_bool ... : M bool`; no standalone tag-read binding has been qualified for this outcome monad |
| `__write_tag` | Impure `(bits(64), bool) -> unit`, bound to `write_tag_bool`; `__WriteRAM_Meta` visits every granule from first to last | The loop requires `M unit`, while the resolved support primitive has `Prompt_monad.monad bool` |

The [emulator read branches](retained-evidence/close3-q35p-20261013/emulator-outcome-callers.txt) and [write branches](retained-evidence/close3-q35p-20261013/emulator-write-callers.txt) identify the five low-level callers. The canonical term reaches data memory through its emitted outcomes, preserving Q35f's existing refusal bodies rather than converting those bodies to memory implementations. `write_ram` retains the successful-data-write-before-metadata order, and the metadata loop retains every overwritten granule and the model's existing width and address behavior.

## Actual semantic boundary

The [native compile record](retained-evidence/close3-q35p-20261013/compile.json) binds its exact mappings and commands against a private copy of the paired Q35n support. The emitted types exit 0; the main exits 1 at the [original tag-write mismatch](retained-evidence/close3-q35p-20261013/bindings.compile.log). This diagnostic reproduction uses the original diagnostic settings and supplies no strict compile acceptance.

The [outcome algebra](retained-evidence/close3-q35p-20261013/outcome-algebra.txt) carries tags within `MemRead` and `MemWrite` data requests, whose addresses name data bytes. It has no standalone granule-keyed tag-read or tag-write constructor. `Defs.monad E` uses `Interface.iMon (fun _ => E)`: [its exact definition](retained-evidence/close3-q35p-20261013/outcome-bindings.txt) shows that extra outcomes carry the model's existing exception type. Giving an exception new tag-plane meaning would require another semantic delivery.

The [data outcome binding](retained-evidence/close3-q35p-20261013/data-outcomes.txt) returns `Ret (Ok None)` when a write request has `value = None`; that path performs no tag write. Replacing the model's metadata write by such a request would silently remove its effect. Supplying a dummy data value would instead add a data write. Neither preserves the model's backing tag plane or the post-success metadata order.

The paired library's [state primitives](retained-evidence/close3-q35p-20261013/state-tags.txt) read an unshifted key with default `false` and write that key before returning `true`. The [emulator runtime](retained-evidence/close3-q35p-20261013/runtime-tags.txt) also reads the exact supplied key with default `false` and returns unit after a tag write. Discarding the state's always-true result preserves that state's tag effect, but supplies no conversion into the canonical outcome monad. The source reading therefore does not qualify a target adapter. The raw journal's completion note describes extra outcomes as empty; the refusal record corrects that shorthand against the exact native definition without altering the journal.

## Preserved inputs and next owner act

The [input identity record](retained-evidence/close3-q35p-20261013/inputs.json) matches both model owners, the error definitions, frozen profile, target and support qualification to their initial bytes. The [non-Rocq record](retained-evidence/close3-q35p-20261013/non-rocq.json) binds a successful complete baseline C++ emission and its outputs. No model source changed, so this is evidence of the preserved source surface and a single baseline emission; it claims no paired regeneration comparison.

The next owner must qualify a standalone granule-keyed tag read/write outcome, or an explicit semantics-preserving adapter into the existing outcome algebra. Agreement must cover the raw granule index, default-false absent tags, every overwritten-granule clear, metadata only after a successful data write and all existing refusals. No new assumption, weaker definition, discarded tag effect or dummy data write supplies that agreement. The owner must then join Q35o's syntax and actual-plugin identity checks, Q35b's strict whole-term compile, exact closure and compiled size, and the unchanged production-carriage predicate. This refusal authorizes no proof-switch change.
