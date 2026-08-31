# SPDX-License-Identifier: Apache-2.0
"""counts, the shipped configurations: one model, handed different files.

There is exactly one Sail model, parameterized by core class, and a V-class or an RoT
emulator is that model handed another configuration rather than a second model. Two
rules stand on that: each file differs from the primary in exactly the keys its own
row declares, and a file composing a hart on a vectorless class names no vector
extension. The first compares the shipped files to each other, the second holds one
file against the model's own extension registry, and neither can see what the other
does.
"""

import re
from typing import TYPE_CHECKING

from vos import config, coreclass

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

# The configurations this tree ships. The first is the primary and every other is read
# against it, each with the keys it is *allowed* to differ in.
#
# Both halves are enumerations rather than patterns on purpose. A further configuration
# is a row here, which is the point at which somebody decides what it is a configuration
# *of*; a further divergent key is the point at which somebody decides whether that file
# still describes the same machine or has quietly become another one.
#
# **The divergence set is per file and not global, and the RoT row is why.** The V-class
# configuration is the primary with the two keys naming which core it composes moved
# (M0.8b). The RoT configuration is the primary with twelve moved, and eleven of the
# twelve are *forced* by a validator clause rather than chosen: a class with no vector
# geometry is refused any `support_level` but `Disabled`, a disabled vector unit is
# refused any `vs_legal_states` but `ExtContext_Off`, each config-gated vector-crypto
# flag is refused by name while `Zve32x` is unavailable, and the element width and index
# width are constrained at or below the vector length above them
# (model/model/postlude/validate_config.sail). One global tuple applied to both rows
# cannot state that: it would either license the RoT's eleven on the V pair, where each
# would be a second machine, or refuse them on the RoT pair, where each is the only value
# the model admits.
SHIPPED_PRIMARY = "model/config/verifiedos.json"

CONFIG_DIVERGENCE: dict[str, tuple[str, ...]] = {
    "model/config/verifiedos-v.json": (
        "platform.hartid",
        "extensions.V.vlen_exp",
    ),
    "model/config/verifiedos-rot.json": (
        "platform.hartid",
        "base.mstatus.vs_legal_states",
        "extensions.V.support_level",
        "extensions.V.vlen_exp",
        "extensions.V.elen_exp",
        "extensions.V.max_index_eew_exp",
        "extensions.Zvbb.supported",
        "extensions.Zvbc.supported",
        "extensions.Zvkg.supported",
        "extensions.Zvkned.supported",
        "extensions.Zvknhb.supported",
        "extensions.Zvkt.supported",
    ),
}

SHIPPED_CONFIGS = (SHIPPED_PRIMARY, *CONFIG_DIVERGENCE)


def shipped_configurations(ctx: Context) -> None:
    """K-65: every shipped configuration is a configuration and not a fork.

    There is exactly one Sail model, parameterized by core class, and a V-class or an
    RoT emulator is that model handed a different configuration rather than a second
    model (R-15-005, M0.8b, M3.1). What makes the claim true is that each file differs
    from the primary in exactly the keys its own row declares and in nothing else, and
    that each of those keys actually differs.

    Nothing else holds them together. The model's own validator refuses a configuration
    whose roster puts the composed hart on a class whose declared geometry is not the
    one the run realizes, but it sees one file at a time and only when a run happens
    (postlude/validate_config.sail), and no build loop here hands it anything but the
    primary; `run.py model config-keys` compares a configuration against the *generated* one
    and answers about keys rather than values. So each non-primary file is a
    six-hundred-line near-copy with no instrument over the copying, which is the
    two-copies-of-one-fact defect this checker exists to catch, sitting inside the
    artifact it checks.

    The divergent keys are held in **both** directions. A key that drifted makes the file
    a different machine; a declared-divergent key that stopped diverging makes it a
    second *copy* of the primary, and the evidence measured against it would be evidence
    about the C class under another name.

    And with more than two files a third failure becomes possible that no pair against
    the primary can see: two non-primary configurations naming one core. Each may diverge
    from the primary in `platform.hartid` and still agree with the other, which is the
    same defect one level up from a divergent key that stopped diverging, so the composed
    identities are held distinct across the whole set.
    """
    rep = ctx.rep
    findings: list[str] = []
    tables = {rel: config.flat_of(ctx.root / rel) for rel in SHIPPED_CONFIGS}
    primary = tables[SHIPPED_PRIMARY]

    findings += [f"{rel} is not there or no longer parses as the model's configuration "
                 f"dialect"
                 for rel, table in tables.items() if not table]

    for rel, allowed in CONFIG_DIVERGENCE.items():
        second = tables[rel]
        if not primary or not second:
            continue
        findings += [f"{rel} does not declare {key}, which {SHIPPED_PRIMARY} does"
                     for key in sorted(set(primary) - set(second))]
        findings += [f"{rel} declares {key}, which {SHIPPED_PRIMARY} does not"
                     for key in sorted(set(second) - set(primary))]
        findings += [f"{rel} disagrees with {SHIPPED_PRIMARY} on {key}, which is not one "
                     f"of the {len(allowed)} keys its own row declares it may differ in"
                     for key in sorted(set(primary) & set(second))
                     if primary[key] != second[key] and key not in allowed]
        findings += [f"{key} is declared as a divergence of {rel} and does not diverge, "
                     f"so that file describes the same machine as {SHIPPED_PRIMARY}"
                     for key in allowed
                     if key in primary and key in second
                     and primary[key] == second[key]]

    composed: dict[object, list[str]] = {}
    for rel, table in tables.items():
        if table and "platform.hartid" in table:
            composed.setdefault(table["platform.hartid"], []).append(rel)
    findings += [f"{' and '.join(sorted(rels))} compose hart {hart}; each shipped "
                 f"configuration is a different core of the one composed roster"
                 for hart, rels in sorted(composed.items(), key=lambda kv: str(kv[0]))
                 if len(rels) > 1]

    # Leaf paths rather than every key path, which is what `keys` counts and what
    # `run.py model config-keys` reports: the question here is what the files *say*, so the
    # figure is the values compared and not the surface declaring them.
    ctx.shared["shipped_config_values"] = len(primary)
    rep.report("K-65", "shipped configuration(s) that are not one model's:", findings,
               f"the {len(SHIPPED_CONFIGS)} shipped configurations state the same "
               f"{len(primary)} values, each differing from the primary in exactly the "
               "keys its own row declares, and each composing a different core")


def vectorless_configurations(ctx: Context) -> None:
    """K-78: a vectorless composition names no vector extension.

    The composed hart's class decides whether a configuration is a configuration of a
    core with a vector unit: `platform.hartid` indexes `platform.core_roster`, and a
    zero `vlen_exp` in that hart's class row is the table's way of saying the core has
    none (R-15-052b, R-15-113). The generated `riscv,isa` string and the
    `riscv,isa-extensions` array of the **attested** devicetree are built from
    `hartSupports`, so an extension that reads true there is a standards-track name in
    an artifact a relying party appraises the part from (R-15-126).

    **The `Zvl` ladder is the rung that reaches that artifact without a key.** Every
    other vector row in the registry is gated on a `supported` key or on the vector
    support level, so a composition turning its vector unit off is refused each of them
    by name at load; the minimum-vector-length rungs are gated on `sizeof(vlen_exp)`
    **alone**, and `vlen_exp` is type-level and constrained `3 <= vlen_exp <= 16`
    (core/vlen.sail), so it cannot be set to zero to mean vectorless. A vectorless
    composition left at a vector-bearing class's exponent therefore validated, ran, and
    emitted four minimum-vector-length extensions it does not implement.

    The model now refuses that at load, and this rule is why refusing it at load is not
    enough: the validator sees one file at a time and only when a run happens, and no
    loop in this repository hands it anything but the primary configuration, so the file
    the defect belongs to is the one nothing runs. That is K-65's own ground, one
    artifact over: K-65 compares the shipped files to each other and would be *satisfied*
    by a vectorless file that had never moved its exponent at all, the exponent then
    agreeing with the primary rather than diverging from it.

    Both readings are the model's own rather than transcriptions: the rungs and their
    thresholds and the config-gated vector extensions and their keys are parsed out of
    the extension registry (vos/coreclass.py), so a rung re-based or a flag added joins
    the rule rather than waiting to be copied into it. A registry this rule cannot read
    yields no rungs, which the floors group reports rather than passing over.
    """
    rep = ctx.rep
    findings: list[str] = []
    bundle = ctx.shared.get("bundle")
    rungs = coreclass.zvl_rungs(bundle)
    gated = coreclass.config_gated_vector_extensions(bundle)
    ctx.shared["zvl_rungs"] = len(rungs)
    vectorless = 0

    for rel in SHIPPED_CONFIGS:
        path = ctx.root / rel
        placed = coreclass.composed(path)
        if placed is None:
            findings.append(f"{rel} does not name its own composed hart in its core "
                            f"roster, so which class it composes cannot be decided")
            continue
        name, class_exp = placed
        if class_exp:
            continue
        vectorless += 1

        level = config.value(path, "extensions", "V", "support_level")
        if level != "Disabled":
            findings.append(f"{rel} composes a hart on the vectorless {name} class and "
                            f"declares `extensions.V.support_level` {level!r}")

        exp = config.integer(path, "extensions", "V", "vlen_exp")
        if exp is None:
            findings.append(f"{rel} declares no `extensions.V.vlen_exp`")
        else:
            findings += [f"{rel} composes a hart on the vectorless {name} class at "
                         f"`extensions.V.vlen_exp` {exp}, which is at or above "
                         f"{rung}'s threshold of {need}, so its attested `riscv,isa` "
                         f"string names a vector extension it does not implement"
                         for rung, need in sorted(rungs.items(), key=lambda kv: kv[1])
                         if exp >= need]

        findings += [f"{rel} composes a hart on the vectorless {name} class and leaves "
                     f"`{key}` true, so {ext} reads supported on a core with no vector "
                     f"register file"
                     for ext, key in sorted(gated.items())
                     if config.value(path, *key.split(".")) is True]

    rep.report("K-78", "vectorless composition(s) naming a vector extension:", findings,
               f"the {vectorless} shipped configuration(s) composing a hart on a "
               f"vectorless class clear all {len(gated)} config-gated vector extensions "
               f"and sit below all {len(rungs)} minimum-vector-length rungs")


# The exclusion row of the profile's §6 that names its extensions inline rather than one
# per row: the names are the backticked tokens on the row whose text says the exclusion
# is by name rather than by silence (R-15-048a).
BY_NAME_ROW_RE = re.compile(r"(?m)^\|([^|\n]*)\|[^|\n]*excluded \*\*by name rather than "
                            r"by silence\*\*")
BACKTICKED_RE = re.compile(r"`(\w+)`")
PROFILE = "docs/isa-profile.md"


def excluded_by_name_keys(ctx: Context) -> None:
    """K-87: an extension excluded by name reads false wherever a key still carries it.

    Two kinds of exclusion look identical from the profile and are not the same fact.
    Most excluded extensions are absent from the model: the surface was deleted, so the
    exclusion is a **shape** of the tree and nothing can turn it back on. A few are still
    implemented and switched off by a `supported` key reading false in every shipped
    configuration, so the exclusion is a **setting**, and a setting is undone by editing
    a file that no review gate reads. `Zbc` and `Zicclsm` are the two today, and no
    artifact said which kind either was: the profile writes both sorts of row the same
    way, and M0.19 recorded the distinction in a completion note where no rule reads it.

    K-66 is the neighbour and cannot see this. It holds that no name the exclusion rows
    spell is spelled back by the model's assembly clauses or carried by the corpus
    assembler, which is exactly the *shape* half; an extension whose clauses are still in
    the tree behind a false key is, to that rule, an excluded name whose clauses it finds
    and reports. So the two rules partition the exclusion set rather than overlapping on
    it, and this one takes the half K-66's own reading has to leave alone.

    Both readings are the artifacts' own. The excluded names are the backticked tokens on
    the profile row that says the exclusion is by name; the gated extensions and their key
    paths are parsed out of the model's extension registry, so a flag added upstream joins
    the rule rather than waiting to be transcribed. The intersection is what this decides
    about, and it is deliberately narrow: an excluded name the registry does not gate is
    outside the rule rather than passing it, that being K-66's subject.

    Fail-closed on the reading, on K-67's and K-75's ground: an absent profile, a §6 that
    yields no by-name row, and a registry that yields no gated extension are each a
    finding rather than a comparison made against nothing.
    """
    rep = ctx.rep
    findings: list[str] = []
    path = ctx.root / PROFILE
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not text:
        rep.report("K-87", "missing artifact:", [f"{PROFILE} is not in the repository"],
                   "")
        return

    rows = BY_NAME_ROW_RE.findall(text)
    excluded = {name for row in rows for name in BACKTICKED_RE.findall(row)}
    gated = coreclass.config_gated_extensions(ctx.shared.get("bundle"))
    if not rows:
        findings.append(f"{PROFILE} carries no row declaring an exclusion by name, so "
                        "the set this rule decides about cannot be read")
    if not gated:
        findings.append("the model's extension registry yields no config-gated "
                        "extension, so no exclusion can be placed as a setting")

    carried = sorted(excluded & gated.keys())
    for ext in carried:
        key = gated[ext]
        for rel in SHIPPED_CONFIGS:
            value = config.value(ctx.root / rel, *key.split("."))
            if value is None:
                findings.append(f"{rel} declares no `{key}`, so {ext}'s exclusion rests "
                                f"on a key that file does not carry")
            elif value is not True:
                continue
            else:
                findings.append(f"{rel} leaves `{key}` true, so {ext} reads supported on "
                                f"a machine the profile excludes it from by name")

    ctx.shared["excluded_by_name_gated"] = len(carried)
    rep.report("K-87", "excluded-by-name extension(s) a configuration still switches on:",
               findings,
               f"each of the {len(carried)} extensions the profile excludes by name and "
               f"the model still gates on a key reads false in all "
               f"{len(SHIPPED_CONFIGS)} shipped configurations")
