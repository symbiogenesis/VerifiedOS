# SPDX-License-Identifier: Apache-2.0
"""Check shipped Sail configuration files, vectorless compositions, MMIO apertures, excluded-by-name extensions, and IO-memory executability (`K-65`, `K-78`, `K-87`, `K-94`, `K-101`)."""

import re
from typing import TYPE_CHECKING

from vos import config, coreclass

if TYPE_CHECKING:
    from . import Context

# Shipped configurations: `SHIPPED_PRIMARY` is the reference configuration, and
# `CONFIG_DIVERGENCE` lists the exact leaf keys each non-primary configuration must
# differ in (11 of the 12 RoT divergences are forced by `validate_config.sail` when
# `extensions.V.support_level` is `Disabled`).
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
    """K-65: every shipped configuration differs from the primary in its declared keys only and composes a distinct hart.

    Checks that every file in `SHIPPED_CONFIGS` declares the exact same leaf key set as
    `SHIPPED_PRIMARY`, differs from `SHIPPED_PRIMARY` on every key in its
    `CONFIG_DIVERGENCE` tuple and on no other key, and selects a distinct
    `platform.hartid` across the set (`R-15-005`).
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

    ctx.shared["shipped_config_values"] = len(primary)
    rep.report("K-65", "shipped configuration(s) that are not one model's:", findings,
               f"the {len(SHIPPED_CONFIGS)} shipped configurations state the same "
               f"{len(primary)} values, each differing from the primary in exactly the "
               "keys its own row declares, and each composing a different core")


def vectorless_configurations(ctx: Context) -> None:
    """K-78: shipped configurations whose composed hart sits on a vectorless class enable no vector extension.

    For every shipped configuration whose `platform.hartid` indexes a core class with
    `vlen_exp == 0` (`R-15-052b`, `R-15-113`), checks that `extensions.V.support_level`
    is `"Disabled"`, `extensions.V.vlen_exp` sits below every `Zvl*b` rung threshold in
    [`zvl_rungs`](../coreclass.py#zvl_rungs) (`core/vlen.sail` constrains
    `3 <= vlen_exp <= 16`, so `Zvl*b` rungs are gated on `vlen_exp` alone), and every
    config-gated vector extension in
    [`config_gated_vector_extensions`](../coreclass.py#config_gated_vector_extensions)
    is `False`.
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


APERTURE_CONFIG = "model/model/core/platform_config.sail"
APERTURE_TREE = "model/model/postlude/device_tree.sail"
APERTURE_VALIDATOR = "model/model/postlude/validate_config.sail"

APERTURE_BASE_RE = re.compile(r"let\s+(plat_\w+_base)\s*:\s*physaddrbits\s*=\s*"
                              r"to_bits_checked\(config\s+(platform\.[\w.]+)\.base\s*:\s*int\)")
DTS_REG_RE = re.compile(r"generate_dts_reg\(\s*(plat_\w+_base)\s*,")
PMA_CALL_RE = re.compile(r'within_configured_pma_memory\("[^"]*",\s*(.*?)\);', re.DOTALL)
PLAT_BASE_RE = re.compile(r"plat_\w+_base")
APERTURE_ROW_RE = re.compile(r"aps\s*=\s*\(\s*\"[^\"]*\"\s*,\s*(plat_\w+_base)\s*,")


def aperture_placements(ctx: Context) -> None:
    """K-94: every enabled MMIO aperture in a shipped configuration is emitted in the devicetree, bounded in IO memory, and listed in whole-map disjointness.

    For every `platform.<name>` object with `supported == True` and a `base` key in
    `SHIPPED_CONFIGS`, checks across three Sail files (`R-15-002b`):
    1. [platform_config.sail](../../../model/model/core/platform_config.sail) binds
       `platform.<name>.base` to a `plat_*_base` identifier.
    2. [device_tree.sail](../../../model/model/postlude/device_tree.sail) passes that
       `plat_*_base` to `generate_dts_reg`.
    3. [validate_config.sail](../../../model/model/postlude/validate_config.sail) bounds
       it inside `Some(IOMemory)` via `within_configured_pma_memory` and includes it in
       the `declared_apertures` disjointness list.
    """
    rep = ctx.rep
    findings: list[str] = []
    texts: dict[str, str] = {}
    for rel in (APERTURE_CONFIG, APERTURE_TREE, APERTURE_VALIDATOR):
        path = ctx.root / rel
        texts[rel] = path.read_text(encoding="utf-8") if path.is_file() else ""
        if not texts[rel]:
            findings.append(f"{rel} is not in the repository, so the pairing between a "
                            f"declared aperture, its devicetree node and its validator "
                            f"clause cannot be read")

    bases = {key: ident
             for ident, key in APERTURE_BASE_RE.findall(texts[APERTURE_CONFIG])}
    if not bases:
        findings.append(f"{APERTURE_CONFIG} declares no aperture base, so no declared "
                        f"window has a name this rule could hold the other two files to")

    placed = set(DTS_REG_RE.findall(texts[APERTURE_TREE]))
    guarded: set[str] = set()
    for args in PMA_CALL_RE.findall(texts[APERTURE_VALIDATOR]):
        if "Some(IOMemory)" in args:
            guarded |= set(PLAT_BASE_RE.findall(args))
    listed = set(APERTURE_ROW_RE.findall(texts[APERTURE_VALIDATOR]))
    if not listed:
        findings.append(f"{APERTURE_VALIDATOR} carries no row in the form the whole-map "
                        f"check's list is written in, so no declared window has a row "
                        f"this rule could hold it to")

    declared = 0
    for rel in SHIPPED_CONFIGS:
        table = config.flat_of(ctx.root / rel)
        for key, value in sorted(table.items()):
            if not key.startswith("platform.") or not key.endswith(".supported"):
                continue
            name = key[: -len(".supported")]
            if value is not True or f"{name}.base" not in table:
                continue
            declared += 1
            ident = bases.get(name)
            if ident is None:
                findings.append(f"{rel} declares the aperture `{name}` and "
                                f"{APERTURE_CONFIG} reads no base for it, so the model "
                                f"has no name for where that window is")
                continue
            if ident not in placed:
                findings.append(f"{rel} declares the aperture `{name}` and "
                                f"{APERTURE_TREE} emits no node stating its window, so "
                                f"the attested devicetree does not carry the placement "
                                f"R-15-002b makes a constraint on it")
            if ident not in guarded:
                findings.append(f"{rel} declares the aperture `{name}` and "
                                f"{APERTURE_VALIDATOR} holds it inside no IO memory "
                                f"region, so a composition may place it in main memory "
                                f"or outside every region and nothing says so")
            if ident not in listed:
                findings.append(f"{rel} declares the aperture `{name}` and "
                                f"{APERTURE_VALIDATOR}'s whole-map list carries no row "
                                f"for it, so nothing holds that window apart from the "
                                f"others and two devices declared at one address both "
                                f"validate")

    ctx.shared["declared_apertures"] = declared
    rep.report("K-94", "declared aperture(s) the model does not place:", findings,
               f"each of the {declared} apertures the {len(SHIPPED_CONFIGS)} shipped "
               f"configurations declare carries a `reg` in the attested devicetree, a "
               f"validator clause holding it inside a configured IO memory region, and a "
               f"row in the list the whole-map check walks")


BY_NAME_ROW_RE = re.compile(r"(?m)^\|([^|\n]*)\|[^|\n]*excluded \*\*by name rather than "
                            r"by silence\*\*")
BACKTICKED_RE = re.compile(r"`(\w+)`")
PROFILE = "docs/hardware/isa-profile.md"


def excluded_by_name_keys(ctx: Context) -> None:
    """K-87: extensions excluded by name in [isa-profile.md](../../../docs/hardware/isa-profile.md) that remain config-gated in Sail are `False` in all shipped configurations.

    Complements `K-66` (which checks extensions removed from the Sail decode surface):
    when an extension excluded by name (`R-15-048a`) still has a `supported` key in
    [`config_gated_extensions`](../coreclass.py#config_gated_extensions), that key must
    be present and `False` across `SHIPPED_CONFIGS`.
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


# CMake configuration template (`@VARIABLE@` placeholders prevent JSON parsing).
CONFIG_TEMPLATE = "model/config/config.json.in"
TEMPLATE_REGION_RE = re.compile(r'"mem_type"\s*:\s*"(\w+)"(?:(?!"mem_type").)*?'
                                r'"executable"\s*:\s*(true|false)', re.DOTALL)
TEMPLATE_TYPE_RE = re.compile(r'"mem_type"\s*:')

MEM_TYPES = ("IOMemory", "MainMemory")


def device_region_executability(ctx: Context) -> None:
    """K-101: no `IOMemory` region in `SHIPPED_CONFIGS` or `model/config/config.json.in` has `executable: true`.

    Checks the forward implication (`IOMemory => not executable`) across every region in
    `SHIPPED_CONFIGS` and `CONFIG_TEMPLATE`; the converse is not required because
    non-executable `MainMemory` regions (such as data scratchpads under `R-15-167` /
    `R-18-009`) are valid.
    """
    rep = ctx.rep
    findings: list[str] = []
    read: list[tuple[str, str, bool]] = []

    for rel in SHIPPED_CONFIGS:
        regions = config.value(ctx.root / rel, "memory", "regions")
        if not isinstance(regions, list) or not regions:
            findings.append(f"{rel} states no `memory.regions` this rule can read, so no "
                            f"region it declares is held against the fetch gate")
            continue
        for index, region in enumerate(regions):
            where = f"{rel}'s `memory.regions[{index}]`"
            attributes = region.get("attributes") if isinstance(region, dict) else None
            if not isinstance(attributes, dict):
                findings.append(f"{where} declares no attributes, so its memory type and "
                                f"its executability cannot be read together")
                continue
            kind, executable = attributes.get("mem_type"), attributes.get("executable")
            if not isinstance(kind, str) or kind not in MEM_TYPES:
                findings.append(f"{where} is typed {kind!r}, which is neither of the two "
                                f"kinds a region is, so whether it is a device endpoint "
                                f"cannot be decided")
                continue
            if not isinstance(executable, bool):
                findings.append(f"{where} states no boolean `executable`, so what "
                                f"`pmaCheck` admits a fetch to it on is undecided")
                continue
            read.append((where, kind, executable))

    path = ctx.root / CONFIG_TEMPLATE
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    pairs = TEMPLATE_REGION_RE.findall(text)
    typed = len(TEMPLATE_TYPE_RE.findall(text))
    if not text:
        findings.append(f"{CONFIG_TEMPLATE} is not in the repository, so the template "
                        f"every generated configuration is configured from is held by "
                        f"nothing")
    elif not pairs:
        findings.append(f"{CONFIG_TEMPLATE} carries no region in the form this rule reads "
                        f"a memory type and an executability out of")
    elif len(pairs) != typed:
        findings.append(f"{CONFIG_TEMPLATE} types {typed} regions and this rule pairs "
                        f"{len(pairs)} of them with an `executable`, so its reading has "
                        f"narrowed and the regions it no longer reaches are unheld")

    for index, (kind, flag) in enumerate(pairs):
        where = f"{CONFIG_TEMPLATE}'s region {index}"
        if kind not in MEM_TYPES:
            findings.append(f"{where} is typed `{kind}`, which is neither of the two kinds "
                            f"a region is, so whether it is a device endpoint cannot be "
                            f"decided")
            continue
        read.append((where, kind, flag == "true"))

    device = [(where, executable) for where, kind, executable in read
              if kind == "IOMemory"]
    findings += [f"{where} is typed IOMemory and declares `executable` true, so an "
                 f"instruction fetch to a device endpoint is admitted by `pmaCheck` "
                 f"(model/model/sys/mem.sail) where it would otherwise raise an access "
                 f"fault"
                 for where, executable in device if executable]
    if read and not device:
        findings.append("no region any shipped configuration or the configuration "
                        "template declares is typed IOMemory, so this rule decides "
                        "nothing about a device endpoint at all")

    rep.report("K-101", "device region(s) a composition declares executable:", findings,
               f"each of the {len(device)} IO memory regions the "
               f"{len(SHIPPED_CONFIGS)} shipped configurations and {CONFIG_TEMPLATE} "
               f"declare is non-executable, out of {len(read)} regions read")
