# SPDX-License-Identifier: Apache-2.0
"""counts, the model window: what the curated model cites, and what it still decodes.

`model/` is outside the document corpus, so two claims about it were held by nothing:
that every requirement a Sail comment argues from exists, and that no form the profile
excludes is still on the decode surface. Both are read over the same window of files,
admitted by kind rather than by name, and the window is opened once here and handed to
each rule that reads it.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from vos import corpus as corpus_mod
from vos import decode
from vos.register import ISA_PROFILE, REQ_TOKEN_RE

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

# A backticked name in an exclusion row's first cell. The cell is prose around them,
# so the backticks are what marks a name the document is spelling exactly rather than
# describing, which is the only part of that cell a machine has any business reading.
EXCLUDED_NAME_RE = re.compile(r"`([^`]+)`")

# The Sail constructor a row names where its subject is a single instruction form,
# written `Sail: `CTOR`` inside the first cell. It is read out before the names are,
# because a constructor is not a mnemonic the profile spells and counting it as one is
# what let it sit in that cell matching nothing and reported as checked.
MARKER_RE = re.compile(r"Sail:\s*`([^`]+)`")


def citation_window(ctx: Context) -> tuple[list[tuple[str, str]], list[str]]:
    """The model-citation window, read once for the two rules that scan it.

    K-63 reads every file the window admits and K-66 re-read the Sail subset of the
    same files moments later, so the one read lives here and every consumer takes
    `(rel, text)` pairs. The reads go through a thread pool because a file read
    releases the interpreter lock, so the on-access virus scan the window's first
    read pays overlaps across files instead of serializing; the pool's `map` returns
    in submission order, so the pairs come back in the sorted order they were asked
    in and the run's output does not depend on which read finished first.

    A file the index lists and the working tree no longer holds is dropped silently,
    as the corpus drops a deleted document; a file that is there and cannot be read
    is a finding worded once, under K-63, because pricing one unreadable file under
    both rules would report one defect twice.
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
    """K-63: every requirement the model cites, in the files this tool can see.

    The curated model argues from the register constantly: a Sail file states why a
    field is the width it is, why a class declares nothing where another declares
    something, why an instruction traps where the base ISA would execute. Every one of
    those arguments names a requirement id, and until now not one of them was checked,
    because `model/` is excluded from the checker's corpus wholesale and K-11 reads
    only tracked documents. A mistyped or invented id in a model comment therefore
    rendered as a citation, survived review, and pointed at nothing.

    The reach is by kind and not by name, which is a decision rather than the absence
    of one. `MODEL_FACTS` is the *value* window and stays narrow, because a rule reading
    a number out of the model should name the file it reads. This rule holds a
    construct that occurs wherever the model argues from the register, so its natural
    reach is the tree: pointed at the value window it would see under a quarter of the
    model's citations, which is a rule reporting `ok` about a quarter of its subject.
    The count itself is this rule's own `ok` line and is never written down here.

    Ids are permanent and a retired requirement is struck rather than removed
    (CLAUDE.md), so what this catches is not renumbering. It is the typo, the id
    invented while writing prose about a requirement that turned out to be numbered
    something else, and the citation carried across from an upstream that had its own.
    """
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


def excluded_forms(ctx: Context, window: list[tuple[str, str]]) -> None:
    """K-66: no form the profile excludes is still on the model's decode surface.

    The profile's §6 excludes by name and the model implements by clause, and until
    now nothing held the two together. `model.py sweep` does not: it runs the profile
    configuration against upstream `riscv-tests` and counts refusals of *those*
    programs, which is conformance against an external corpus and not a claim that the
    model implements only what the profile admits. Its figure reads the same whether or
    not an excluded form is still decoded, which is how the fault-only-first loads
    (R-15-039b) stayed on the surface after the amendment that excluded them.

    **Both halves of the surface are read, because a form leaves by two doors.** A
    `mapping clause assembly` is the model spelling what it decoded; `dialect.MNEMONICS`
    is the corpus assembler emitting a word for the model to decode. A form deleted from
    one and left in the other is still reachable: an encoder row with no clause lays
    down a word the model refuses, and a clause with no encoder row is surface no corpus
    program can reach and an implementation still carries. So a finding names the half
    it was found in, and the rule is not satisfied by either half alone.

    **The reach is by kind, and here that is not a preference.** `MODEL_FACTS` is the
    *value* window of files named one by one, and **none of the readable spellings is
    in one of them**, so aimed there this rule would have read nothing at all and passed
    green over the whole decode surface: not K-63's quarter of its subject but none of it.
    A decode clause occurs wherever the model defines an instruction, which is most of
    the tree, so the window that fits it is the one that admits by kind.

    **Where a row's subject is a single instruction form the profile names the Sail
    constructor, and that name is tested by membership rather than by matching.** A
    skeleton is a lower bound on what a clause spells, so a mnemonic assembled out of
    three mappings and a dot leaves nothing to match against: the profile writes
    `amocas.q`, the model writes `amo_mnemonic(op) ^ "." ^ width_mnemonic_wide(width)`,
    and the fragment test pairs the one with nothing. A marker is not a spelling and is
    not matched: the constructor is in the set of names the decode surface decodes to
    or it is not, which additionally reaches a form whose clause is shared with its
    neighbours and whose identity is a field value, `AMOCAS` being both.

    **The marker widens the rule and replaces no part of it.** The fragment path runs
    over every row's names exactly as before, marked or not, because a marker cannot
    see a form re-added under another constructor and is worth only the run that
    validated it: one that is stale or misspelled is absent for the same reason a
    deleted form is, and degrading to the fragment path is what keeps that from being a
    silent green. A row naming several forms, or an extension spanning many
    constructors, carries no marker and is out of the membership test's reach rather
    than mis-typed, so an unmarked row is read exactly as it was.

    **What it cannot see is most of the exclusion table, and the honest figure is in
    the `ok` line.** A row is read only where a name it spells matches something the
    machine can spell back: a CSR, a privilege mode, an extension name, and a
    microarchitectural structure are all excluded in prose that no mnemonic test
    decides, and such a row is read and passes. So a green run says *no excluded name
    is spelled by the surface and no marked constructor is decoded by it*, never *every
    exclusion is honoured*. On the model's side the same boundary holds for the
    fragment path: the assembly clauses that build their mnemonic entirely inside a
    mapping leave no literal in the file and are invisible to it, which is the gap a
    marker on such a form closes one row at a time.
    """
    rep = ctx.rep
    findings: list[str] = []
    spellings = decode.read_spellings(window)
    decoded = decode.read_decoded(window)

    names = 0
    markers = 0
    for row in ctx.art.exclusion_rows:
        cells = row.strip().strip("|").split("|")
        ground = ", ".join(sorted(set(REQ_TOKEN_RE.findall(cells[-1])))) or "no requirement"
        for ctor in MARKER_RE.findall(cells[0]):
            markers += 1
            findings += [
                f"{ISA_PROFILE} §6 excludes `{ctor}` on {ground}, and "
                f"{d.file}:{d.line} still decodes it, in {d.site}"
                for d in decoded if d.ctor == ctor]
        for name in EXCLUDED_NAME_RE.findall(MARKER_RE.sub("", cells[0])):
            names += 1
            findings += [
                f"{ISA_PROFILE} §6 excludes `{name}` on {ground}, and "
                f"{s.file}:{s.line} still spells it, as {s.ctor}"
                for s in spellings if decode.spells(s.skeleton, name)]
            findings += [
                f"{ISA_PROFILE} §6 excludes `{name}` on {ground}, and the corpus "
                f"assembler still encodes `{mnemonic}`"
                for mnemonic in decode.encoder_rows(name)]

    ctx.shared["exclusion_names"] = names
    ctx.shared["exclusion_markers"] = markers
    ctx.shared["decode_spellings"] = len(spellings)
    ctx.shared["decoded_names"] = len(decoded)
    ctx.shared["encoder_rows"] = len(decode.dialect.MNEMONICS)
    rep.report("K-66", "excluded form(s) still on the decode surface:", findings,
               f"none of the {names} names the profile's {len(ctx.art.exclusion_rows)} "
               f"exclusion rows spell is spelled by the {len(spellings)} readable "
               f"assembly clauses or carried by the "
               f"{len(decode.dialect.MNEMONICS)} encoder rows, and none of the "
               f"{markers} Sail constructors they mark is among the {len(decoded)} "
               f"names the decode surface decodes to")
