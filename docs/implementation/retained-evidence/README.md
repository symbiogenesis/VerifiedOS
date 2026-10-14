# Retained native evidence

This directory keeps verbatim copies of the evidence records that tracked files cite
by path, among them the [completion log](../completion-log.md), the
[implementation checklist](../implementation-checklist.md), the
[supervisor route record](../../../supervisor/route/result.json) and its
[exchange result](../../../supervisor/route/exchange-result.json).
Those paths name working storage: the guest build and log roots, and a checkout's
ignored `out/` directory. A clone carries neither, later runs overwrite the tools'
fixed work directories, and lane cleanup removes native outputs. The copies keep each
cited record readable after its source is gone.

**Each copy sits at its cited path.** A guest path `/root/<path>` is retained at
`root/<path>`, and a checkout path `out/<path>` at `out/<path>`. Each Markdown
citation links its copy, using either a path label or a readable description. The
resolved indexed target identifies the copy. The bytes are unchanged, so a SHA-256
recorded beside a citation, or bound to the path in a JSON record, also identifies
the copy.
`python tools/run.py test --only retained_evidence` checks those relations and
exercises each refusal on a sandbox control.

**A cited bundle manifest may bind its members instead of repeating every member
in the owning prose.** The owning document links the manifest by its retained path
and records its SHA-256. Only a file named `manifest.json` defines a bundle;
native receipts' unrelated file inventories remain recorded data. A manifest's
`files` map identifies each member by a
relative `path`, or by the map key when no `path` is present, and records `sha256`
and `bytes`. Members must be indexed files beneath the manifest's own directory;
absolute paths, traversal, missing copies and mismatched hashes or sizes fail.
For an `encoding: gzip` member, `stored_sha256` and `stored_bytes` bind the stored
copy, and `sha256` and `bytes` also bind its decompressed contents. Only `identity`
and `gzip` encodings are accepted. A lossless storage change preserves the recorded
content hash and byte count, binds the new stored bytes, and refreshes the manifest's
external hash citation; native paths inside historical records stay unchanged.
Each manifest requires its own hash-checked
citation from a tracked document or record outside this directory. Listing
another manifest as a member binds its bytes but does not cite its children.
A manifest cannot cite itself or make an otherwise uncited bundle count as cited.
Every member remains either directly
cited or bound by a manifest whose own citation and hash were checked. This is a
retention relation, not build or proof acceptance.

**Prepare a new bundle from explicitly selected files.** The retention command
copies each named source verbatim, writes the members' identities and prints a
manifest citation with its SHA-256:

```powershell
python tools/run.py retain --bundle q40/hosted `
  --note docs/implementation/completion-log.md --label "Hosted compiler qualification" `
  --file report.json=out/qualification/report.json `
  --gzip logs/compile.log.gz=out/qualification/compile.log.gz
```

`--file MEMBER=SOURCE` and `--gzip MEMBER=SOURCE` may be repeated. Source paths
may be absolute or relative to the checkout; there is no glob or directory selection.
`--gzip` preserves an already compressed source and records both its stored and
decoded hashes and byte counts. `--bundle` names a new directory relative to this
directory. `--note` supplies the owning Markdown note's path so the printed link
is relative to it; the command edits no note and stages no files. Add the citation
to that note, inspect the output and stage the note and bundle by their paths.

The producer refuses existing destinations, symlink or junction components,
escaping and ambiguous names, colliding members and selected nested manifests.
Private staging holds every copied member and the manifest before one atomic
publication; interruption publishes no partial bundle. The command never replaces
historical evidence. Run the focused retention checks after indexing the intended
deliverables; their independent roots and byte checks still decide the retention
relation.

**A copy is a historical observation of its recorded bytes.** It is not a current
build receipt and grants no acceptance beyond what its citing note states. Absolute
paths inside a record identify artifacts on the recording host. Traces, images and
toolchains that a record binds by hash stay in native storage when they are retained
at all; reading a copy does not require them. Do not rewrite its recorded contents.
