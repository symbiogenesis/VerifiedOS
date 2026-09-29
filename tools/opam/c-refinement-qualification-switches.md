# Private C-refinement qualification switches

Q35e's [qualification record](../../docs/assurance/c-refinement-foundation-qualification.md)
ran in five project switches created for it in the guest's opam root, four by its
implementer lane and one by its repair lane. They are evaluation instruments, not
project snapshots: no provisioner, bootstrap or hosted workflow imports them, and no
`.lock` here describes them. One installs CompCert's opam package and so carries the
INRIA Non-Commercial License Agreement; under M1.1a's containment every one of them
stays private to the guest that ran the qualification and out of hosted CI's public
proof lane. The [proof switch](README.md) is not among them, and its
`opam switch export` was byte-identical to [rocq.lock](rocq.lock) at the start and
end of both lanes.

Each switch was created empty with
`opam switch create NAME --repos=rocq-released,default --empty --no-switch -y`,
leaving the active switch unchanged, against local metadata last written on
2026-09-27, the `rocq-released` repository at 23:09:39 and `default` at 23:09:53
-0500: `default` at stamp `bbc4314c37cbe5902ab659460c440b099fe729a3` and
`rocq-released` at stamp `2026-09-26 16:46`. No `opam update` ran. The first three
switches hold the locked prover, Rocq 9.2.0 on OCaml 5.4.1; the last two hold only
pins and served the solver.

| Switch | Seed | Added | Non-commercial term |
| --- | --- | --- | --- |
| `verifiedos-q35e-vst2-20260928` | `opam switch import tools/opam/rocq.lock` | `coq-vst.2.17`, which brings `coq-compcert.3.18`, `coq-flocq.4.2.2`, `coq-vst-zlist.2.13` and their menhir closure | Yes: `coq-compcert` |
| `verifiedos-q35e-vst3-20260928` | `opam switch import tools/opam/rocq.lock` | `rocq-iris.4.5.0`, `rocq-vst-ora.1.2`, `coq-vst-zlist.2.13`, `coq-flocq.4.2.2`; VST 3.2beta and 2.17 are built from their release archives in the lane, against the CompCert subset each carries under `compcert/`, and are not installed | No opam package carries it; the CompCert Rocq sources the 2.17 build compiled are on CompCert's dual-licensed list, and the qualification record lists the subset's other files |
| `verifiedos-q35e-refinedc-20260928` | the prover packages alone | pins below, then `coq-lithium` and `refinedc` with `--ignore-constraints-on=coq` | No |
| `verifiedos-q35e-cn-20260928` | none | pins below; nothing installs | No |
| `verifiedos-q35e-cnfix-20260928` | none | the CN switch's pins and `coq-struct-tact` below; nothing installs | No |

The RefinedC switch pins, at the revisions RefinedC `2e89846baeaa7f65cbe17e3ae7297a8ed5b4feca`'s
README and `coq-lithium.opam` name, stdpp through the Iris development package that
`coq-lithium.opam` requires:
`cerberus-lib` at `f11e6b335a687c1b77539f7e5695607d09dfc3ea`, `rocq-stdpp`,
`rocq-stdpp-bitvector` and `rocq-stdpp-unstable` at `c3186aad493872e3a9774ac0b42ca2f591b05835`,
`rocq-iris` at `b3495ef9f0805b0dc7c1b1abbdc8cf473ede121b`, and `coq-lithium` and
`refinedc` at that RefinedC revision. The CN switch pins `cerberus-lib` at
`c8c085d4714ae17095b2e1202fa33c5545d98df1`, the revision `cn.opam` names, and
`cn` and `cn-coq` at CN `10c586baf01f75d0a3209c83d8e622a9d62fb7c8`. The CN repair
switch pins the same three and `coq-struct-tact` at StructTact
`97268e11564c8fe59aa72b062478458d7aa53e9d`, cloned from its upstream repository
because no registered repository carries the package.

The installed sets after the qualification, from each switch's own export:

- **vst2:** the lock's installed packages plus `conf-clang.2`, `coq.9.2.0`, `coq-compcert.3.18`,
  `coq-core.9.2.0`, `coq-flocq.4.2.2`, `coq-menhirlib.20260209`, `coq-vst.2.17`,
  `coq-vst-zlist.2.13`, `coqide-server.9.2.0`, `menhir.20260209`, `menhirCST.20260209`,
  `menhirGLR.20260209`, `menhirLib.20260209` and `menhirSdk.20260209`.
- **vst3:** the lock's installed packages plus `conf-clang.2`, `coq.9.2.0`, `coq-core.9.2.0`,
  `coq-flocq.4.2.2`, `coq-vst-zlist.2.13`, `coqide-server.9.2.0`, `rocq-iris.4.5.0` and
  `rocq-vst-ora.1.2`.
- **refinedc:** the prover's packages, the pinned packages above, and the rest of the
  solver's plan under `--ignore-constraints-on=coq`, among them `coq.9.2.0`,
  `coq-record-update.0.3.6`, `rocq-elpi.3.5.1`, `elpi.3.7.3` and `cerberus-lib`'s
  OCaml closure. The implementer's receipt carries that plan whole and binds the
  switch's export.
- **cn** and **cnfix:** no package.

The switches outlive the lanes that made them, private to the guest, so Q35h can
read VST 2.17 in vst2 and vst3; removing one is a guest act that this guide records.
Recreating one follows the table and the qualification record's commands, and a
recreated switch is a new measurement rather than this one.
