# The checker's "Incompatible resolver roots" anomaly

Q35h's standalone reproduction of F-486. `rocqchk`, the Rocq kernel checker, aborts with
the anomaly `Incompatible resolver roots: <application path> is not a subpath of
<functor path>` on a functor whose body opaquely ascribes a module that holds a
submodule, once the functor is applied. The compiler, `rocq c`, accepts every file here.
The anomaly is raised by `add_delta_resolver` in the kernel's `mod_subst.ml`, a root
check PR #20124 added on 2025-01-27 and every release from 9.1 carries. VST 2.17's
`floyd/SeparationLogicAsLogicSoundness.v` has this shape, which is how the proof gate
met it. [The record](../../../docs/assurance/checker-resolver-anomaly.md) holds the
reduction, the readings of released checkers and of rocq master, which gives the 9.3.0
column's results at `981bb63f`, and the upstream state; the report is
[rocq-prover/rocq#22555](https://github.com/rocq-prover/rocq/issues/22555). This
directory holds the files and the runner.

[Upstream fixed #22555 in #22556](https://github.com/rocq-prover/rocq/pull/22556) on 2026-10-08; as of 2026-10-10 no release carries the fix, so the locked 9.3.0 checker remains affected and VST requalification remains pending. The table and runner retain their expectations for the measured releases; a run with a fixed checker is a new measurement, including the related `AliasTypedField.v` symptom.

Every file is authored here from scratch and carries none of VST's content.

| File | What it holds | `rocq c` | `rocqchk -silent -o` at 9.1.1, 9.2.0 and 9.3.0 |
| --- | --- | --- | --- |
| `Minimal.v` | the trigger alone: empty module types, a functor sealing a module that holds an empty submodule, one application | accepts | exit 129, `Incompatible resolver roots: Repro.Minimal.R.M.N is not a subpath of Repro.Minimal.F.M.N` |
| `MinimalTransparent.v` | `Minimal.v` with `<:` for `:` | accepts | exit 0, summary written |
| `VstShape.v` | VST's shape and names: a functor sealing `CConseq` against a `with Module CSHL_Def := Def` signature, the sealed body aliasing the parameter, applied inside a second functor's body | accepts | exit 129, the message naming `…DeepEmbeddedSoundness.DeepEmbedded.CConseq.CSHL_Def` and `…DeepEmbedded.CConseq.CSHL_Def` |
| `VstShapeTransparent.v` | `VstShape.v` with `<:` for `:` | accepts | exit 0, summary written |
| `SealedNoSubmodule.v` | `VstShape.v` with the sealed module holding a constant and no submodule | accepts | exit 0, summary written |
| `AliasTypedField.v` | `VstShape.v` with one constant in the sealed module typed through its own alias field | accepts | exit 129: the resolver-roots message at 9.1.1, `Type error: IllFormedConstant` at 9.2.0 and 9.3.0 |

The record's reduction table says which other constructs were tried and found
inessential: the second file, the outer functor, the alias, the `with Module` clause,
the constant and the sibling module each leave the anomaly in place, and the seal, the
submodule under it, its position inside a functor body and the functor's application
each remove it.

## Running

In the WSL guest, with the switch's name and an output directory on the guest's own
filesystem:

```
bash tools/checker-reproductions/resolver-roots/run.sh verifiedos-rocq-9.3.0-ocaml-5.4.1 /root/build/lane-<name>/resolver-roots
```

The script copies the files, compiles each with the switch's `rocq c -q -Q . Repro`,
checks each with `rocqchk -silent -o -Q . Repro Repro.<File>` and prints one line per
file with both exit statuses and the checker's message. `tools.txt` under the output
directory records the checker's version and SHA-256 and the sources' hashes, and each
`<File>.time` is GNU time's record of the check. The run installs nothing and leaves
the switch unchanged.
