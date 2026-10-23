# SPDX-License-Identifier: Apache-2.0
"""Native Rocq inventory queries and their strictly framed responses.

Search runs in a fresh process with both search filters disabled. It includes local
constants and generated Program obligations, which source declaration scans miss.
Every returned symbol receives its own Print Assumptions query. No source-authored
query contributes to this inventory or to the verdict. The kernel checker's own
context summary is parsed here too, as a second enumeration that does not share the
compiler's Print Assumptions.
"""

import re
from collections import defaultdict
from typing import TypedDict

from vos import proofcites
from vos.proofs import ATTRIBUTE_OPEN, CONTROL_PREFIXES, SENTENCE_END, sentences

MARKER = "VOS_PROOF_AUDIT|"
EMPTY_BLACKLIST = "Current search blacklist :  is empty."
QUALIFIED = re.compile(r"[\w']+(?:\.[\w']+)+")
_SYMBOL = re.compile(r"^([\w']+(?:\.[\w']+)+):\s*(.*)$")

SETTINGS = '''\
Remove Search Blacklist "_subterm" "_subproof" "Private_".
Unset Search Blacklist Locals.
Unset Search Output Name Only.
Set Printing All.
Set Printing Depth 1000000.
Set Printing Width 1000000.
'''


KERNEL_CONTEXT = ("CONTEXT SUMMARY", "===============")
KERNEL_THEORY = ("Set is predicative", "Rewrite rules are not allowed")
KERNEL_UNSAFE = ("Constants/Inductives relying on type-in-type",
                 "Constants/Inductives relying on unsafe (co)fixpoints",
                 "Inductives whose positivity is assumed")
# The summary's final section names the inductives whose elimination or universe relies
# on indices not mattering, Corelib's `eq` among them. The CIC checker profile fixes
# indices_matter=false, so the section describes that theory rather than an assumption
# beyond it. The pinned checker always writes it, `<none>` when it is empty.
KERNEL_INDICES = "Inductives relying on indices not mattering"

# Settings the compiler command line fixes, or whose default the audit relies on. A
# source that sets one overrides that choice for itself, so the gate refuses it.
# Kernel Conversion Dep Heuristic, which Rocq 9.3 adds, is a typing flag each
# declaration records and the checker re-applies, and neither Print Assumptions nor the
# kernel summary reports it. Default Proof Using annotates every unannotated section
# lemma, and an annotation declaring more than the proof uses adds hypotheses to the
# discharged statement.
PINNED_SETTINGS = ("Warnings", "Default Goal Selector", "Bullet Behavior",
                   "Nested Proofs Allowed", "Allow StrictProp", "Definitional UIP",
                   "Guard Checking", "Positivity Checking", "Universe Checking",
                   "Indices Matter", "Strict Universe Declaration", "Default Timeout",
                   "Kernel Conversion Dep Heuristic", "Default Proof Using")
# Everything that can precede a command within its sentence, bullets, braces, goal
# selectors, control flags and quoted and legacy attributes, is the shared lexer's
# decoration grammar ([proofs.py](proofs.py)), written there once for every head reading
# here and every reader outside the gate. A lexical reading anchored after it sees the
# command however it is decorated.
_PINNED = re.compile(CONTROL_PREFIXES + r"(?:Set|Unset)\s+(?:" + "|".join(
    r"\s+".join(map(re.escape, name.split())) for name in PINNED_SETTINGS) + r")\b")
# Attributes that relax the same settings for one declaration. A wall-clock Timeout or
# an allocation limit makes a verdict depend on the machine that ran it.
_PINNED_ATTRIBUTE = re.compile(ATTRIBUTE_OPEN + r"\b(?:warnings?|bypass_check)\b")
_TIMEOUT = re.compile(CONTROL_PREFIXES + r"(?:Timeout|AllocLimit)\s+\d")
# Where a refused word stands as a token of its own (_TACTICAL, _COINDUCTIVE). Rocq's
# lexer continues an identifier through letters, digits, `_` and `'`, so a word joined to
# one of them is a token of its own only where a numeral, a quote or a token from the
# lexer's keyword table ends. So a run of quotes, underscores and numerals before a word
# is read apart from it. A numeral is read as the lexer reads one, fraction and exponent
# included and possessively, so a hexadecimal one reads on through a word's leading
# hexadecimal digits. A decimal one stops before a `0x` that may open a hexadecimal one,
# since a token ending in a digit lets one start there. The possessive read keeps a long
# run of digits linear. Rocq 9.3.0's Unicode table is older than Python's, and the two
# class thousands of characters differently, so only ASCII letters, digits, `_` and `'`
# continue a word here. Any other character beside one separates it, as `²` does in
# Rocq's lexer, which refuses loudly an identifier such as `écofix` that Rocq reads whole.
_WORD = r"A-Za-z0-9_'"
_HEXADECIMAL = r"0[xX][0-9a-fA-F][0-9a-fA-F_]*(?:\.[0-9a-fA-F_]+)?(?:[pP][+-]?[0-9][0-9_]*)?"
_DECIMAL = r"[0-9](?:(?!0[xX][0-9a-fA-F])[0-9_])*(?:\.[0-9_]+)?(?:[eE][+-]?[0-9][0-9_]*)?"
_APART = rf"(?<![{_WORD}])(?:['_]|{_HEXADECIMAL}|{_DECIMAL})*+"
# The Ltac tactical `timeout`, Rocq 9.3's `alloc_limit`, and Ltac2's `Control.timeout` and
# its float twin `Control.timeoutf` bind a verdict to the machine in the same way, and
# stand anywhere in a sentence. Ltac2's two are first-class values, which an alias, a
# parenthesis or `Import Ltac2.Control` lets a proof apply with no argument beside the
# word, so each word is refused wherever Rocq's lexer can read it as a token of its own:
# the pinned Rocq 9.3.0 runs `do 1timeout 5 tac` and, once a notation declares `#_`,
# `#_timeout 5 tac`. A Gallina identifier named exactly after one, a record field among
# them, is refused too, which is loud and costs a rename, and so is one holding a word
# after only quotes, underscores and numerals; any other identifier that contains one is
# read whole.
_TACTICAL = re.compile(_APART + rf"(?:timeoutf?|alloc_limit)(?![{_WORD}])")
# Once comments are blanked, every remaining quote opens or closes a string literal, in
# a source that declares no token holding one, which unreadable_tokens refuses.
_STRING = re.compile(r'"[^"]*"')
# A module command's head: whether it declares a module, and whether it opens a signature.
_MODULE = re.compile(CONTROL_PREFIXES + r"(Declare\s+)?Module\s+(Type\b)?")
# Commands that bring into a compile what no lexical reading of the source sees. Load
# runs another file's sentences, Cd moves where a relative Load resolves, Declare ML
# Module loads a plugin, and Ltac2's `@ external` binds any primitive a loaded plugin
# exports, the timeout tactical among them, under a name of the source's choosing. Add
# LoadPath, Add Rec LoadPath, Remove LoadPath and Add ML Path would choose which files a
# Require reads; the pinned Rocq 9.3.0 parses each as an option table it lacks and
# refuses it, as its deprecation refuses Cd under the gate's flags, and they are refused
# here all the same.
DYNAMIC_SOURCE = re.compile(
    CONTROL_PREFIXES + r"(?:Load|Cd|(?:Add|Remove)\s+(?:Rec\s+)?(?:LoadPath|ML\s+Path)"
    r"|Declare\s+ML\s+Module|Ltac2\s*@\s*external)(?![\w'])")
# Where a declared token comes from. Rocq's lexer matches the longest declared token
# before it looks for a string, a comment or a full stop inside one (find_keyword and
# process_chars in the pinned 9.3.0's cLexer.ml), so once a notation declares `^"`, `a"`,
# `*(*` or `^.`, each is one token wherever it stands. The shared lexer knows no declared
# token. It would open a string at the quote or a comment at the opener, hiding every
# sentence up to the close, or end a sentence at the full stop, cutting the statement it
# is in. That holds for Rocq's own `.` and `...` too: a notation may declare either as an
# infix, and the pinned Rocq 9.3.0 then compiles `1 ... 2 = 3 -> forall m : Machine, P`
# as one statement. Tokens come from the strings a Notation, Reserved Notation, Infix,
# Reserved Infix, Tactic Notation or Ltac2 Notation writes before its `:=`, a Tactic or
# Ltac2 Notation's separators among them. An attribute's strings declare none, and
# neither does a `where` clause: the pinned Rocq 9.3.0 refuses one whose parsing rule no
# earlier Reserved Notation declared.
_DECLARES_TOKENS = re.compile(r"(?<![\w'])(?:Notation|Infix)(?![\w'])")
_TOKEN_SOURCE = re.compile(ATTRIBUTE_OPEN + r'\]|"((?:[^"]|"")*)"|:=')


class AuditError(ValueError):
    """A native response cannot support a complete audit."""


class Symbol(TypedDict):
    name: str
    type: str
    assumptions: list[str]
    claims: list[str]


def inventory_query(module: str) -> str:
    return (f"Require {module}.\n{SETTINGS}Print Table Search Blacklist.\n"
            f"Search _ inside {module}.\n")


def inventory(stdout: str, module: str) -> list[Symbol]:
    """Every native symbol, refusing diagnostics and an active search filter."""
    lines = stdout.splitlines()
    if not lines or lines[0].strip() != EMPTY_BLACKLIST:
        raise AuditError("Rocq did not confirm an empty search blacklist")
    found: list[Symbol] = []
    seen: set[str] = set()
    for line in lines[1:]:
        if not line.strip():
            continue
        match = _SYMBOL.fullmatch(line)
        if match:
            name, typ = match.groups()
            if not name.startswith(f"{module}.") or name in seen:
                raise AuditError(f"unexpected or repeated native symbol {name}")
            seen.add(name)
            found.append({"name": name, "type": typ, "assumptions": [], "claims": []})
        elif line[:1].isspace() and found:
            found[-1]["type"] += " " + line.strip()
        else:
            raise AuditError(f"unrecognized native inventory output: {line}")
    if any(not symbol["type"] for symbol in found):
        raise AuditError("a native symbol has no type")
    return sorted(found, key=lambda symbol: symbol["name"])


def bind_claims(text: str, symbols: list[Symbol]) -> None:
    """Resolve each annotation to exactly one compiled constant in this artifact."""
    claims, faults = proofcites.discharges(text)
    if faults:
        raise AuditError("; ".join(faults))
    if not claims:
        return
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    for symbol in symbols:
        _, separator, name = symbol["name"].rpartition(".")
        if separator:
            by_name[name].append(symbol)
    for name, entries in claims:
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise AuditError(f"claim {name} resolves to {len(matches)} native symbols; "
                             "a claim must identify one compiled declaration")
        symbol = matches[0]
        if symbol["claims"]:
            raise AuditError(f"{name} carries more than one discharge annotation")
        symbol["claims"] = entries


def _assumption_block(name: str) -> list[str]:
    """One framed Print Assumptions, after the marker the response parse keys on."""
    if not QUALIFIED.fullmatch(name):
        raise AuditError(f"invalid native symbol name {name!r}")
    # Each interactive proof opens with Proof: Rocq 9.3 warns by default otherwise,
    # and the gate refuses any diagnostic.
    return [f'Goal True. Proof. idtac "{MARKER}{name}". Abort.\n',
            f"Print Assumptions {name}.\n"]


def assumption_query(module: str, symbols: list[Symbol]) -> str:
    lines = [f"Require {module}.\n", SETTINGS]
    for symbol in symbols:
        name = symbol["name"]
        lines += _assumption_block(name)
        if symbol["claims"]:
            # The source keyword Theorem can introduce a term of type nat. The
            # kernel, rather than that keyword, must decide that a claim is a Prop.
            lines.append(f"Goal True. Proof. let T := type of (@{name}) in "
                         "let K := type of T in unify K Prop. exact I. Qed.\n")
    return "".join(lines)


# A proof module's stem, as `Require` names it: the module of a file under proofs/.
_ROOT = re.compile(r"[\w']+")


def sealed_field_query(roots: list[str], names: list[str]) -> str:
    """Print Assumptions over each of `names`, in the environment that Requires exactly
    `roots`, framed as the assumption audit frames its queries.

    The names are kernel names the checker's summary printed for fields of sealed
    modules in libraries a worker checked. The compiler answers for such a field with
    the assumptions of the implementation its module expression names, resolving an
    alias and a functor application alike (the pinned Rocq 9.3.0's
    vernac/assumptions.ml, `lookup_constant_in_impl`, `fields_of_mp` and
    `fields_of_expr`), and traversing that implementation's body and type
    (`traverse_object`). It reports an assumption the seal hides from the environment
    under the sealed path, and an admitted implementation as the field itself. The
    kernel summary cannot give that reading (`kernel_context`); this query asks the
    compiler for it over the same roots the checker loaded.
    """
    for root in roots:
        if not _ROOT.fullmatch(root):
            raise AuditError(f"invalid proof module name {root!r}")
    if not names:
        raise AuditError("a sealed-field query needs at least one name")
    lines = [f"Require {root}.\n" for root in roots] + [SETTINGS]
    for name in names:
        lines += _assumption_block(name)
    return "".join(lines)


def sealed_field_assumptions(stdout: str, names: list[str]) -> dict[str, list[str]]:
    """Each queried name's assumption entries, empty where the compiler reports the
    name closed under the global context, read exactly as `assumptions` reads a proof
    module's: one complete framed answer per name, in order, or the reading is refused."""
    symbols: list[Symbol] = [{"name": name, "type": "", "assumptions": [], "claims": []}
                             for name in names]
    assumptions(stdout, symbols)
    return {symbol["name"]: symbol["assumptions"] for symbol in symbols}


def assumptions(stdout: str, symbols: list[Symbol]) -> None:
    """Require one complete native answer for every queried symbol, in order."""
    blocks: list[tuple[str, list[str]]] = []
    for line in stdout.splitlines():
        if line.startswith(MARKER):
            blocks.append((line[len(MARKER):], []))
        elif line.strip():
            if not blocks:
                raise AuditError(f"unframed assumption output: {line}")
            blocks[-1][1].append(line)
    if [name for name, _ in blocks] != [symbol["name"] for symbol in symbols]:
        raise AuditError("native assumption responses do not enumerate exactly the queries")
    for symbol, (_, lines) in zip(symbols, blocks, strict=True):
        if lines == ["Closed under the global context"]:
            continue
        if not lines or lines[0] != "Axioms:" or len(lines) < 2:
            raise AuditError(f"{symbol['name']} has an incomplete assumption response")
        entries: list[str] = []
        for line in lines[1:]:
            if line[:1].isspace() and entries:
                entries[-1] += " " + line.strip()
            elif ":" in line:
                entries.append(line.strip())
            else:
                raise AuditError(f"unrecognized assumption entry: {line}")
        if not entries:
            raise AuditError(f"{symbol['name']} has an empty Axioms block")
        symbol["assumptions"] = entries


def kernel_context(summary: str) -> list[str]:
    """The axioms `rocqchk -o` names, refusing every other assumption it reports.

    The summary covers the whole environment the checker loaded, admitted and `-norec`
    modules included, so an axiom that is loaded but never used is named as well. It is
    read independently of Print Assumptions, and it does not report definitional UIP,
    which the Print Assumptions audit does. rocqchk writes the summary to stderr, and
    nothing else may appear there: an unrecognized line refuses the run. The summary
    must end with KERNEL_INDICES; its entries must be qualified names, and they are
    accepted because they rely only on the theory the checker profile fixes.
    """
    lines = [line.rstrip() for line in summary.splitlines() if line.strip()]
    if tuple(lines[:2]) != KERNEL_CONTEXT:
        raise AuditError("rocqchk printed no context summary")
    sections: list[tuple[str, str, list[str]]] = []
    for line in lines[2:]:
        if line.startswith("* ") and ":" in line:
            key, _, value = line[2:].partition(":")
            sections.append((key, value.strip(), []))
        elif line[:1].isspace() and sections and not sections[-1][1]:
            sections[-1][2].append(line.strip())
        else:
            raise AuditError(f"unrecognized kernel context line: {line}")
    keys = [key for key, _, _ in sections]
    expected = ["Theory", "Theory", "Axioms", *KERNEL_UNSAFE]
    if keys != [*expected, KERNEL_INDICES]:
        raise AuditError("unrecognized kernel context sections: " + ", ".join(keys))
    theory = tuple(value for key, value, _ in sections[:2])
    if theory != KERNEL_THEORY:
        raise AuditError("the kernel checked a non-default theory: " + "; ".join(theory))
    for key, value, entries in sections[3:len(expected)]:
        if value != "<none>" or entries:
            raise AuditError(f"{key}: {', '.join(entries) or value}")
    _, value, axioms = sections[2]
    if (value == "<none>") == bool(axioms) or value not in ("", "<none>"):
        raise AuditError(f"malformed kernel axiom list: {value or 'empty'}")
    for _, value, inductives in sections[len(expected):]:
        if ((value == "<none>") == bool(inductives) or value not in ("", "<none>")
                or not all(QUALIFIED.fullmatch(name) for name in inductives)):
            raise AuditError(f"malformed kernel indices list: "
                             f"{', '.join(inductives) or value or 'empty'}")
    return axioms


def pinned_overrides(text: str) -> list[str]:
    """Sentences that would change a gate-pinned setting for their own source.

    The shared lexer reads a comment as the separator Rocq's lexer reads it as, so
    `timeout(* c *)5` is the word and its argument, and ends a sentence only outside a
    string literal, so a quoted full stop hides no command. The tactical reading empties
    each sentence's string literals, so a quoted tactic is not read as code. Each
    sentence is reported once, as written.
    """
    tactical = "timeout" in text or "alloc_limit" in text
    return [sentence for sentence in sentences(text)
            if _PINNED.match(sentence) or _PINNED_ATTRIBUTE.search(sentence)
            or _TIMEOUT.match(sentence)
            or (tactical and _TACTICAL.search(_STRING.sub('""', sentence)))]


def dynamic_sources(text: str) -> list[str]:
    """Sentences that load a file, a plugin or a plugin's primitive into the compile.

    What one loads passes every other refusal here unread: `Load` of a file outside
    `proofs/` compiles with a pinned setting on and the pinned reading sees none of it,
    and an Ltac2 external binds the timeout tactical under a name no word list can
    follow. So each is refused before compilation, and the gate also withdraws cache
    reuse for it. The head is read after the control prefixes, as every head reading
    here is.
    """
    return [sentence for sentence in sentences(text) if DYNAMIC_SOURCE.match(sentence)]


# The words that write a coinductive type or a cofixpoint (coinductive_forms), each read
# where it stands as a token of its own: the pinned Rocq 9.3.0 runs `do 1cofix H` as the
# cofix tactic, and `#_cofix H` too once a notation declares `#_`. Each word begins with a
# hexadecimal digit, so `0x1cofix` is `0x1c` and then `ofix`, and once a notation declares
# `#0`, the lexer reads `#00x1p5cofix` as `#0`, `0x1p5` and `cofix`.
_COINDUCTIVE = re.compile(_APART + r"(?:CoInductive|CoFixpoint|CoFix|cofix_|cofix)"
                          rf"(?![{_WORD}])")
# A declared token hides a word from that reading when Rocq's lexer reads the token through
# its keyword table, not as an identifier, and its trailing ASCII letters, digits, quotes
# and underscores hold a letter. The lexer ends such a token where the reading is still
# inside a word, and a word may follow it there, directly or after a numeral or a quote:
# the pinned Rocq 9.3.0 runs `#a1cofix H` as `cofix H` once a tactic notation declares
# `#a1`, and as `do 1 (cofix H)` once one declares `#a` with a count. Tactic and Ltac2
# notations take each string as one terminal, its blanks removed. Every other notation
# command declares its terminals in its first string, as its blank-separated parts, a
# part quoted at both ends read inside its quotes. An ASCII identifier among them names a
# variable or is read whole, as any identifier is.
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
_HIDING_TAIL = re.compile(rf"[A-Za-z][{_WORD}]*\Z")
_WHOLE_TERMINALS = re.compile(r"(?<![\w'])(?:Tactic|Ltac2)\s+Notation(?![\w'])")


def coinductive_forms(text: str) -> list[str]:
    """Sentences that write a coinductive type or a cofixpoint, whose guard check the
    locked kernel gets wrong, or that declare a token able to hide one from this reading.

    Rocq 9.3.0's cofixpoint guard checker computes a cofixpoint's recursive tree in the
    wrong environment (rocq#22386) and checks nested mutual cofixpoints against one tree
    (rocq#22389). Rocq's critical-bug list records `rocqchk` affected alike, so neither
    the kernel recheck nor the assumption audit is taken as a cover. `CoInductive`,
    `CoFixpoint` and `cofix`, which is Rocq's term binder, Ltac tactic and reduction flag,
    write one, and so do Ltac2's `Std.cofix_` tactic and its `Constr.Unsafe.CoFix`
    constructor. So each is refused wherever Rocq's lexer can read it as a word of its own,
    qualified or not, `Let CoFixpoint`, a Search filter `is:CoFixpoint`, the forms under
    `Fail` or `Succeed` and a word after a numeral, a quote or an underscore among them. A
    Gallina identifier spelled as one is refused too, which is loud and costs a rename, as
    the tactical refusal refuses `timeout`, and so is one holding a word after only quotes,
    underscores and numerals, such as `_cofix`; any other identifier that contains one,
    `is_cofix` or `cofix'` among them, is read whole. A comment separates, so
    `co(* c *)fix` is two words, and string literals are emptied first.

    Rocq's lexer can also end a token from its keyword table inside what this reading
    takes for one word, so the declaration of each token that would hide a word that way is
    refused in every source, whether or not that source writes a word: another source may
    Require it and write one. The tokens a dependency declares stay outside this reading,
    Stdlib's `+c` among them: the pinned Rocq 9.3.0 reads `+c1cofix` as `+c`, `1` and
    `cofix`. [The lock guide](../opam/README.md) records that residue and the lock move
    that retires the refusal.
    """
    words = "cofix" in text or "CoFix" in text or "CoInductive" in text
    declares = "Notation" in text or "Infix" in text
    if not words and not declares:
        return []
    return [sentence for sentence in sentences(text)
            if (words and _COINDUCTIVE.search(_STRING.sub('""', sentence)))
            or (declares and any(map(_hides, _declared_terminals(sentence))))]


def _declared_terminals(sentence: str) -> list[str]:
    """The terminals a notation command declares, each as Rocq's lexer adds it."""
    emptied = _STRING.sub('""', sentence)
    if not _DECLARES_TOKENS.search(emptied):
        return []
    whole = _WHOLE_TERMINALS.search(emptied)
    found: list[str] = []
    for part in _TOKEN_SOURCE.finditer(sentence):
        if part.group() == ":=":
            break
        literal = part.group(1)
        if literal is None:
            continue
        found += [_unquote(piece) for piece in literal.split()]
        if not whole:
            break
        found.append(literal.replace(" ", ""))
    return found


def _unquote(piece: str) -> str:
    """A notation string's part as a terminal: inside its quotes when quoted at both ends."""
    return piece[1:-1] if len(piece) > 2 and piece[0] == piece[-1] == "'" else piece


def _hides(terminal: str) -> bool:
    """Whether the lexer can end this terminal where the reading is still inside a word."""
    return not _IDENTIFIER.fullmatch(terminal) and bool(_HIDING_TAIL.search(terminal))


def unreadable_tokens(text: str) -> list[str]:
    """Sentences declaring a token the shared lexer would not read as Rocq's lexer does.

    Such a token holds a quote or a comment opener, or a full stop at which the sentence
    split would end a sentence Rocq continues, `.` and `...` among them. Until one is
    declared, the shared lexer finds every string, comment and sentence end Rocq's does,
    the installed libraries declaring no such token, so it reads the declaring sentence
    as Rocq does. Refusing that sentence before compilation keeps every other lexical
    reading here sound. A declaration's tokens are its strings' blank-separated parts, a
    quoted part's quotes aside.
    """
    found: list[str] = []
    for sentence in sentences(text):
        if not _DECLARES_TOKENS.search(_STRING.sub('""', sentence)):
            continue
        for part in _TOKEN_SOURCE.finditer(sentence):
            if part.group() == ":=":
                break
            if part.group(1) is not None and _unreadable(part.group(1)):
                found.append(sentence)
                break
    return found


def _unreadable(literal: str) -> bool:
    """Whether a declaring string literal, doubled quotes as written, holds such a token."""
    return ('"' in literal or "(*" in literal
            or any(SENTENCE_END.search(part.strip("'")) for part in literal.split()))


def unsupported_abstractions(text: str) -> list[str]:
    """Reject inaccessible module bodies instead of claiming a partial inventory.

    Ordinary nested modules and generated obligations are supported. Functors and
    sealed signatures need a module-body audit, since Search cannot enumerate their
    inaccessible constants. They are not present in the shipped proof tree. The head is
    read after the control prefixes, whose own brackets and colons are not a functor's
    parameters or a signature's ascription: the pinned Rocq 9.3.0 compiles
    `Time Module Type` and `Time Declare Module`.
    """
    found: list[str] = []
    for sentence in sentences(text):
        module = _MODULE.match(sentence)
        if module is None:
            continue
        declared, signature = module.groups()
        header = sentence[module.end():].split(":=", 1)[0]
        if declared or signature or "(" in header or ":" in header:
            found.append(sentence)
    return found
