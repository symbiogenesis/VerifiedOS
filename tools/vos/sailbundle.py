# SPDX-License-Identifier: Apache-2.0
"""The model's own machine-readable view of itself, and what may be asked of it.

Sail emits a bundle describing everything it typechecked: every function, mapping,
`val`, type, register and `let`, each with its source text, the file it is written in
and the line it starts on, plus the md5 of every file that went into the run. The
curated model already built that bundle on the way to every other artifact and nothing
read it, while `tools/vos/` carried four regex parsers over the same Sail. That is the
two-copies-of-one-parse defect this repository exists to catch, sitting in the tools
that catch it.

**This module is a parse and never a decision**, as everywhere else in this package.
What the values must be and which disagreements matter belongs to the checks.

## What the schema is, and what it is not

The bundle is `version` 1 with `embedding` `plain`, and a version other than 1 is
refused rather than read: the shapes below are that version's, and a reader that
guessed at a later one would report about fields it invented. Ten maps hang off the
top level, and under `--doc-embed plain --doc-embed-with-location` every source slot is
`{contents, file, loc}` with `loc` the six-element `[line, bol, char, line, bol, char]`
Sail writes, whose first element is the 1-based line a finding sends a person to.

The one thing a reader must not assume is provenance. **The bundle carries no `git`
key**: Sail 0.20.2 emits none, so the artifact does not record the commit it came from,
and nothing here may say which revision it describes. What it does record is the md5 of
every file it read, which is the stronger fact for the question actually being asked:
whether the bundle still describes the sources in this checkout.

## The precondition on those hashes, which is a precondition and not a normalization

Of the 158 files the emitter hashes, most are keyed relative to `model/model/` and
resolve in this checkout. The rest are the Sail library's own, keyed by the **absolute
host path** they were read from, `/root/.opam/default/share/sail/lib/arith.sail` and its
neighbours. Those keys are the emitter's output and the tracked artifact is exactly what
the emitter wrote, which is the property the whole generated-artifact discipline buys,
so they are not rewritten here: a normalizer would make the tracked bytes a function of
this module rather than of Sail.

What stands in place of a normalizer is a stated precondition. The comparison below
holds **under the layout `vos/env.py` fixes**: the guest lane runs as root against the
default opam switch, so the library prefix is `LIBRARY_PREFIX`. A hashes key that is
neither relative nor under that prefix means the bundle was emitted against a Sail
library this repository does not fix, and `library_owners` **fails closed** on it,
naming the key, rather than dropping it and reporting agreement over the rest.
`env.opam_root()` is deliberately not consulted: it answers with the *running* lane's
root, which on the Windows host is not the root the artifact was emitted under, so a
rule built on it would decide different things on the two lanes about one file.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, override

BUNDLE_NAME = "sail_riscv_model.json"

# Tracked, and under `tools/` rather than under `model/`. `model/` is `-text` in
# .gitattributes and vendored byte-identically from its upstream pin, so a generated
# artifact there would break both properties at once; `tools/` already carries four
# directories that are inputs to the tools rather than commands, and this is a fifth of
# exactly that kind. Neither placement adds a top-level directory to CLAUDE.md's map.
BUNDLE = f"tools/generated/{BUNDLE_NAME}"

# What a hashes key and a source slot's `file` are relative to.
SOURCE_ROOT = "model/model"

# The only version whose shapes are written down here.
VERSION = 1

# The layout the comparison holds under: see this module's docstring. Stated as the
# literal it is, because the running lane's own opam root is not the one the tracked
# artifact was emitted under.
LIBRARY_PREFIX = "/root/.opam/default/share/sail/"

# The maps this reader knows how to open, and the key each one's members are indexed by
# inside its own entry. `spans` and `anchors` are top-level too and nothing here reads
# them, so they are absent by decision rather than by oversight.
_TOP_LEVEL = ("version", "embedding", "hashes", "functions", "mappings", "vals",
              "types", "registers", "lets", "anchors", "spans")

# The call every assembly clause puts between the mnemonic and its first operand, as the
# bundle spells it: an `app` node whose id is this. A clause with none spells a mnemonic
# and nothing else.
OPERAND_SEP = "spc"

# A Sail string literal arrives with its quotes, `"\"amoswap\""`, because the node
# carries the literal's own source spelling rather than its value.
_QUOTED_RE = re.compile(r'^"(.*)"$', re.DOTALL)

# The literals of a body this reader has only as text, which is the one assembly clause
# the emitter leaves unstructured. Not a general Sail parse: one scan for quoted runs in
# one string, which is what a lower bound on that clause's spelling is made of.
_TEXT_LITERAL_RE = re.compile(r'"([^"]*)"')


class BundleError(RuntimeError):
    """The bundle is there and is not the artifact this reader was written against.

    Raised rather than returned, because every caller here is a check whose whole
    subject is the bundle: a reader that answered `None` for a version it does not know
    would let a rule report agreement between a document and a shape it never read.
    """


@dataclass(frozen=True)
class Site:
    """Where a definition is written, as a finding has to name it: a repository-relative
    path and the 1-based line a person opens."""

    file: str
    line: int

    @override
    def __str__(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True)
class Spelled:
    """One `mapping clause assembly`, and every mnemonic it can spell.

    `exact` is the whole of the difference between this and the skeleton parse it
    replaces. Where the emitter gives the clause's right-hand side as structured
    patterns, every mapping in the mnemonic is resolved against its own literal arms and
    `mnemonics` is the finished set, which **over**-approximates: a cross product admits
    combinations a joint constraint elsewhere in the model forbids. Where it does not,
    `mnemonics` is the clause's string literals in order and nothing else, which
    **under**-approximates exactly as the skeleton did. A rule reading this owes the
    direction out loud, because the two are not two strengths of one claim.
    """

    ctor: str
    site: Site
    exact: bool
    mnemonics: tuple[str, ...]


@dataclass(frozen=True)
class Decoded:
    """One name the model's decode surface can decode a word to, and where it says so."""

    ctor: str
    site: Site
    mapping: str


def _quoted(value: str) -> str | None:
    """A Sail string literal's value, or `None` where the node is not one."""
    found = _QUOTED_RE.match(value)
    return str(found.group(1)) if found else None


class Bundle:
    """One emitted bundle, opened once and asked many questions.

    Every accessor below either answers or raises `BundleError`. Nothing returns a
    quietly empty answer for a name the model does not carry: a renamed or deleted
    definition is the defect this whole item exists to turn from a silent no-match into a
    named finding, so a lookup that misses says which name missed.
    """

    def __init__(self, raw: dict[str, Any], path: str = BUNDLE) -> None:
        self.path = path
        missing = [key for key in _TOP_LEVEL if key not in raw]
        if missing:
            raise BundleError(
                f"{path} carries no {', '.join(missing)}, so it is not the "
                f"version {VERSION} bundle this reader was written against")
        if raw["version"] != VERSION:
            raise BundleError(
                f"{path} states version {raw['version']!r} and this reader is written "
                f"against version {VERSION}; regenerate it with `run.py model bundle` "
                f"or teach this module the newer shape")
        self.embedding: str = str(raw["embedding"])
        self._raw = raw

    # -- the maps, each as the emitter indexes it -------------------------------------

    def _map(self, name: str) -> dict[str, Any]:
        got = self._raw[name]
        if not isinstance(got, dict):
            raise BundleError(f"{self.path}'s {name} is a {type(got).__name__} "
                              f"and this reader expects a map")
        return got

    @property
    def hashes(self) -> dict[str, str]:
        """Every file the emitter read, against the md5 it read it at."""
        out: dict[str, str] = {}
        for key, entry in self._map("hashes").items():
            digest = entry.get("md5") if isinstance(entry, dict) else None
            if not isinstance(digest, str):
                raise BundleError(f"{self.path} records no md5 for {key}")
            out[key] = digest
        return out

    def owners(self) -> dict[str, str]:
        """The files this checkout carries, keyed by their repository-relative path.

        These are the bundle's own statement of what it was emitted from, so a rule
        holding them against the working tree is asking whether the artifact still
        describes the model beside it, with no second list to maintain.
        """
        return {f"{SOURCE_ROOT}/{key}": digest
                for key, digest in self.hashes.items() if not key.startswith("/")}

    def library_owners(self) -> dict[str, str]:
        """The Sail library files the emitter read, keyed by the absolute path it read
        them at. Fails closed on a key under any other root: see this module's docstring
        for why that is a precondition and not something to normalize away."""
        out: dict[str, str] = {}
        for key, digest in self.hashes.items():
            if not key.startswith("/"):
                continue
            if not key.startswith(LIBRARY_PREFIX):
                raise BundleError(
                    f"{self.path} was emitted against {key}, which is outside "
                    f"{LIBRARY_PREFIX}: the layout vos/env.py fixes is the one this "
                    f"comparison holds under, and under any other OPAMROOT the "
                    f"library this bundle describes is not the pinned one")
            out[key] = digest
        return out

    # -- definitions, by name ---------------------------------------------------------

    def _site(self, slot: dict[str, Any]) -> Site:
        file, loc = slot.get("file"), slot.get("loc")
        if not isinstance(file, str) or not isinstance(loc, list) or not loc:
            raise BundleError(f"{self.path} carries a source slot with no file:line, "
                              f"which --doc-embed-with-location is what supplies")
        return Site(f"{SOURCE_ROOT}/{file}", int(loc[0]))

    def type_text(self, name: str) -> str:
        """A type synonym's own declaration, as the model writes it.

        The text rather than the value, because the value is one `= <n>` extraction
        further in and the callers each want their own. What this buys over a scan of
        the file is that a renamed or deleted declaration raises here instead of
        matching nothing there.
        """
        entry = self._map("types").get(name)
        if not isinstance(entry, dict) or not isinstance(entry.get("type"), dict):
            raise BundleError(f"the model declares no type {name}")
        return str(entry["type"].get("contents", ""))

    def let_text(self, name: str) -> str:
        """A top-level `let`'s own declaration, on the same terms as `type_text`."""
        entry = self._map("lets").get(name)
        source = entry.get("let", {}).get("source") if isinstance(entry, dict) else None
        if not isinstance(source, dict):
            raise BundleError(f"the model declares no let {name}")
        return str(source.get("contents", ""))

    def function_clauses(self, name: str) -> list[tuple[str, str, Site]]:
        """One function's clauses, as `(the pattern's id, the body's text, the site)`.

        The pattern is structured, so a clause of `hartSupports` hands back `Ext_Zvl64b`
        without the caller writing a pattern for the head; the body is text, because
        what a caller asks of it is an expression and not a name.
        """
        entry = self._map("functions").get(name)
        clauses = entry.get("function") if isinstance(entry, dict) else None
        if not isinstance(clauses, list):
            raise BundleError(f"the model declares no function {name}")
        out: list[tuple[str, str, Site]] = []
        for clause in clauses:
            if not isinstance(clause, dict):
                continue
            pattern = clause.get("pattern")
            body = clause.get("body")
            source = clause.get("source")
            ident = pattern.get("id") if isinstance(pattern, dict) else None
            if not isinstance(ident, str) or not isinstance(body, dict):
                continue
            out.append((ident, str(body.get("contents", "")),
                        self._site(source if isinstance(source, dict) else body)))
        return out

    # -- mappings ---------------------------------------------------------------------

    def mapping_names(self) -> list[str]:
        return sorted(self._map("mappings"))

    def _clauses(self, name: str) -> list[dict[str, Any]]:
        entry = self._map("mappings").get(name)
        clauses = entry.get("mapping") if isinstance(entry, dict) else None
        if not isinstance(clauses, list):
            raise BundleError(f"the model declares no mapping {name}")
        return [c for c in clauses if isinstance(c, dict)]

    def mapping_literals(self, name: str) -> tuple[str, ...] | None:
        """Every string a mapping's arms can produce, or `None` where one arm produces
        no literal at all.

        `None` rather than a short list, because a mapping one of whose arms is decided
        elsewhere cannot be enumerated: taking the arms that do carry a literal would
        hand back a set that reads complete and is not, which is the failure mode the
        whole of this item is about.
        """
        out: list[str] = []
        for clause in self._clauses(name):
            found = [value for side in ("left", "right")
                     if isinstance(node := clause.get(side), dict)
                     and node.get("type") == "literal"
                     and (value := _quoted(str(node.get("value", "")))) is not None]
            if not found:
                return None
            out.append(found[0])
        return tuple(out) if out else None

    def _expand(self, node: dict[str, Any]) -> tuple[str, ...] | None:
        """Every string one pattern of a mnemonic can be, or `None` where it is decided
        by something this reader cannot enumerate."""
        kind = node.get("type")
        if kind == "literal":
            value = _quoted(str(node.get("value", "")))
            return None if value is None else (value,)
        if kind == "app":
            ident = node.get("id")
            if isinstance(ident, str) and ident in self._map("mappings"):
                return self.mapping_literals(ident)
        return None

    def assembly(self) -> list[Spelled]:
        """Every `mapping clause assembly`, with the mnemonics each can spell.

        The mnemonic is the run of patterns before the operand separator, and each is
        expanded against the mapping that decides it. A clause the emitter hands back
        with no structured right-hand side keeps the older reading, its own string
        literals in order, and says so in `exact`: one such clause is not a reason to
        drop the exactness of the other two hundred, and it is not a reason to claim it
        either.
        """
        out: list[Spelled] = []
        for clause in self._clauses("assembly"):
            left = clause.get("left")
            ctor = left.get("id") if isinstance(left, dict) else None
            source = clause.get("source")
            if not isinstance(ctor, str) or not isinstance(source, dict):
                continue
            site = self._site(source)
            right = clause.get("right")
            if isinstance(right, dict):
                spelled = self._spell(right)
                if spelled is not None:
                    out.append(Spelled(ctor, site, exact=True, mnemonics=spelled))
                    continue
            out.append(Spelled(ctor, site, exact=False,
                               mnemonics=self._text_skeleton(clause)))
        return out

    def _spell(self, right: dict[str, Any]) -> tuple[str, ...] | None:
        """One clause's finished mnemonics, or `None` where a part is not enumerable."""
        parts = (right.get("patterns") if right.get("type") == "string_append"
                 else [right])
        if not isinstance(parts, list):
            return None
        options: list[tuple[str, ...]] = []
        for part in parts:
            if not isinstance(part, dict):
                return None
            if part.get("type") == "app" and part.get("id") == OPERAND_SEP:
                break
            expanded = self._expand(part)
            if expanded is None:
                return None
            options.append(expanded)
        if not options:
            return None
        spellings: list[str] = [""]
        for choices in options:
            spellings = [head + tail for head in spellings for tail in choices]
        # ordered rather than a set, because a finding names the mnemonic it found and
        # the run's output must not depend on a hash seed
        return tuple(dict.fromkeys(spellings))

    def _text_skeleton(self, clause: dict[str, Any]) -> tuple[str, ...]:
        """The one reading left for a clause the emitter does not structure: its string
        literals in order, concatenated, which is a lower bound on what it spells and
        never a claim about the characters between them."""
        body = clause.get("body") or clause.get("source")
        text = str(body.get("contents", "")) if isinstance(body, dict) else ""
        head = text.split(f"{OPERAND_SEP}()")[0]
        joined = "".join(str(part) for part in _TEXT_LITERAL_RE.findall(head))
        out: tuple[str, ...] = (joined,) if joined else ()
        return out

    def decoded(self, prefix: str = "encdec") -> list[Decoded]:
        """Every name the model's decode surface can decode a word to.

        Two shapes and one reading, where the file scan needed two patterns. A whole
        clause is the form where the mapping is `encdec` itself and its left side names
        an instruction constructor; the form's identity is a field value where the clause
        is shared and a named `encdec_*` mapping says which value means which form. Both
        are arms of a mapping here, so both come out of one walk, and a numeric arm
        carries no id and contributes nothing rather than contributing a digit run that
        looked like a name to a backwards scan.
        """
        out: list[Decoded] = []
        for name in self.mapping_names():
            if not name.startswith(prefix):
                continue
            for clause in self._clauses(name):
                source = clause.get("source")
                if not isinstance(source, dict):
                    continue
                site = self._site(source)
                for side in ("left", "right"):
                    node = clause.get(side)
                    if not isinstance(node, dict) or node.get("type") not in ("app", "id"):
                        continue
                    ident = node.get("id")
                    if isinstance(ident, str):
                        out.append(Decoded(ident, site, name))
        return out


def load(root: Path, path: str = BUNDLE) -> Bundle | None:
    """The tracked bundle, or `None` where it is not there.

    Absence is the caller's finding to word and not this module's to raise, exactly as
    the other model parses in this package treat a file that has moved. Anything else
    wrong with it raises: a bundle that is there and unreadable is a defect in the
    generated artifact, and a rule that read past it would report about nothing.
    """
    file = root / path
    if not file.is_file():
        return None
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{path} is not readable as JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise BundleError(f"{path} is a {type(raw).__name__} and not a bundle")
    return Bundle(raw, path)
