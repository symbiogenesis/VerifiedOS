# SPDX-License-Identifier: Apache-2.0
"""Offline AdmissionPath reference execution and image-bound fixture records.

The reference carries discharge metadata, not proof terms. Successful execution
therefore reports reference acceptance only, never production admission.
"""

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

from . import proofs

if TYPE_CHECKING:
    from .boot import Roster

SOURCE = "proofs/AdmissionPath.v"
CHECKER = "tools/vos/admission.py"
SCOPE = "fixture-reference"
OPEN = ["real members' checked derivation records", "production admission refinement",
        "tier-zero and tier-one evidence beyond the reference facet metadata"]


class AdmissionError(ValueError):
    """An unreadable request or an unsupported reference shape."""


@dataclass(frozen=True)
class Step:
    judgment: int
    move: int
    facet: int
    site: int


@dataclass(frozen=True)
class Certificate:
    versions: tuple[int, ...]
    binds: int
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class Package:
    identity: int
    tier: int
    certificate: Certificate | None


@dataclass(frozen=True)
class Verdict:
    rule: str | None = None
    site: int | None = None

    def json(self) -> dict[str, object]:
        return {"decision": "accepted" if self.rule is None else "refused",
                "rule": self.rule, "site": self.site}


@dataclass(frozen=True)
class Reference:
    judgments: tuple[str, ...]
    moves: tuple[str, ...]
    facets: tuple[str, ...]
    tiers: tuple[str, ...]
    routing: tuple[int, ...]
    phase_moves: tuple[int, ...]
    move_rules: tuple[str, ...]
    required: tuple[tuple[int, ...], ...]
    versions: tuple[int, ...]


def _body(text: str, kind: str, name: str) -> str:
    found = re.search(rf"\b{kind} {name}\b[^:=]*?(?::[^=]*?)?:=\s*(.*?)\.", text, re.DOTALL)
    if found is None:
        raise AdmissionError(f"{SOURCE}: cannot read {kind} {name}")
    return str(found[1])


def read_reference(root: Path) -> Reference:
    """Read the reference's closed enums, routing, phase order and demo profile."""
    text = proofs.strip_comments((root / SOURCE).read_text(encoding="utf-8"))

    def enum(name: str) -> tuple[str, ...]:
        body = _body(text, "Inductive", name)
        if re.fullmatch(r"\s*(?:\|\s*\w+\s*)+", body) is None:
            raise AdmissionError(f"{SOURCE}: unsupported {name} enumeration")
        result = tuple(str(item) for item in re.findall(r"\|\s*(\w+)", body))
        if len(set(result)) != len(result):
            raise AdmissionError(f"{SOURCE}: duplicate {name} constructor")
        return result

    judgments, moves, facets, tiers, phases = (enum(name) for name in
                                              ("Judgment", "Move", "Facet", "Tier", "Phase"))

    def mapping(name: str, body: str | None = None) -> dict[str, str]:
        selected = _body(text, "Definition", name) if body is None else body
        matched = re.fullmatch(r"match\s+\w+\s+with\s+(.*?)\s+end", selected.strip(),
                               flags=re.DOTALL)
        if matched is None:
            raise AdmissionError(f"{SOURCE}: unsupported mapping {name}")
        result: dict[str, str] = {}
        for arm in matched[1].strip().lstrip("|").split("|"):
            pair = re.fullmatch(r"\s*(\w+)\s*=>\s*(\w+)\s*", arm)
            if pair is None or pair[1] in result:
                raise AdmissionError(f"{SOURCE}: unsupported or duplicate mapping arm in {name}")
            result[str(pair[1])] = str(pair[2])
        return result

    for noun, names in (("judgment", judgments), ("move", moves), ("facet", facets), ("tier", tiers)):
        if mapping(f"code_of_{noun}") != {name: str(i) for i, name in enumerate(names)}:
            raise AdmissionError(f"{SOURCE}: unsupported {noun} coding")
        decoder = re.sub(r"\bSome\s+", "", _body(text, "Definition", f"{noun}_of_code"))
        expected_decoder = {str(i): name for i, name in enumerate(names)} | {"_": "None"}
        decoded = mapping(f"{noun}_of_code", decoder)
        if decoded != expected_decoder:
            raise AdmissionError(f"{SOURCE}: unsupported {noun} decoding")

    routing = mapping("move_of")
    move_phases = mapping("phase_of_move")
    rules = mapping("rule_of_move")
    if set(routing) != set(facets) or set(move_phases) != set(moves) or set(rules) != set(moves):
        raise AdmissionError(f"{SOURCE}: move mappings must cover exactly their enumerations")
    try:
        routed = tuple(moves.index(routing[f]) for f in facets)
        ordered = tuple(sorted(range(len(moves)), key=lambda m: phases.index(move_phases[moves[m]])))
        move_rules = tuple(rules[m] for m in moves)
    except (KeyError, ValueError) as exc:
        raise AdmissionError(f"{SOURCE}: incomplete move mapping: {exc}") from exc
    order = _body(text, "Definition", "in_phase_order")
    if len(moves) != 3:
        raise AdmissionError(f"{SOURCE}: unsupported coverage move enumeration")
    ordered_names = [moves[index] for index in ordered]
    normalized_order = " ".join(order.split())
    expected_order = (f"app (facets_of_move_in {ordered_names[0]} l) "
                      f"(app (facets_of_move_in {ordered_names[1]} l) "
                      f"(facets_of_move_in {ordered_names[2]} l))")
    if normalized_order != expected_order:
        raise AdmissionError(f"{SOURCE}: unsupported coverage phase order")
    required_body = _body(text, "Definition", "demo_required")
    if re.findall(r"\|\s*(\w+)\s*=>", required_body) != list(tiers):
        raise AdmissionError(f"{SOURCE}: unsupported demo tier requirements")
    required: list[tuple[int, ...]] = []
    for tier in tiers:
        match = re.search(rf"\|\s*{tier}\s*=>\s*(.*?)(?=\||\bend\b)", required_body, re.DOTALL)
        if match is None:
            raise AdmissionError(f"{SOURCE}: no demo requirement for {tier}")
        expression = match[1].strip()
        words = re.findall(r"\b[A-Za-z_]\w*\b", expression)
        if expression == "all_facets":
            required.append(tuple(range(len(facets))))
        elif any(word not in (*facets, "cons", "nil") for word in words):
            raise AdmissionError(f"{SOURCE}: unsupported required expression for {tier}")
        else:
            required.append(tuple(facets.index(word) for word in words if word in facets))
    versions = tuple(int(v) for v in re.findall(r"ver_\w+\s*:=\s*(\d+)",
                                               _body(text, "Definition", "demo_versions")))
    if len(versions) != 4:
        raise AdmissionError(f"{SOURCE}: demo versions must have four components")
    return Reference(judgments, moves, facets, tiers, routed, ordered, move_rules,
                     tuple(required), versions)


def decide(reference: Reference, package: Package) -> Verdict:
    """AdmissionPath.spec_check's metadata decision, including its first failure."""
    cert = package.certificate
    if cert is None:
        return Verdict("DerivationAbsent", package.identity)
    if cert.versions != reference.versions:
        return Verdict("VersionMismatch", package.identity)
    if cert.binds != package.identity:
        return Verdict("BindingMismatch", package.identity)
    if not 0 <= package.tier < len(reference.tiers):
        return Verdict("TierUnrecognised", package.identity)
    for step in cert.steps:
        if not (0 <= step.judgment < len(reference.judgments)
                and 0 <= step.move < len(reference.moves)
                and 0 <= step.facet < len(reference.facets)):
            return Verdict("FormUnrecognised", step.site)
    discharged = {(step.facet, step.move) for step in cert.steps}
    for move in reference.phase_moves:
        for facet in reference.required[package.tier]:
            if reference.routing[facet] == move and (facet, move) not in discharged:
                return Verdict(reference.move_rules[move], facet)
    return Verdict()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _exact(value: object, keys: set[str], where: str) -> dict[str, object]:
    if not isinstance(value, dict) or value.keys() != keys:
        raise AdmissionError(f"{where}: expected exactly {', '.join(sorted(keys))}")
    return cast("dict[str, object]", value)


def _natural(value: object, where: str) -> int:
    if type(value) is not int or value < 0:
        raise AdmissionError(f"{where}: expected a natural number")
    return value


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise AdmissionError(f"{where}: expected nonempty text")
    return value


def _hash(value: object, where: str) -> str:
    text = _text(value, where)
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise AdmissionError(f"{where}: expected lowercase SHA-256")
    return text


def _path(root: Path, value: object) -> Path:
    relative = _text(value, "path")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()) or Path(relative).is_absolute():
        raise AdmissionError("path must remain relative to the checkout")
    return result


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AdmissionError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _parse(data: bytes) -> dict[str, object]:
    try:
        raw: object = json.loads(data, object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdmissionError(f"unreadable request: {exc}") from exc
    result = _exact(raw, {"schema_version", "scope", "profile", "members"}, "request")
    if type(result["schema_version"]) is not int or result["schema_version"] != 1:
        raise AdmissionError("schema_version must be 1")
    if result["scope"] != SCOPE or result["profile"] != "AdmissionPath.demo":
        raise AdmissionError("only fixture-reference with AdmissionPath.demo is supported")
    return result


def _certificate(value: object) -> Certificate | None:
    if value is None:
        return None
    raw = _exact(value, {"versions", "binds_sha256", "steps"}, "certificate")
    versions = raw["versions"]
    steps = raw["steps"]
    if not isinstance(versions, list) or len(versions) != 4 or not isinstance(steps, list):
        raise AdmissionError("certificate: expected four versions and a step list")
    parsed: list[Step] = []
    for item in steps:
        step = _exact(item, {"judgment", "move", "facet", "site"}, "step")
        parsed.append(Step(*(_natural(step[key], key)
                             for key in ("judgment", "move", "facet", "site"))))
    return Certificate(tuple(_natural(v, "version") for v in versions),
                       int(_hash(raw["binds_sha256"], "binds_sha256"), 16), tuple(parsed))


def make_record(root: Path, request_path: str, image: bytes, graph: bytes,
                roster: Roster) -> dict[str, object]:
    """Bind an all-or-nothing reference decision to exact image and graph bytes.

    No field can promote these metadata fixtures into checked derivations.
    Offline tools are identified by the roster digest, never self-certified.
    """
    request = _path(root, request_path).read_bytes()
    raw = _parse(request)
    listed = raw["members"]
    if not isinstance(listed, list):
        raise AdmissionError("members must be a list")
    expected = [member.id for member in roster.members if member.kind != "offline"]
    reference = read_reference(root)
    results: list[dict[str, object]] = []
    seen: list[str] = []
    for item in listed:
        member = _exact(item, {"member", "artifact", "tier", "certificate"}, "member")
        name = _text(member["member"], "member")
        artifact = _path(root, member["artifact"])
        actual_digest = digest(artifact.read_bytes())
        package = Package(int(actual_digest, 16), _natural(member["tier"], "tier"),
                          _certificate(member["certificate"]))
        seen.append(name)
        results.append({"member": name, "artifact": artifact.relative_to(root.resolve()).as_posix(),
                        "artifact_sha256": actual_digest, **decide(reference, package).json()})
    if seen != expected:
        raise AdmissionError(f"members must match the runtime roster in order: {expected!r}")
    accepted = all(result["decision"] == "accepted" for result in results)
    return {"schema_version": 1, "scope": SCOPE, "production_admission": False,
            "decision": "accepted" if accepted else "refused", "generation_accepted": accepted,
            "image_sha256": digest(image), "graph_sha256": digest(graph),
            "roster": {"path": roster.source, "sha256": digest(_path(root, roster.source).read_bytes())},
            "request": {"path": request_path, "sha256": digest(request)},
            "reference_sha256": digest((root / SOURCE).read_bytes()),
            "checker_sha256": digest((root / CHECKER).read_bytes()),
            "members": results, "open": list(OPEN)}


def validate_record(root: Path, record: object, image: bytes, graph: bytes,
                    roster: Roster) -> list[str]:
    """Recompute rather than trusting a caller's success boolean or stale record."""
    if not isinstance(record, dict):
        return ["admission record is not an object"]
    if record.get("image_sha256") != digest(image):
        return ["admission record image digest differs"]
    if record.get("graph_sha256") != digest(graph):
        return ["admission record graph digest differs"]
    try:
        request = _exact(record.get("request"), {"path", "sha256"}, "record request")
        expected = make_record(root, _text(request["path"], "request path"), image, graph, roster)
    except (AdmissionError, OSError) as exc:
        return [f"admission record cannot be replayed: {exc}"]
    if canonical(record) != canonical(expected):
        return ["admission record differs from the replayed reference decision or bound inputs"]
    if expected["decision"] != "accepted":
        return ["admission refused a member; the whole generation is refused"]
    return []


def generated_cases(reference: Reference) -> list[tuple[str, Package]]:
    """Generate accepted/refused families without maintaining a result table."""
    cases: list[tuple[str, Package]] = []
    for tier, required in enumerate(reference.required):
        cert = Certificate(reference.versions, 17, tuple(
            Step(reference.judgments.index("InstructionTransfer"), reference.routing[facet], facet, site)
            for site, facet in enumerate(required)))
        package = Package(17, tier, cert)
        prefix = f"tier{tier}"
        cases.append((prefix + "_covering", package))
        cases.append((prefix + "_absent", replace(package, certificate=None)))
        cases.append((prefix + "_binding", replace(package, certificate=replace(cert, binds=18))))
        cases.append((prefix + "_unknown_tier", replace(package, tier=len(reference.tiers))))
        for version in range(len(reference.versions)):
            versions = list(cert.versions)
            versions[version] += 1
            cases.append((f"{prefix}_version{version}", replace(package, certificate=replace(
                cert, versions=tuple(versions)))))
        for index, step in enumerate(cert.steps):
            candidates: dict[str, tuple[Step, ...]] = {
                "drop": cert.steps[:index] + cert.steps[index + 1:],
                "duplicate": (*cert.steps, step),
                "reverse": tuple(reversed(cert.steps)),
            }
            for field, bound in (("judgment", len(reference.judgments)),
                                 ("move", len(reference.moves)), ("facet", len(reference.facets))):
                changed = replace(step, **{field: bound})
                candidates[field] = (*cert.steps[:index], changed, *cert.steps[index + 1:])
            for move in range(len(reference.moves)):
                candidates[f"route{move}"] = (*cert.steps[:index], replace(step, move=move),
                                               *cert.steps[index + 1:])
            for name, steps in candidates.items():
                cases.append((f"{prefix}_{name}_{index}", replace(
                    package, certificate=replace(cert, steps=steps))))
        cases.extend((f"{prefix}_retag{judgment}", replace(package, certificate=replace(
            cert, steps=tuple(replace(step, judgment=judgment) for step in cert.steps))))
                     for judgment in range(len(reference.judgments)))
    # Each pair distinguishes the specified first refusal from a reordered checker.
    unknown_tier = len(reference.tiers)
    stale_versions = (reference.versions[0] + 1, *reference.versions[1:])
    cases.extend([
        ("version_before_binding", Package(17, unknown_tier, Certificate(stale_versions, 18, ()))),
        ("binding_before_tier", Package(17, unknown_tier, Certificate(reference.versions, 18, ()))),
        ("tier_before_structure", Package(17, unknown_tier, Certificate(reference.versions, 17,
                                      (Step(len(reference.judgments), 0, 0, 8),)))),
        ("deletion_before_citation", Package(17, 0, Certificate(reference.versions, 17, ()))),
    ])
    return cases


def comparison_source(reference: Reference) -> str:
    """Emit concrete Python verdicts as equations the Gallina reference must satisfy."""
    def seq(items: list[str]) -> str:
        result = "nil"
        for item in reversed(items):
            result = f"(cons {item} {result})"
        return result

    lines = ["(* Generated finite comparison, not a refinement proof. *)",
             "Require Import AdmissionPath."]
    for name, package in generated_cases(reference):
        cert = package.certificate
        encoded = "None"
        if cert is not None:
            fields = ("ver_spec_set", "ver_sail_model", "ver_language", "ver_profile")
            versions = "; ".join(f"{field} := {value}" for field, value in
                                 zip(fields, cert.versions, strict=True))
            steps = seq([f"{{| st_judgment := {s.judgment}; st_move := {s.move}; "
                         f"st_facet := {s.facet}; st_site := {s.site} |}}" for s in cert.steps])
            encoded = (f"(Some {{| cert_versions := {{| {versions} |}}; "
                       f"cert_binds := {cert.binds}; cert_steps := {steps} |}})")
        verdict = decide(reference, package)
        expected = "Accepted" if verdict.rule is None else f"(Refused {verdict.rule} {verdict.site})"
        lines += [f"Example compare_{name} :",
                  "  spec_check demo Cert full_reading {| amb_run := 0; amb_state := 0 |}",
                  f"    (package_at {package.identity} {package.tier} 0 false {encoded})",
                  f"  = {expected} := eq_refl."]
    return "\n".join(lines) + "\n"
