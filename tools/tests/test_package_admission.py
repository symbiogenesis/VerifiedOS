# SPDX-License-Identifier: Apache-2.0
"""Fixed proof reuse is rooted in prior admission and never replaces fresh checks.

All checker and current-generation adapters below are explicitly synthetic host
fixtures. Their positive verdicts are not production TAL/CIC evidence.
"""

import hashlib
import tempfile
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import cast
from unittest.mock import Mock

from tests.harness import Case, ensure
from vos import image
from vos import package_admission as admission
from vos import package_artifacts as artifacts
from vos.composer import canonical_bytes


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ref(data: bytes) -> dict[str, object]:
    return {"sha256": _sha(data), "bytes": len(data)}


def _artifact(root: Path, name: str, *, changed: str | None = None,
              versions: dict[str, str] | None = None) -> artifacts.Artifact:
    objects = {"source": f"source of {name}".encode(), "contract": f"contract of {name}".encode(),
               "code": bytes.fromhex("1305700067800000"), "initializer": b"initial0",
               "derivation": f"derivation of {name}".encode(),
               "correspondence": f"correspondence of {name}".encode(),
               "hyperproperty": f"hyperproperty of {name}".encode()}
    if changed is not None:
        objects[changed] = (bytes.fromhex("1305800067800000") if changed == "code"
                            else objects[changed] + b" changed")
    context = {key: _sha(key.encode()) for key in
               ("target", "specification", "model", "descriptor", "profile", "decoder", "dictionary")}
    context.update(versions or {})
    manifest = {
        "schema_version": 1, "package_id": name, "context": context,
        "source_closure": _ref(objects["source"]), "contract": _ref(objects["contract"]),
        "span": 256, "alignment": 16,
        "regions": [{"name": "text", "kind": "code", "offset": 0, "alignment": 4,
                     "memory_class": 0, "object": _ref(objects["code"])},
                    {"name": "data", "kind": "initializer", "offset": 128, "alignment": 8,
                     "memory_class": 0, "object": _ref(objects["initializer"])}],
        "entry": 0, "exports": [{"name": "main", "offset": 0}],
        "proofs": {"derivation_template": _ref(objects["derivation"]),
                   "correspondence": _ref(objects["correspondence"]),
                   "hyperproperties": [_ref(objects["hyperproperty"])]}}
    folder = root / "transport"
    (folder / "objects").mkdir(parents=True, exist_ok=True)
    refs = []
    for data in set(objects.values()):
        relative = f"objects/{_sha(data)}"
        (folder / relative).write_bytes(data)
        refs.append({"path": relative, **_ref(data)})
    request = folder / "request.json"
    request.write_bytes(canonical_bytes({"manifest": manifest, "objects": refs}))
    built = artifacts.read_request(folder, "request.json")
    directory = root / "store"
    identity = artifacts.store(directory, built)
    return artifacts.load(directory, identity)


def _context(artifact: artifacts.Artifact, **changes: str | int) -> admission.ProofContext:
    context = artifact.document()["context"]
    value = admission.ProofContext(target=context["target"], specification=context["specification"],
        model=context["model"], descriptor=context["descriptor"], profile=context["profile"],
        decoder=context["decoder"], dictionary=context["dictionary"], checker=_sha(b"checker"),
        environment=_sha(b"environment"), assumptions=_sha(b"assumptions"),
        policy=_sha(b"policy"), resources=_sha(b"resources"), tier=1)
    return replace(value, **changes)


def _requests(packages: tuple[artifacts.Artifact, ...], contexts: tuple[admission.ProofContext, ...],
              base: int = 0x80000000) -> tuple[admission.Request, ...]:
    return tuple(admission.Request(artifacts.place(artifact, base + index * 4096), context,
                                   f"concrete TAL input at {base + index * 4096}".encode())
                 for index, (artifact, context) in enumerate(zip(packages, contexts, strict=True)))


def _image(root: Path, requests: tuple[admission.Request, ...]) -> bytes:
    path = root / "generation.elf"
    sections = [section for request in requests for section in request.placement.sections]
    image.write_elf(path, sections, {}, requests[0].placement.entry)
    return path.read_bytes()


class _Current:
    """Fixture for the root read from an already admitted generation."""

    def __init__(self, root: str | None) -> None:
        self.root = root

    def checked_set_root(self) -> str | None:
        return self.root


class _Checks:
    """Fixture checkers count real coordinator invocations over immutable inputs."""

    def __init__(self, contexts: dict[str, admission.ProofContext]) -> None:
        self.contexts = contexts
        self.packages: list[str] = []
        self.layouts: list[int] = []
        self.linkages: list[bytes] = []
        self.generations: list[bytes] = []
        self.package_ok = True
        self.layout_ok = True
        self.linkage_ok = True
        self.generation_ok = True
        self.on_generation: Callable[[], None] | None = None

    def package(self, artifact: artifacts.Artifact, context: admission.ProofContext) -> bool:
        ensure(context == self.contexts[artifact.identity], "checker saw an untrusted proof context")
        artifact.validate()
        self.packages.append(artifact.identity)
        return self.package_ok

    def layout(self, request: admission.Request, actual: bytes, generation: bytes) -> bool:
        ensure(actual.startswith(b"\x7fELF") and bool(generation), "layout checker lost concrete inputs")
        self.layouts.append(request.placement.base)
        return self.layout_ok

    def generation(self, requests: tuple[admission.Request, ...], actual: bytes,
                   generation: bytes) -> bool:
        artifacts.verify_image(actual, tuple(request.placement for request in requests))
        self.generations.append(generation)
        if self.on_generation is not None:
            self.on_generation()
        return self.generation_ok

    def linkage(self, requests: tuple[admission.Request, ...], actual: bytes,
                generation: bytes) -> bool:
        ensure(bool(requests) and actual.startswith(b"\x7fELF"), "linkage checker lost its concrete inputs")
        self.linkages.append(generation)
        return self.linkage_ok

    def checkers(self) -> admission.Checkers:
        return admission.Checkers(package=self.package, layout=self.layout, generation=self.generation,
                                  context=lambda artifact: self.contexts[artifact.identity], linkage=self.linkage)


def _refused(action: Callable[[], object], phrase: str) -> None:
    try:
        action()
    except (ValueError, OSError) as error:
        ensure(phrase in str(error), f"wrong fixed admission refusal: {error}")
        return
    raise AssertionError(f"fixed admission accepted {phrase}")


def _reuse_across_reboot_and_change() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-admission-") as directory:
        root = Path(directory)
        packages = (_artifact(root, "alpha"), _artifact(root, "beta"))
        contexts = tuple(_context(artifact) for artifact in packages)
        requests = _requests(packages, contexts)
        checks = _Checks(dict(zip((artifact.identity for artifact in packages), contexts, strict=True)))
        first = admission.prepare_generation(requests, _image(root, requests), b"generation one", checks.checkers())
        ensure(len(checks.packages) == 2 and len(checks.layouts) == 2 and len(checks.generations) == 1
               and checks.linkages == [b"generation one"],
               "cold admission must invoke both package checkers and all fresh checks")
        snapshot = root / "committed-checked-set"
        snapshot.write_bytes(first.checked_set)
        prior = admission.restore(snapshot.read_bytes(), _Current(first.checked_root))
        moved = _requests(packages, contexts, 0x80010000)
        moved_checks = _Checks(checks.contexts)
        second = admission.prepare_generation(moved, _image(root, moved), b"generation two",
                                               moved_checks.checkers(), prior=prior)
        ensure(moved_checks.packages == [] and len(moved_checks.layouts) == 2
               and moved_checks.linkages == [b"generation two"]
               and moved_checks.generations == [b"generation two"],
               "a reboot and new layouts reuse only package-local proofs")
        ensure(first.bindings != second.bindings and first.image_sha256 != second.image_sha256,
               "concrete image and TAL bindings must change at the translated layouts")
        ensure(first.checked_root == second.checked_root and len(second.reused) == 2,
               "unchanged proof subjects retain their authenticated checked-set root")
        beta = _artifact(root, "beta", changed="correspondence")
        changed = (packages[0], beta)
        changed_contexts = (contexts[0], _context(beta))
        last_checks = _Checks(dict(zip((artifact.identity for artifact in changed), changed_contexts, strict=True)))
        last_requests = _requests(changed, changed_contexts, 0x80020000)
        last = admission.prepare_generation(last_requests, _image(root, last_requests), b"generation three",
                                             last_checks.checkers(), prior=prior)
        ensure(last_checks.packages == [beta.identity] and len(last.reused) == 1,
               "one changed package must invoke exactly its own package checker")
        ensure(prior.snapshot == first.checked_set and prior.root == first.checked_root,
               "preparing a successor never edits authenticated predecessor state")
        _refused(lambda: admission.prepare_generation(requests, _image(root, requests), b"uncommitted",
                                                       checks.checkers(), prior=cast("admission.AuthenticatedState", first)),
                 "only authenticated")


def _artifact_changes_invalidate() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-proof-subjects-") as directory:
        root = Path(directory)
        original = _artifact(root, "alpha")
        context = _context(original)
        requests = _requests((original,), (context,))
        checks = _Checks({original.identity: context})
        first = admission.prepare_generation(requests, _image(root, requests), b"first", checks.checkers())
        prior = admission.restore(first.checked_set, _Current(first.checked_root))
        for changed in ("source", "contract", "code", "initializer", "derivation", "correspondence", "hyperproperty"):
            artifact = _artifact(root, "alpha", changed=changed)
            current = _context(artifact)
            selection = _requests((artifact,), (current,))
            callbacks = _Checks({artifact.identity: current})
            candidate = admission.prepare_generation(selection, _image(root, selection), changed.encode(),
                                                      callbacks.checkers(), prior=prior)
            ensure(callbacks.packages == [artifact.identity] and not candidate.reused,
                   f"changed {changed} must invalidate package-local proof reuse")


def _current_context_controls_reuse() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-proof-context-") as directory:
        root = Path(directory)
        artifact = _artifact(root, "alpha")
        context = _context(artifact)
        requests = _requests((artifact,), (context,))
        checks = _Checks({artifact.identity: context})
        first = admission.prepare_generation(requests, _image(root, requests), b"first", checks.checkers())
        prior = admission.restore(first.checked_set, _Current(first.checked_root))
        versions = set(artifact.document()["context"])
        for name in asdict(context):
            value = 2 if name == "tier" else _sha(f"changed {name}".encode())
            expected = replace(context, **{name: value})
            callbacks = _Checks({artifact.identity: expected})
            _refused(lambda callbacks=callbacks: admission.prepare_generation(requests, _image(root, requests),
                     b"old context", callbacks.checkers(), prior=prior), "trusted current context")
            changed_artifact = (_artifact(root, "alpha", versions={name: cast("str", value)})
                                if name in versions else artifact)
            selection = _requests((changed_artifact,), (expected,))
            callbacks = _Checks({changed_artifact.identity: expected})
            candidate = admission.prepare_generation(selection, _image(root, selection), b"new context",
                                                      callbacks.checkers(), prior=prior)
            ensure(callbacks.packages == [changed_artifact.identity] and not candidate.reused,
                   f"changed trusted {name} must invoke the actual package checker")


def _unanchored_and_forged_state_refuses() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-proof-roots-") as directory:
        root = Path(directory)
        artifact = _artifact(root, "alpha")
        context = _context(artifact)
        requests = _requests((artifact,), (context,))
        checks = _Checks({artifact.identity: context})
        first = admission.prepare_generation(requests, _image(root, requests), b"first", checks.checkers())
        _refused(lambda: admission.restore(first.checked_set, None), "no trusted")
        _refused(lambda: admission.restore(first.checked_set, _Current(None)), "current admitted")
        _refused(lambda: admission.restore(first.checked_set, _Current("0" * 64)), "current admitted root")
        corrupt = first.checked_set[:-1] + bytes([first.checked_set[-1] ^ 1])
        _refused(lambda: admission.restore(corrupt, _Current(first.checked_root)), "current admitted root")
        fake = canonical_bytes({"accepted": True, "entries": [artifact.identity]})
        _refused(lambda: admission.restore(fake, _Current(_sha(fake))), "malformed")
        duplicate = b"VOSPKG1\0" + (2).to_bytes(4, "little") + first.checked_set[12:] * 2
        _refused(lambda: admission.restore(duplicate, _Current(_sha(duplicate))), "unique")
        _refused(lambda: admission.AuthenticatedState(first.checked_set, first.checked_root, frozenset(),
                                                      _Current(first.checked_root), object()), "requires a trusted")
        _refused(lambda: admission.restore(first.checked_set + b"trailer", _Current(first.checked_root)),
                 "exact byte population")


def _fresh_failures_do_not_publish() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-proof-failures-") as directory:
        root = Path(directory)
        artifact = _artifact(root, "alpha")
        context = _context(artifact)
        requests = _requests((artifact,), (context,))
        actual = _image(root, requests)
        checks = _Checks({artifact.identity: context})
        first = admission.prepare_generation(requests, actual, b"first", checks.checkers())
        current = _Current(first.checked_root)
        prior = admission.restore(first.checked_set, current)
        for phase, phrase in (("layout", "TAL/layout"), ("linkage", "source-correspondence linkage"),
                              ("generation", "wiring")):
            callbacks = _Checks(checks.contexts)
            setattr(callbacks, f"{phase}_ok", False)
            _refused(lambda callbacks=callbacks: admission.prepare_generation(requests, actual, b"refused",
                     callbacks.checkers(), prior=prior), phrase)
            ensure(callbacks.packages == [] and bool(callbacks.layouts),
                   "fresh checks must run even when package-local proof checking is reused")
            ensure(prior.root == first.checked_root and prior.snapshot == first.checked_set,
                   "a rejected successor must leave prior admission unchanged")
        cold = _Checks(checks.contexts)
        cold.package_ok = False
        _refused(lambda: admission.prepare_generation(requests, actual, b"bad package", cold.checkers()),
                 "package-local proof refused")
        _refused(lambda: admission.prepare_generation(requests, actual, b"missing checker", None), "checkers are required")
        missing_context = replace(checks.checkers(), context=None)
        _refused(lambda: admission.prepare_generation(requests, actual, b"missing context", missing_context, prior=prior),
                 "checkers are required")
        missing_linkage = replace(checks.checkers(), linkage=None)
        _refused(lambda: admission.prepare_generation(requests, actual, b"missing linkage", missing_linkage, prior=prior),
                 "checkers are required")
        fake_verdict = replace(checks.checkers(), package=Mock(return_value={"accepted": True}))
        _refused(lambda: admission.prepare_generation(requests, actual, b"fake verdict", fake_verdict), "proof refused")

        def interrupted() -> None:
            raise KeyboardInterrupt("fixture interruption")

        callbacks = _Checks(checks.contexts)
        callbacks.on_generation = interrupted
        try:
            admission.prepare_generation(requests, actual, b"interrupted", callbacks.checkers(), prior=prior)
        except KeyboardInterrupt:
            pass
        else:
            raise AssertionError("interrupted checking returned a successor")
        ensure(prior.root == first.checked_root and prior.snapshot == first.checked_set,
               "interruption must preserve authenticated predecessor state")


def _image_and_input_drift_refuses() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-package-proof-drift-") as directory:
        root = Path(directory)
        artifact = _artifact(root, "alpha")
        context = _context(artifact)
        requests = _requests((artifact,), (context,))
        actual = _image(root, requests)
        checks = _Checks({artifact.identity: context})
        code = bytes.fromhex("1305700067800000")
        at = actual.index(code)
        corrupt = actual[:at] + bytes([actual[at] ^ 1]) + actual[at + 1:]
        _refused(lambda: admission.prepare_generation(requests, corrupt, b"bad image", checks.checkers()), "image")
        ensure(checks.packages == [], "a mismatched physical image must refuse before checking proofs")
        placement = requests[0].placement
        wrong_section = replace(placement.sections[0], writable=True)
        forged = (replace(placement, entry=placement.base + 128),
                  replace(placement, exports=(("main", placement.base + 128),)),
                  replace(placement, sections=(wrong_section, *placement.sections[1:])))
        for wrong in forged:
            selected = (replace(requests[0], placement=wrong),)
            _refused(lambda selected=selected: admission.prepare_generation(selected, actual, b"forged metadata",
                     checks.checkers()), "placement metadata")
            ensure(checks.packages == [] and checks.layouts == [],
                   "noncanonical placement entry exports or sections must never reach a trusted checker")
        original_policy = context.policy

        def mutate_context() -> None:
            object.__setattr__(context, "policy", _sha(b"mutated policy"))

        checks.on_generation = mutate_context
        try:
            _refused(lambda: admission.prepare_generation(requests, actual, b"context drift", checks.checkers()), "inputs changed")
        finally:
            object.__setattr__(context, "policy", original_policy)
        section = placement.sections[0]
        original_bytes = bytes(section.data)

        def mutate_section() -> None:
            section.data[0] ^= 1

        checks.on_generation = mutate_section
        try:
            _refused(lambda: admission.prepare_generation(requests, actual, b"section drift", checks.checkers()),
                     "placement metadata")
        finally:
            section.data[:] = original_bytes
        checks.on_generation = None
        first = admission.prepare_generation(requests, actual, b"first", checks.checkers())
        current = _Current(first.checked_root)
        prior = admission.restore(first.checked_set, current)
        checks.on_generation = lambda: setattr(current, "root", "0" * 64)
        _refused(lambda: admission.prepare_generation(requests, actual, b"root drift", checks.checkers(), prior=prior), "stale or corrupt")


def cases() -> list[Case]:
    return [Case("persistent prior admission reuses only unchanged package proofs", _reuse_across_reboot_and_change),
            Case("every artifact and proof object change invalidates reuse", _artifact_changes_invalidate),
            Case("trusted current context controls every reuse dimension", _current_context_controls_reuse),
            Case("unanchored corrupt and fabricated checked states refuse", _unanchored_and_forged_state_refuses),
            Case("fresh checks refusals and interruption cannot publish state", _fresh_failures_do_not_publish),
            Case("physical image and live input drift refuse", _image_and_input_drift_refuses)]
