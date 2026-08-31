# SPDX-License-Identifier: Apache-2.0
"""The encoder table's generator: what it reaches, and what it refuses.

[test_dialect.py](test_dialect.py) pins the words the table encodes and this pins the
*reasoning* that produced them, which is the half a golden word cannot see: a generator
goes wrong by a rule rather than a row, and a rule wrong about admission moves five
hundred rows at once with every word it still carries unchanged.

Four questions, and each names the defect it exists to catch.

- **Does the admission refuse what the model cannot decode?** The model spells a load
  `"l" ^ width_mnemonic(width) ^ maybe_u(is_unsigned)` and rules out the unsigned
  doubleword in the `encdec` guard, so an enumeration hands back `ldu` and an assembler
  that carried it would lay down a word the machine traps.
- **Does it refuse what the shipped configurations switch off, and only that?** `clmulr`
  is guarded on `Zbc` alone, which is off; `clmul` and `clmulh` are `Zbc | Zbkc` and
  `Zbkc` is on. The transcription this replaced excluded exactly those three by hand,
  and the generator reproduces the split without being told about it.
- **Is an unreadable guard fail-closed?** An assembler refuses what it cannot show the
  model decodes, because a mnemonic refused is a program that does not assemble at the
  line that wrote it and a mnemonic wrongly admitted is an image that loads and traps
  somewhere else entirely.
- **Does every row's placement partition the word?** This is the invariant behind every
  golden word at once: a field the mnemonic decided but the encoding left free leaves two
  mnemonics sharing an encoding, and a field the encoding places that nothing prints
  leaves bits no operand can set.
"""

from pathlib import Path
from typing import Final

from tests.harness import Case, ensure
from vos import corpus, dialect, dialectgen, encdec, sailbundle, sailexpr

_ROOT: Final[Path] = corpus.find_root(Path(__file__).resolve())


def _surface() -> tuple[sailbundle.Bundle, encdec.Surface]:
    bundle = sailbundle.load(_ROOT)
    if bundle is None:
        raise AssertionError(f"{sailbundle.BUNDLE} is not in this checkout, so nothing "
                             f"here decides anything")
    return bundle, encdec.Surface(bundle)


def _over_approximates() -> None:
    """The parse spells `ldu` and the policy refuses it, which is the whole shape of
    this pair: the join reads what the clauses *spell* and the admission decides what
    an assembler may emit."""
    _bundle, surface = _surface()
    forms, _residue = surface.forms()
    spelled = {form.mnemonic for form in forms}
    ensure("ldu" in spelled,
           "the join no longer spells `ldu`, so the over-approximation this pair is "
           "built around has moved and the refusal below proves nothing")
    ensure("ldu" not in dialect.TABLE,
           "`ldu` is in the encoder table: the model decodes it nowhere, its clause "
           "ruling out the unsigned doubleword in `valid_load_encdec`")


def _extension_split() -> None:
    ensure("clmulr" not in dialect.TABLE,
           "`clmulr` is guarded on Ext_Zbc alone, which no shipped configuration "
           "supports, so the table may not carry it")
    for name in ("clmul", "clmulh"):
        ensure(name in dialect.TABLE,
               f"`{name}` is guarded `Zbc | Zbkc` and Zbkc is supported, so the table "
               f"must carry it")


def _unknown_guard_refuses() -> None:
    """A guard naming something the model does not define admits nothing.

    Seeded rather than argued about: the failure this guards against is silent, an
    unreadable guard read as *admits* putting a form in the table with no evidence at
    all behind it.
    """
    bundle, surface = _surface()
    forms, _residue = surface.forms()
    facts = dialectgen.Facts(bundle, _ROOT)
    row = next(form for form in forms if form.mnemonic == "add")
    invented = encdec.Form(
        mnemonic=row.mnemonic, ctor=row.ctor, site=row.site, word=row.word,
        mask=row.mask, guard="thereIsNoSuchPredicate(rs1)", operands=row.operands,
        syntax=row.syntax, bindings=row.bindings)
    try:
        dialectgen.admit(invented, facts)
    except (dialectgen.RefusedError, sailexpr.UnresolvedError):
        return
    raise AssertionError("a guard this reader cannot resolve admitted a form: the "
                         "policy is fail-closed and this is the case that says so")


def _placement_partitions_the_word() -> None:
    reached = 0
    for mnemonic, row in dialect.TABLE.items():
        bits = row.mask
        for slot in row.slots:
            for word_hi, word_lo, _src_hi, _src_lo in slot.pieces:
                run = ((1 << (word_hi - word_lo + 1)) - 1) << word_lo
                ensure(not bits & run,
                       f"{mnemonic}'s {slot.name} overlaps a bit the encoding fixes "
                       f"or another operand already reaches")
                bits |= run
        ensure(bits == (1 << 32) - 1,
               f"{mnemonic} leaves {((1 << 32) - 1) & ~bits:#010x} decided by nothing")
        ensure(not row.word & ~row.mask,
               f"{mnemonic}'s constant sets a bit its mask does not claim")
        reached += 1
    ensure(reached == len(dialect.TABLE),
           f"only {reached} of {len(dialect.TABLE)} rows were read")


def _constants_survive_encoding() -> None:
    """Every row's fixed bits are the bits `encode` lays down for it.

    The bridge between the artifact and the encoder that reads it: a loader that dropped
    a slot, or an encoder that shifted one, would leave the table and the words it
    produces disagreeing with nothing to notice.
    """
    for mnemonic, row in dialect.TABLE.items():
        operands = [0] * len(row.slots)
        try:
            word = dialect.encode(mnemonic, operands, 0)
        except dialect.AsmError:
            # A row whose guard forbids a zero operand (`lc` into the null register)
            # says so at the site, which is the requirement doing its job.
            continue
        ensure(word & row.mask == row.word,
               f"{mnemonic} encodes {word:#010x}, whose fixed bits are "
               f"{word & row.mask:#010x} against the row's {row.word:#010x}")


def _requirements_are_the_model_s_guards() -> None:
    """The two one-off rules the transcription carried are the clause now."""
    wanted = {
        "lc": ("ne", "cd", (0,), "cd != zreg"),
        "vkeccak.vi": ("in", "rnd", (12, 24), "keccak_valid_rounds(rnd)"),
    }
    for mnemonic, (kind, operand, values, fragment) in wanted.items():
        row = dialect.TABLE[mnemonic]
        found = [r for r in row.requires if r.operand == operand]
        ensure(len(found) == 1,
               f"{mnemonic} carries {len(found)} requirement(s) on {operand}, wanted 1")
        ensure(found[0].kind == kind and found[0].values == values,
               f"{mnemonic}'s requirement is {found[0]}, wanted {kind} {values}")
        ensure(fragment in found[0].guard,
               f"{mnemonic}'s requirement quotes {found[0].guard!r}, which does not "
               f"name the model's own {fragment!r}")


def _three_valued_evaluation() -> None:
    """`UNKNOWN` is machine state and an unresolved name is a defect in the reader, and
    the two must not collapse: a caller reading them as one admits an encoding on the
    strength of a typo."""
    bundle, _unused = _surface()
    facts = dialectgen.Facts(bundle, _ROOT)
    env = dialectgen._Model(facts)
    unknown = sailexpr.evaluate(sailexpr.parse("currentlyEnabled(Ext_M)"), env)
    ensure(unknown is sailexpr.UNKNOWN,
           f"Ext_M's enablement is a CSR, so it is machine state, got {unknown!r}")
    decided = sailexpr.evaluate(sailexpr.parse("hartSupports(Ext_Zbc)"), env)
    ensure(decided is False,
           f"no shipped configuration supports Zbc, got {decided!r}")
    try:
        sailexpr.evaluate(sailexpr.parse("noSuchName"), env)
    except sailexpr.UnresolvedError:
        return
    raise AssertionError("an undefined name answered instead of raising")


def _artifact_is_what_the_generator_writes() -> None:
    """The tracked artifact against its generator, which is K-88's own claim.

    Held here as well as at the gate, because the two answer different questions: the
    gate decides about the tree as it stands and this decides that the generator is
    deterministic, a run over one bundle twice writing one file.
    """
    bundle, _unused = _surface()
    first = dialectgen.emit(bundle, _ROOT)
    second = dialectgen.emit(bundle, _ROOT)
    ensure(first == second,
           "two runs of the generator over one bundle wrote different bytes")
    tracked = (_ROOT / dialectgen.TABLE).read_text(encoding="utf-8")
    ensure(first == tracked,
           f"the tracked artifact is {len(tracked)} bytes and the generator writes "
           f"{len(first)}: run `python tools/run.py check --fix`")


def cases() -> list[Case]:
    return [
        Case("over-approximates-and-refuses", _over_approximates),
        Case("extension-split", _extension_split),
        Case("unknown-guard-refuses", _unknown_guard_refuses),
        Case("placement-partitions-the-word", _placement_partitions_the_word),
        Case("constants-survive-encoding", _constants_survive_encoding),
        Case("requirements-are-the-models-guards", _requirements_are_the_model_s_guards),
        Case("three-valued-evaluation", _three_valued_evaluation),
        Case("artifact-is-what-the-generator-writes",
             _artifact_is_what_the_generator_writes),
    ]
