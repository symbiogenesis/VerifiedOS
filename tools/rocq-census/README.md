# Locked Rocq native type metadata

This original producer reads Rocq 9.3.0's installed native module/declaration API.
It replaces the earlier diagnostic term printer with versioned JSON constructors.
It does not decide the [complete support census](../../docs/implementation/contracts/sail-support-census.md),
classify declarations for the common inventory guard, resolve sealed implementation
connections, audit assumptions, or run the recursive kernel checker.

Run the focused control in the guest using the existing locked switch and an
explicit immutable directory containing the already compiled selected support:

```sh
python3 tools/run.py rocq-census \
  --switch-root /root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1 \
  --out /root/build/lane-ASSIGNED/native-metadata-NEW \
  --support-source /absolute/retained/support/src-stdpp
```

The `rocq-census` dispatcher runs [qualify.py](qualify.py). The supplied support
must contain the compatible `MachineWordInterface.vo` and dependencies. The helper
copies that directory into the fresh output directory and compiles only the
original [plugin](vos_rocq_census.ml) and [control query](NativeControls.v).
It installs nothing and never compiles installed or supplied dependency sources.
Every subprocess has an absolute temporary working directory. The environment
inherits system variables and adds only tool/plugin discovery and target selection.

`--targets` optionally supplies comma-separated native module names loaded by the
control query. The default requests its synthetic controls and the actual support
interface. The query contains signature, functor parameter/result, sealed concrete,
applied functor, empty module and dependent-type shapes. Its successful exit is a
**metadata control**, not census qualification. Strict compiler diagnostics remain
refusals. Exhaustive constructor matches are compiled with missing-case warnings
as errors; a changed locked API requires a producer review.

`receipt.json` records arguments, command exits, authored source and launcher
identities. Complete `.vo`/`.glob` path-to-hash maps are rescanned beneath installed
`lib/coq` and the original supplied support before and after the control. Added,
deleted and changed paths are reported separately; any difference refuses its exit.
The final helper also requires exactly one well-formed JSON emission with the
expected metadata schema/boundary and exact requested target population. This output
guard supplies no full native field-census qualification.
This checks those recorded populations at the observation cuts, not every installed
file or the interval between cuts. The runner's final canonical-path and identity-refusal packaging
has focused helper/static checks; the retained executed runner remains independently bound.

The output schema is `verifiedos-rocq-native-metadata/1`. A `tag` names each native
term, module-signature, quality, universe-level or name constructor; the remaining
keys retain its components. Arrays retain native order. Module paths and both user
and canonical kernel names are structural, and bound-module identifiers retain
stamp, identifier and directory. Directory and declaration-context sequences retain
the native reversed/innermost-first order named by their keys. Types retain binder
relevance, cast kind, complete case annotations and branch/return binders, recursion
metadata, projection details, universe instances, abstract universe binder names
and constraints, and local declaration contexts. Primitive strings use byte hex;
floats use the API's exact hex spelling, with NaNs identified as Rocq's single
semantic NaN class. No debugging term printer or marshalled runtime object is used.

`Meta`, `Evar`, rewrite-rule fields and an unrecognized universe-level representation
explicitly refuse. Native refusal controls have not been run. The successful bounded
control covers only constructors occurring in its retained JSON; it does not qualify
unexercised constructors. Module/global monomorphic universe constraints, module expressions/delta
resolvers, template/variance metadata, declaration typing flags and concrete implementation
connections remain outside this type-metadata export. Every module carries
`implementation_connection: unqualified`; interface and functor contexts remain
explicit. The output cannot be passed to the common inventory guard as a census.

The [checkpoint](checkpoint.json) fixes this step's maximum three candidate checks
or twenty active minutes. Its three attempts are retained by the
[native inventory note](../../docs/implementation/q35q-native-inventory.md).
Further native qualification requires a new bounded owner act under the contract.
The linked plugin stays in the native lane; only original source and textual evidence
are distributed. The installed Rocq implementation is LGPL-2.1 and is not copied here.
