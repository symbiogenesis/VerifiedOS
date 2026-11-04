# SPDX-License-Identifier: Apache-2.0
"""Coordinate fixed-package checking against authenticated prior admissions.

The [reuse contract](../../docs/implementation/contracts/fixed-packages.md#reusing-checked-proofs-across-generations)
separates package-local proof checking from fresh layout and generation checks.
Checker callbacks and the current-generation adapter are trusted caller interfaces;
fixture callbacks do not qualify a production checker. No cache document can assert
its own admission, and a returned candidate is not authenticated prior state.
"""

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Protocol

from vos import package_artifacts
from vos.composer import canonical_bytes

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MAGIC = b"VOSPKG1\0"
_HEADER_BYTES = len(_MAGIC) + 4
_ENTRY_BYTES = 64
MAX_CHECKED_PACKAGES = 65536
_AUTHENTICATED = object()

type ProofKey = tuple[str, str]


class PackageAdmissionError(ValueError):
    """Inputs or trusted checking interfaces cannot produce a successor state."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash(value: object, where: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise PackageAdmissionError(f"{where}: expected a lowercase SHA-256 identity")
    return value


@dataclass(frozen=True, kw_only=True)
class ProofContext:
    """Exact package proof judgment, checker, environment and resource scope."""

    target: str
    specification: str
    model: str
    descriptor: str
    profile: str
    decoder: str
    dictionary: str
    checker: str
    environment: str
    assumptions: str
    policy: str
    resources: str
    tier: int

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if name != "tier":
                _hash(value, f"proof context {name}")
        if type(self.tier) is not int or not 0 <= self.tier <= 2:
            raise PackageAdmissionError("proof context tier must be 0, 1 or 2")

    def identity(self) -> str:
        self.validate()
        return _digest(canonical_bytes(asdict(self)))


class CurrentGeneration(Protocol):
    """Trusted adapter to the current admitted generation's protected root."""

    def checked_set_root(self) -> str | None: ...


@dataclass(frozen=True)
class AuthenticatedState:
    """Prior state produced only by restoration against a trusted current root."""

    snapshot: bytes
    root: str
    _entries: frozenset[ProofKey] = field(repr=False)
    _current: CurrentGeneration = field(repr=False, compare=False)
    _seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _AUTHENTICATED:
            raise PackageAdmissionError("prior checked state requires a trusted current-generation root")


@dataclass(frozen=True)
class Request:
    """One concrete placement and its fresh TAL input under a package context."""

    placement: package_artifacts.Placement
    context: ProofContext
    tal: bytes


@dataclass(frozen=True)
class Checkers:
    """Trusted checker entry points, never verdicts supplied by package metadata."""

    package: Callable[[package_artifacts.Artifact, ProofContext], bool] | None
    layout: Callable[[Request, bytes, bytes], bool] | None
    generation: Callable[[tuple[Request, ...], bytes, bytes], bool] | None
    context: Callable[[package_artifacts.Artifact], ProofContext] | None = None
    linkage: Callable[[tuple[Request, ...], bytes, bytes], bool] | None = None


@dataclass(frozen=True)
class Candidate:
    """Checked successor proposal; the authenticated transactor must commit it."""

    checked_set: bytes
    checked_root: str
    image_sha256: str
    generation_sha256: str
    bindings: tuple[str, ...]
    checked: tuple[ProofKey, ...]
    reused: tuple[ProofKey, ...]


def _encode(entries: frozenset[ProofKey]) -> bytes:
    if len(entries) > MAX_CHECKED_PACKAGES:
        raise PackageAdmissionError("checked package set exceeds its finite capacity")
    return (_MAGIC + len(entries).to_bytes(4, "little")
            + b"".join(bytes.fromhex(artifact) + bytes.fromhex(context)
                       for artifact, context in sorted(entries)))


def _decode(snapshot: bytes) -> frozenset[ProofKey]:
    if (type(snapshot) is not bytes or len(snapshot) < _HEADER_BYTES
            or len(snapshot) > _HEADER_BYTES + MAX_CHECKED_PACKAGES * _ENTRY_BYTES
            or snapshot[:len(_MAGIC)] != _MAGIC):
        raise PackageAdmissionError("malformed or over-limit checked package set")
    count = int.from_bytes(snapshot[len(_MAGIC):_HEADER_BYTES], "little")
    if count > MAX_CHECKED_PACKAGES or len(snapshot) != _HEADER_BYTES + count * _ENTRY_BYTES:
        raise PackageAdmissionError("checked package count differs from its exact byte population")
    entries = frozenset((snapshot[start:start + 32].hex(), snapshot[start + 32:start + 64].hex())
                        for start in range(_HEADER_BYTES, len(snapshot), _ENTRY_BYTES))
    if len(entries) != count or _encode(entries) != snapshot:
        raise PackageAdmissionError("checked package entries must be unique and canonically ordered")
    return entries


def _current_root(current: CurrentGeneration | None) -> str:
    if current is None:
        raise PackageAdmissionError("prior checked state has no trusted current-generation root")
    try:
        root = current.checked_set_root()
    except (AttributeError, TypeError, ValueError, OSError) as error:
        raise PackageAdmissionError(f"current admitted root is unavailable: {error}") from error
    return _hash(root, "current admitted checked-set root")


def restore(snapshot: bytes, current: CurrentGeneration | None) -> AuthenticatedState:
    """Restore persistent membership only through the trusted current adapter."""
    root = _current_root(current)
    entries = _decode(snapshot)
    if _digest(snapshot) != root or _current_root(current) != root:
        raise PackageAdmissionError("checked package set differs from the current admitted root")
    if current is None:
        raise PackageAdmissionError("prior checked state has no trusted current-generation root")
    return AuthenticatedState(snapshot, root, entries, current, _AUTHENTICATED)


def _prior_entries(prior: AuthenticatedState | None) -> frozenset[ProofKey]:
    if prior is None:
        return frozenset[ProofKey]()
    if not isinstance(prior, AuthenticatedState) or prior._seal is not _AUTHENTICATED:
        raise PackageAdmissionError("only authenticated current-generation state may be reused")
    if (_current_root(prior._current) != prior.root or _digest(prior.snapshot) != prior.root
            or _decode(prior.snapshot) != prior._entries):
        raise PackageAdmissionError("prior checked state is stale or corrupt")
    return prior._entries


def _request_binding(request: Request) -> tuple[ProofKey, str]:
    if not isinstance(request, Request) or not isinstance(request.context, ProofContext):
        raise PackageAdmissionError("generation requires typed fixed-package requests")
    placement = request.placement
    if not isinstance(placement, package_artifacts.Placement):
        raise PackageAdmissionError("generation requires a typed fixed-package placement")
    artifact = placement.artifact
    fresh = package_artifacts.place(artifact, placement.base)
    if placement != fresh:
        raise PackageAdmissionError("placement metadata differs from the immutable artifact and base")
    request.context.validate()
    context = artifact.document()["context"]
    for name, value in context.items():
        if getattr(request.context, name) != value:
            raise PackageAdmissionError(f"artifact and proof context disagree at {name}")
    if type(request.tal) is not bytes or not request.tal:
        raise PackageAdmissionError("each concrete layout requires fresh nonempty TAL input")
    key = artifact.identity, request.context.identity()
    binding = _digest(canonical_bytes({"artifact": artifact.identity, "context": key[1],
                                      "placement": fresh.binding(),
                                      "tal_sha256": _digest(request.tal)}))
    return key, binding


def _trusted_context(request: Request, checkers: Checkers) -> None:
    if checkers.context is None:
        raise PackageAdmissionError("trusted current proof-context adapter is required")
    expected = checkers.context(request.placement.artifact)
    if not isinstance(expected, ProofContext):
        raise PackageAdmissionError("trusted proof-context adapter returned no typed context")
    expected.validate()
    if expected != request.context:
        raise PackageAdmissionError("requested proof context differs from the trusted current context")


def prepare_generation(requests: Sequence[Request], image: bytes, generation: bytes,
                       checkers: Checkers | None, *,
                       prior: AuthenticatedState | None = None) -> Candidate:
    """Stage reusable proofs and always recheck the concrete successor generation.

    The caller supplies the exact immutable image and generation-check inputs.
    This function writes no persistent state. Failure or interruption returns no
    candidate and cannot modify the authenticated predecessor.
    """
    if (checkers is None or not isinstance(checkers, Checkers)
            or not callable(checkers.package) or not callable(checkers.layout)
            or not callable(checkers.generation) or not callable(checkers.context)
            or not callable(checkers.linkage)):
        raise PackageAdmissionError("actual package, TAL/layout, linkage, generation and current-context checkers are required")
    if type(image) is not bytes or type(generation) is not bytes or not image or not generation:
        raise PackageAdmissionError("image and generation inputs must be nonempty immutable bytes")
    selected = tuple(requests)
    if len(selected) > MAX_CHECKED_PACKAGES:
        raise PackageAdmissionError("generation exceeds its finite package capacity")
    previous = _prior_entries(prior)
    before = tuple(_request_binding(request) for request in selected)
    for request in selected:
        _trusted_context(request, checkers)
    placements = tuple(request.placement for request in selected)
    package_artifacts.verify_image(image, placements)
    staged: set[ProofKey] = set()
    checked: set[ProofKey] = set()
    reused: set[ProofKey] = set()
    for request, (key, _) in zip(selected, before, strict=True):
        if key in previous:
            reused.add(key)
        elif key not in staged:
            if checkers.package(request.placement.artifact, request.context) is not True:
                raise PackageAdmissionError(f"package-local proof refused: {request.placement.artifact.package_id}")
            checked.add(key)
        staged.add(key)
        if checkers.layout(request, image, generation) is not True:
            raise PackageAdmissionError(f"concrete TAL/layout refused: {request.placement.artifact.package_id}")
    if checkers.linkage(selected, image, generation) is not True:
        raise PackageAdmissionError("generation source-correspondence linkage checks refused")
    if checkers.generation(selected, image, generation) is not True:
        raise PackageAdmissionError("generation wiring, memory or schedule checks refused")
    if tuple(_request_binding(request) for request in selected) != before:
        raise PackageAdmissionError("package, context or layout inputs changed during checking")
    for request in selected:
        _trusted_context(request, checkers)
    package_artifacts.verify_image(image, placements)
    if _prior_entries(prior) != previous:
        raise PackageAdmissionError("prior admitted state changed during checking")
    snapshot = _encode(frozenset(staged))
    return Candidate(snapshot, _digest(snapshot), _digest(image), _digest(generation),
                     tuple(binding for _, binding in before), tuple(sorted(checked)), tuple(sorted(reused)))
