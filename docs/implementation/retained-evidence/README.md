# Retained native evidence

This directory keeps verbatim copies of the evidence records that the
[completion log](../completion-log.md), the
[implementation checklist](../implementation-checklist.md) and the
[supervisor route record](../../../supervisor/route/result.json) cite by path.
Those paths name working storage: the guest build and log roots, and a checkout's
ignored `out/` directory. A clone carries neither, later runs overwrite the tools'
fixed work directories, and lane cleanup removes native outputs. The copies keep each
cited record readable after its source is gone.

**Each copy sits at its cited path.** A guest path `/root/<path>` is retained at
`root/<path>`, and a checkout path `out/<path>` at `out/<path>`. Each Markdown
citation links its copy. The bytes are unchanged, so a SHA-256 recorded beside a
citation, or bound to the path in a JSON record, also identifies the copy.
`python tools/run.py test --only retained_evidence` checks those relations and
exercises each refusal on a sandbox control.

**A copy is a historical observation of its recorded bytes.** It is not a current
build receipt and grants no acceptance beyond what its citing note states. Absolute
paths inside a record identify artifacts on the recording host. Traces, images and
toolchains that a record binds by hash stay in native storage when they are retained
at all; reading a copy does not require them. Do not rewrite a copy.
