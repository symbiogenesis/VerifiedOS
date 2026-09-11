# SPDX-License-Identifier: Apache-2.0
"""Q22b's executable qualification model, with ideal authentication and storage.

Tuples represent complete log histories: prefix and membership stand for checked
consistency and inclusion proofs. Authentication booleans are assumptions supplied
by an ideal verifier, never signature checks. This module is not an admission
implementation or a machine-checked policy theorem.
"""

from dataclasses import dataclass
from itertools import combinations

type Checkpoint = tuple[str, ...]


class WitnessError(ValueError):
    """An operation has no transition under this model's assumptions."""


@dataclass(frozen=True)
class Key:
    identity: str
    public_key: str


@dataclass(frozen=True)
class Policy:
    scope: str
    epoch: int
    witnesses: tuple[Key, ...]
    threshold: int
    faults: int

    def __post_init__(self) -> None:
        n = len(self.witnesses)
        if (not self.scope or self.epoch < 0 or not 1 <= self.threshold <= n
                or not 0 <= self.faults < n):
            raise WitnessError("invalid flat policy parameters")
        if (any(not key.identity or not key.public_key for key in self.witnesses)
                or len({key.identity for key in self.witnesses}) != n
                or len({key.public_key for key in self.witnesses}) != n):
            raise WitnessError("witness identities and keys must each be unique")

    @property
    def safe(self) -> bool:
        return 2 * self.threshold - len(self.witnesses) > self.faults

    def available(self, responsive: frozenset[Key]) -> bool:
        """Assumes these witnesses will sign this consistent request eventually."""
        return len(responsive.intersection(self.witnesses)) >= self.threshold


def flat(n: int, k: int, f: int, *, scope: str = "population", epoch: int = 0,
         prefix: str = "w") -> Policy:
    return Policy(scope, epoch, tuple(Key(f"{prefix}{i}", f"{prefix}-key-{i}")
                                     for i in range(n)), k, f)


def extends(new: Checkpoint, old: Checkpoint) -> bool:
    return new[:len(old)] == old


@dataclass(frozen=True)
class Transition:
    old: Policy
    new: Policy
    anchor: Checkpoint

    @property
    def continuous(self) -> bool:
        return (self.old.safe and self.new.safe and self.new.scope == self.old.scope
                and self.new.epoch == self.old.epoch + 1)


@dataclass(frozen=True)
class Record:
    checkpoint: Checkpoint
    serial: int = 0
    terminal: Transition | None = None


@dataclass(frozen=True)
class Signature:
    policy: Policy
    signer: Key
    checkpoint: Checkpoint
    terminal: Transition | None = None
    authenticated: bool = True


@dataclass(frozen=True)
class Recovery:
    policy: Policy
    signer: Key
    record: Record
    authenticated: bool


class Witness:
    """An honest witness; trusted is an ideal authenticated antirollback anchor.

    The anchor survives modeled process/storage failures. Providing such an anchor
    or retiring the identity when it is unavailable is an external obligation.
    stored may be lost or rolled back independently; pending is volatile. A commit
    atomically advances stored and trusted before any release.
    """

    def __init__(self, policy: Policy, key: Key, anchor: Checkpoint = ()) -> None:
        if key not in policy.witnesses:
            raise WitnessError("identity/key is not enrolled")
        self.policy = policy
        self.key = key
        self.trusted = Record(anchor)
        self.stored: Record | None = self.trusted
        self.pending: Record | None = None

    def _current(self) -> Record:
        if self.stored is None or self.stored != self.trusted:
            raise WitnessError("lost or rolled-back state requires authenticated recovery")
        return self.stored

    def prepare(self, checkpoint: Checkpoint, terminal: Transition | None = None) -> None:
        current = self._current()
        if current.terminal is not None and (checkpoint != current.checkpoint
                                             or terminal != current.terminal):
            raise WitnessError("terminal epoch cannot sign again")
        if not extends(checkpoint, current.checkpoint):
            raise WitnessError("inconsistent checkpoint")
        if terminal is not None and (not terminal.continuous or terminal.old != self.policy
                                     or terminal.anchor != checkpoint):
            raise WitnessError("terminal statement does not bind this transition")
        same = current.checkpoint == checkpoint and current.terminal == terminal
        self.pending = current if same else Record(checkpoint, current.serial + 1, terminal)

    def commit(self) -> None:
        self._current()
        if self.pending is None:
            raise WitnessError("no prepared checkpoint")
        self.stored = self.pending
        self.trusted = self.pending

    def release(self) -> Signature:
        current = self._current()
        if self.pending is None or current != self.pending:
            raise WitnessError("co-signature requires the exact durable successor")
        signature = Signature(self.policy, self.key, current.checkpoint, current.terminal)
        self.pending = None
        return signature

    def sign(self, checkpoint: Checkpoint, terminal: Transition | None = None) -> Signature:
        self.prepare(checkpoint, terminal)
        self.commit()
        return self.release()

    def crash(self) -> None:
        self.pending = None

    def recover(self, evidence: Recovery) -> None:
        if (not evidence.authenticated or evidence.policy != self.policy
                or evidence.signer != self.key or evidence.record != self.trusted):
            raise WitnessError("recovery does not authenticate the latest identity state")
        self.stored = evidence.record
        self.pending = None


def certificate(policy: Policy, checkpoint: Checkpoint, signatures: tuple[Signature, ...],
                terminal: Transition | None = None) -> bool:
    """Ideal verified signatures, distinct enrolled keys, exact statement binding."""
    signers: set[Key] = set()
    if not policy.safe:
        return False
    for signature in signatures:
        if (not signature.authenticated or signature.policy != policy
                or signature.checkpoint != checkpoint or signature.terminal != terminal
                or signature.signer not in policy.witnesses or signature.signer in signers):
            return False
        signers.add(signature.signer)
    return len(signers) >= policy.threshold


@dataclass(frozen=True)
class Rebootstrap:
    old: Policy
    new: Policy
    anchor: Checkpoint
    replacement_assumptions: str
    authenticated: bool


class Client:
    """Abstract local policy/pin state; admission refusal preserves the installed name."""

    def __init__(self, policy: Policy, pinned: Checkpoint = ()) -> None:
        self.policy = policy
        self.pinned = pinned
        self.installed = "running-generation"
        self.continuity_preserved = True
        self.seen_scopes = frozenset((policy.scope,))

    def admit(self, checkpoint: Checkpoint, signatures: tuple[Signature, ...],
              base: str, packages: tuple[str, ...], generation: str) -> bool:
        if (not certificate(self.policy, checkpoint, signatures)
                or not extends(checkpoint, self.pinned)
                or not base or base not in checkpoint
                or any(not package or package not in checkpoint for package in packages)):
            return False
        self.pinned = checkpoint
        self.installed = generation
        return True

    def transition(self, change: Transition, old_seals: tuple[Signature, ...],
                   new_signatures: tuple[Signature, ...]) -> bool:
        if (change.old != self.policy or not change.continuous
                or not extends(change.anchor, self.pinned)
                or not certificate(change.old, change.anchor, old_seals, change)
                or not certificate(change.new, change.anchor, new_signatures)):
            return False
        self.policy = change.new
        self.pinned = change.anchor
        return True

    def rebootstrap(self, change: Rebootstrap,
                    new_signatures: tuple[Signature, ...]) -> bool:
        if (change.old != self.policy or not change.authenticated
                or not change.replacement_assumptions.strip()
                or change.new.scope in self.seen_scopes
                or not certificate(change.new, change.anchor, new_signatures)):
            return False
        self.policy = change.new
        self.pinned = change.anchor
        self.continuity_preserved = False
        self.seen_scopes = self.seen_scopes | {change.new.scope}
        return True


@dataclass(frozen=True)
class QuorumSweep:
    max_n: int
    policies: int
    assignments: int
    disagreements: tuple[str, ...]


def quorum_sweep(max_n: int = 6) -> QuorumSweep:
    """Enumerate all K, f, quorum pairs and faulty subsets for 1 <= N <= max_n.

    Size-K quorums suffice: every accepted larger set contains one. Fault sets
    of every size through f are enumerated, including no faults. The formula is
    compared with intersection minus the actual fault set, not with itself.
    """
    if not 1 <= max_n <= 6:
        raise WitnessError("qualification enumeration requires 1 <= max_n <= 6")
    policies = 0
    assignments = 0
    disagreements: list[str] = []
    for n in range(1, max_n + 1):
        members = range(n)
        for k in range(1, n + 1):
            quorums = tuple(frozenset(q) for q in combinations(members, k))
            intersections = tuple(a & b for a in quorums for b in quorums)
            for f in range(n):
                policies += 1
                all_intersect = True
                for size in range(f + 1):
                    for faulty in combinations(members, size):
                        bad = frozenset(faulty)
                        for overlap in intersections:
                            assignments += 1
                            if not overlap - bad:
                                all_intersect = False
                if all_intersect != flat(n, k, f).safe:
                    disagreements.append(f"N={n}, K={k}, f={f}")
    return QuorumSweep(max_n, policies, assignments, tuple(disagreements))


def signatures(policy: Policy, checkpoint: Checkpoint,
               terminal: Transition | None = None) -> tuple[Signature, ...]:
    """Fixture witnesses with fresh authenticated genesis, not an external service."""
    return tuple(Witness(policy, key).sign(checkpoint, terminal)
                 for key in policy.witnesses[:policy.threshold])
