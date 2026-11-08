# SPDX-License-Identifier: Apache-2.0
"""Check requirement citations in `model/` comments (`K-63`) and excluded instruction forms on the Sail decode surface (`K-66`)."""

import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from vos import corpus as corpus_mod
from vos import decode, sailbundle
from vos.register import ISA_PROFILE, REQ_TOKEN_RE

if TYPE_CHECKING:
    from . import Context

# Backticked mnemonic/extension tokens in an exclusion row's first cell.
EXCLUDED_NAME_RE = re.compile(r"`([^`]+)`")

# Sail AST constructor marker (`Sail: `CTOR``) in an exclusion row's first cell.
MARKER_RE = re.compile(r"Sail:\s*`([^`]+)`")


def citation_window(ctx: Context) -> tuple[list[tuple[str, str]], list[str]]:
    """Read all tracked files matching [`is_model_citation_path`](../corpus.py#is_model_citation_path) once for `K-63` and `K-81`.

    Uses a thread pool so file reads overlap in deterministic path order. Missing
    working-tree files are skipped; unreadable files are returned in `faults` and
    reported once under `K-63`.
    """
    rels = [rel for rel in sorted(ctx.corpus.tracked)
            if corpus_mod.is_model_citation_path(rel)]

    def read(rel: str) -> tuple[str, str] | str | None:
        path = ctx.root / rel
        if not path.is_file():
            return None
        try:
            return rel, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return f"{rel}: unreadable, so its citations cannot be decided ({exc})"

    pairs: list[tuple[str, str]] = []
    faults: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for got in pool.map(read, rels):
            if isinstance(got, tuple):
                pairs.append(got)
            elif got is not None:
                faults.append(got)
    return pairs, faults


def model_citations(ctx: Context, window: list[tuple[str, str]],
                    faults: list[str]) -> None:
    """K-63: every `R-NN-NNN` token in the `model/` citation window names a requirement in [requirements-register.md](../../../docs/requirements-register.md)."""
    rep, reg = ctx.rep, ctx.reg
    findings: list[str] = list(faults)
    cited = 0
    files = 0
    for rel, text in window:
        found = REQ_TOKEN_RE.findall(text)
        if found:
            files += 1
        cited += len(found)
        findings += [f"{rel} cites {ident}, which the register does not declare"
                     for ident in sorted(set(found)) if ident not in reg.id_set]
    ctx.shared["model_citations"] = cited
    rep.report("K-63", "model citation(s) naming no requirement:", findings,
               f"all {cited} requirement citations the model makes, across {files} of "
               "its files, name a requirement the register declares")


def excluded_forms(ctx: Context) -> None:
    """K-66: no instruction form excluded in [isa-profile.md](../../../docs/hardware/isa-profile.md) §6 remains on the Sail decode or corpus-assembler surface.

    For each row in `ctx.art.exclusion_rows`:
    1. Any `Sail: `CTOR`` marker is checked against the decoded AST constructors in
       [`BUNDLE`](../sailbundle.py#BUNDLE) (`bundle.decoded()`).
    2. Every other backticked name in the first cell is checked against both the Sail
       assembly mappings (`bundle.assembly()`, via [`spelled_by`](../decode.py#spelled_by))
       and the differential-corpus assembler table ([`encoder_rows`](../decode.py#encoder_rows)).
    """
    rep = ctx.rep
    findings: list[str] = []
    bundle = ctx.shared.get("bundle")
    spellings: list[sailbundle.Spelled] = []
    decoded: list[sailbundle.Decoded] = []
    if isinstance(bundle, sailbundle.Bundle):
        spellings = bundle.assembly()
        decoded = bundle.decoded()
    else:
        findings.append(
            f"the model's side of this rule is {sailbundle.BUNDLE}, of which this run "
            "has no readable copy, so no exclusion can be decided against the decode "
            "surface at all")

    names = 0
    markers = 0
    for row in ctx.art.exclusion_rows:
        cells = row.strip().strip("|").split("|")
        ground = ", ".join(sorted(set(REQ_TOKEN_RE.findall(cells[-1])))) or "no requirement"
        for ctor in MARKER_RE.findall(cells[0]):
            markers += 1
            findings += [
                f"{ISA_PROFILE} §6 excludes `{ctor}` on {ground}, and "
                f"{d.site} still decodes it, in {d.mapping}"
                for d in decoded if d.ctor == ctor]
        for name in EXCLUDED_NAME_RE.findall(MARKER_RE.sub("", cells[0])):
            names += 1
            findings += [
                f"{ISA_PROFILE} §6 excludes `{name}` on {ground}, and {s.site} still "
                f"spells `{hit}`, as {s.ctor}"
                for s in spellings for hit in decode.spelled_by(s, name)]
            findings += [
                f"{ISA_PROFILE} §6 excludes `{name}` on {ground}, and the corpus "
                f"assembler still encodes `{mnemonic}`"
                for mnemonic in decode.encoder_rows(name)]

    mnemonics = {m for s in spellings for m in s.mnemonics}
    exact = sum(1 for s in spellings if s.exact)
    ctx.shared["exclusion_names"] = names
    ctx.shared["exclusion_markers"] = markers
    ctx.shared["decode_spellings"] = len(mnemonics)
    ctx.shared["decoded_names"] = len(decoded)
    ctx.shared["encoder_rows"] = len(decode.dialect.MNEMONICS)
    rep.report("K-66", "excluded form(s) still on the decode surface:", findings,
               f"none of the {names} names the profile's {len(ctx.art.exclusion_rows)} "
               f"exclusion rows spell is among the {len(mnemonics)} mnemonics the "
               f"model's {len(spellings)} assembly clauses spell, {exact} of them "
               f"enumerated from the bundle and the rest read as skeletons, or carried "
               f"by the {len(decode.dialect.MNEMONICS)} encoder rows, and none of the "
               f"{markers} Sail constructors they mark is among the {len(decoded)} "
               f"names the decode surface decodes to")
