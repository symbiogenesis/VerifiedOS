# SPDX-License-Identifier: Apache-2.0
"""Replay bounded Vela elaboration through Menhir and the Rocq kernel.

This qualifies generated CIC terms, never checked parsing, source correspondence,
the production frontend or machine-code admission. Each attempt retains its own
native sources, syntax, generated libraries, process logs and exact identities.
"""

import copy
import hashlib
import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from filelock import FileLock

from vos import env, proofenv, vela
from vos.atomic import atomic_path
from vos.vela import (
    VelaError,
)
from vos.vela import (
    elaborate as vela_elaborate,
)
from vos.vela import (
    parser as vela_parser,
)

TIMEOUT = 120
EXAMPLE = "tools/vela/examples/dependent.vela"


@dataclass(frozen=True)
class Fixture:
    name: str
    source: bytes
    expected: str = "accepted"
    pure: bool = False
    observations: tuple[tuple[str, str], ...] = ()


def fixtures(example: bytes) -> tuple[Fixture, ...]:
    """Independent source examples and well-formed semantic negative neighbors."""
    positives = (
        ("fresh-polymorphic-calls", """module GenericReplay;
definition T Identity<T>(T value) => value;
definition Nat Number() => Identity(3);
definition bool Flag() => Identity(true);
definition Nat Explicit() => Identity<Nat>(4);
"""),
        ("retained-explicit-generic-values-and-calls", """module ExplicitReplay;
definition T Identity<T>(T value) => value;
definition U Apply<T,U>(Fn(T value) -> U function,T value) => function(value);
definition Nat Value() => Apply(Identity::<Nat>,7);
definition Nat Call() => Identity::<Nat>(8);
lemma ValueCorrect() ensures Value() == 7 proof { assert Value() == 7; }
lemma CallCorrect() ensures Call() == 8 proof { assert Call() == 8; }
"""),
        ("dependent-vector-lookup", """module VectorReplay;
definition Vec<T,n> Copy<T, ghost Nat n>(Vec<T,n> xs) => xs;
definition Vec<Nat,2> Two() => VCons(7, VCons(8, VNil<Nat>()));
definition Vec<Nat,0> Empty() => Copy(VNil<Nat>());
definition Nat Lookup() => At(Copy(Two()), FSucc(FZero<0>()));
lemma Selected() ensures At(Two(), FSucc(FZero<0>())) == 8 proof { assert At(Two(), FSucc(FZero<0>())) == 8; }
"""),
        ("product-projection-conversion", """module ProductReplay;
definition Nat Left() => Fst((7, true));
definition bool Right() => Snd((7, true));
lemma LeftValue() ensures Fst((7, true)) == 7 proof { assert Fst((7, true)) == 7; }
lemma RightValue() ensures Snd((7, true)) == true proof { assert Snd((7, true)) == true; }
"""),
        ("higher-order-inference", """module InferenceReplay;
definition U Apply<T,U>(Fn(T value) -> U f, T x) => f(x);
definition Nat Increment() => Apply(x => x + 1, 2,);
Nat Arrow(Nat value,) => Apply((x) => x + 1, value,);
"""),
        ("dependent-type-family", """module FamilyReplay;
definition type[family(n)] Keep(Fn(Nat index) -> Type family, Nat n,
    type[family(n)] value) => value;
definition Nat Use() => Keep((Nat index) => type Nat, 0, 7);
"""),
        ("proof-composition", """module ProofReplay;
definition T Id<T>(T value) => value;
lemma Reflexive<T>(T x) ensures x == x proof {
    assert x == x;
}
lemma Same<T>(T x) ensures x == x proof {
    assert x == x by {
        let step = Id(x);
        assert x == step;
        assert step == x;
    }
}
lemma Step(Nat x) ensures x + 1 == x + 1 proof {
    assert x + 1 == x + 1 by Reflexive(x);
}
definition Eq<T,(x),(y)> KeepProof<T, ghost T x, ghost T y>(Eq<T,(x),(y)> p) => p;
"""),
        ("universal-explicit-equality-proof", """module QuantifierReplay;
lemma Reflexive() ensures forall (Nat value) => value == value proof {
    assert value == value;
}
"""),
        ("definitional-conversion", """module ConversionReplay;
definition Nat Twice(Nat value) => value + value;
lemma Computed() ensures Twice(2) == 4 proof { assert Twice(2) == 4; }
"""),
        ("canonical-unit-and-labeled-generics", """module NamedReplay;
definition T Identity<T>(T value) => value;
definition Unit Empty() => Identity<Unit>(value: ());
definition Nat Value() => Identity(value: 7,);
lemma Same() ensures Identity(value: 7) == 7 proof { assert Identity(value: 7) == 7; }
"""),
        ("declared-dependent-callable-labels", """module CallableReplay;
alias Reader<T> = Fn(Nat count, Vec<T,count> values) -> Vec<T,count>;
definition Reader<Nat> Preserve() => (length, storage) => storage;
definition Vec<Nat,1> Singleton() => VCons(7, VNil<Nat>());
definition Vec<Nat,1> Use() => Preserve()(count: 1, values: Singleton());
definition Vec<Nat,count> Keep(Nat count, Vec<Nat,count> values) => values;
definition Vec<Nat,1> Partial() => Keep(count: 1)(values: Singleton());
definition U Apply<T,U>(Fn(T input) -> U function, T value) => function(input: value);
definition Nat Higher() => Apply(implementation => implementation + 1, value: 41);
"""),
        ("required-static-values-and-dependent-indices", """module StaticReplay;
const Nat Base = 21;
definition Nat Twice(Nat value) => let copy = value in copy + copy;
const Nat Answer = Twice(value: Base);
const bool Accepted = Answer <= 42;
const Unit Nothing = ();
Nat Local() { const Nat Next = Answer + 1; return Next; }
const Nat Count = 1;
definition Vec<Nat,Count> One() => VCons(7, VNil<Nat>());
lemma Correct() ensures Answer == 42 proof { assert Answer == 42; }
"""),
        ("compositional-static-and-runtime-calls", """module StaticCallsReplay;
public const Nat Square(Nat value) => value * value;
const Nat Limit = Square(4);
Nat Scale(const Nat factor, Nat value) {
    const Nat multiplier = Square(factor);
    return multiplier * value;
}
Nat Forward(const Nat factor, Nat value) => Scale(factor: factor, value: value);
Nat Runtime(Nat value) => Forward(factor: 4, value: value);
Nat RuntimeSquare(Nat value) => Square(value);
lemma Specialized() ensures Runtime(3) == 48 proof { assert Runtime(3) == 48; }
lemma DualPhase() ensures RuntimeSquare(3) == 9 proof { assert RuntimeSquare(3) == 9; }
"""),
        ("static-callable-telescopes-and-lambdas", """module StaticCallableReplay;
alias StaticMap = Fn(const Nat factor, Nat value) -> Nat;
definition StaticMap Build() => (const Nat factor, Nat value) => factor * value;
definition StaticMap Explicit() => Fn(const Nat factor, Nat value) -> Nat => factor * value;
definition Nat Partial(Nat value) => Build()(factor: 4)(value: value);
definition T Select<T>(const Nat index, T value) => value;
definition Nat Generic(Nat value) => Select(index: 0, value: value);
lemma Correct() ensures Partial(3) == 12 proof { assert Partial(3) == 12; }
lemma TypedCorrect() ensures Explicit()(factor: 5, value: 3) == 15 proof { assert Explicit()(factor: 5, value: 3) == 15; }
"""),
        ("nullary-and-explicit-unit-values", """module ArityReplay;
definition Nat Empty() => 7;
definition Nat Explicit(Unit token) => 7;
definition Nat UseEmpty() => Empty();
definition Nat UseExplicit() => Explicit(token: ());
definition Nat UseLambda() => (() => 7)();
definition Fn(Unit published) -> Nat Build() => actual => 7;
definition Nat UseBuilt() => Build()(published: ());
"""),
        ("pattern-matching-and-destructuring", """module PatternReplay;
definition (TRight, TLeft) Swap<TLeft, TRight>((TLeft, TRight) pair) =>
    let (left, right) = pair in (right, left);
definition Nat Predecessor(Nat value) =>
    match (value) {
        0 => 0,
        Succ(previous) => previous,
    };
Nat Classify((bool, Nat) item) {
    let (flag, count) = item;
    match ((flag, count)) {
        case (true, 0): return 1;
        case (true, Succ(rest)): return rest + 2;
        case (false, _): return 0;
    }
}
lemma PredecessorStep(Nat value) ensures Predecessor(Succ(value)) == value proof {
    assert Predecessor(Succ(value)) == value;
}
definition bool Flip(bool flag) =>
    match (flag) {
        true => false,
        false => true,
    };
lemma BoolInvolution(bool flag) ensures Flip(Flip(flag)) == flag proof {
    match (flag) {
        case true: assert Flip(Flip(true)) == true;
        case false: assert Flip(Flip(false)) == false;
    }
}
lemma PairEta<TLeft, TRight>((TLeft, TRight) pair)
    ensures pair == (Fst(pair), Snd(pair)) proof {
    match (pair) as whole : type[Eq(whole, (Fst(whole), Snd(whole)))] {
        case (left, right): assert (left, right) == (Fst((left, right)), Snd((left, right)));
    }
}
"""),
        ("raw-strings-and-checked-formatting", '''module CheckedFormattingReplay;
public definition Vec<Nat, 10> HeaderTag() =>
    """
    [vela-hdr]
    """;
public const Nat HeaderBytes = ByteLength(HeaderTag());
public TextBuilder<36> FormatPacket(Nat id, bool ok) {
    let TextBuilder<36> builder = EmptyBuilder();
    let TextBuilder<36> withHeader = Format.Write(ref builder, $"hdr={HeaderTag()} ");
    let TextBuilder<36> complete = Format.Write(ref withHeader, $"id=0x{id:x4} ok={ok}");
    return complete;
}
public TextBuilder<12> OverflowPacket(Nat id) {
    let TextBuilder<12> tiny = EmptyBuilder();
    return Format.Write(ref tiny, $"hdr={HeaderTag()} id=0x{id:x4}");
}
public lemma DedentedHeaderLength() ensures HeaderBytes == 10 proof { assert HeaderBytes == 10; }
public theorem PacketFitsForEveryId() ensures forall (Nat id) => Fits(FormatPacket(id, true)) == true
    proof { assert Fits(FormatPacket(id, true)); }
public lemma PacketWrites32Bytes() ensures Written(FormatPacket(42, true)) == 32 proof { assert Written(FormatPacket(42, true)) == 32; }
public lemma SmallBufferFailsClosed() ensures Fits(OverflowPacket(42)) == false proof { assert Fits(OverflowPacket(42)) == false; }
public definition Nat Scale(Nat factor, Nat value) => factor * value;
public TextBuilder<48> FormatComputed(Nat id) {
    let TextBuilder<48> b = EmptyBuilder();
    return Format.Write(ref b, $"next=0x{id + 1:x4} scaled=0x{Scale(factor: 2, value: id):x4}");
}
public lemma ComputedWrites25Bytes() ensures Written(FormatComputed(5)) == 25 proof { assert Written(FormatComputed(5)) == 25; }
'''),
        ("ergonomic-expressions-patterns-updates-guards-and-properties", '''module ErgonomicsReplay;
public record Counter(Nat Value, Nat Limit) {
    public bool AtLimit => this.Value >= this.Limit;
    public Nat Remaining => this.Limit - this.Value;
}
public Nat DefaultStep => 1;
public definition Counter Advance(Counter counter, Nat step) =>
    if (counter.AtLimit) counter
    else counter with { Value = counter.Value + step };
public definition Counter Reconfigure(Counter counter, Nat value, Nat limit) =>
    counter with { Value = value, Limit = limit };
public definition Nat Unpack(Counter counter) =>
    match (counter) {
        Counter(Value: current, Limit: maximum) =>
            if (current <= maximum) maximum - current else 0,
    };
public Nat StepIfPositive(Nat value, Counter counter) {
    let Succ(previous) = value else {
        return counter.Value;
    }
    let Counter(Value: base, Limit: limit) = counter;
    if (previous is Succ(inner)) {
        return base + inner + limit;
    } else {
        return base + limit;
    }
}
public definition Nat ExprIfIs(Nat value) =>
    if (value is Succ(previous)) previous + 10 else 0;
public definition bool HasSuccessor(Nat value) => value is Succ(_);
public TextBuilder<24> FormatCounter(Counter counter) {
    let TextBuilder<24> builder = EmptyBuilder();
    return Format.Write(ref builder, $"v=0x{counter.Value:x4} r=0x{counter.Remaining:x4}");
}
public lemma AdvanceStep()
    ensures Advance(Counter(Value: 2, Limit: 5), DefaultStep).Value == 3
    proof { assert Advance(Counter(Value: 2, Limit: 5), DefaultStep).Value == 3; }
public lemma ReconfigureBoth()
    ensures Reconfigure(Counter(Value: 1, Limit: 2), 4, 9).Remaining == 5
    proof { assert Reconfigure(Counter(Value: 1, Limit: 2), 4, 9).Remaining == 5; }
public lemma UnpackMatchesRemaining()
    ensures Unpack(Counter(Value: 2, Limit: 5)) == Counter(Value: 2, Limit: 5).Remaining
    proof { assert Unpack(Counter(Value: 2, Limit: 5)) == Counter(Value: 2, Limit: 5).Remaining; }
public lemma GuardEarlyExit()
    ensures StepIfPositive(0, Counter(Value: 10, Limit: 5)) == 10
    proof { assert StepIfPositive(0, Counter(Value: 10, Limit: 5)) == 10; }
public lemma GuardRefinedBranch()
    ensures StepIfPositive(2, Counter(Value: 10, Limit: 5)) == 15
    proof { assert StepIfPositive(2, Counter(Value: 10, Limit: 5)) == 15; }
public lemma ExprIfIsCheck()
    ensures (ExprIfIs(3) == 12 && HasSuccessor(3) && !HasSuccessor(0)) == true
    proof { assert (ExprIfIs(3) == 12 && HasSuccessor(3) && !HasSuccessor(0)) == true; }
public lemma FormatCounterLength()
    ensures Written(FormatCounter(Counter(Value: 2, Limit: 5))) == 17
    proof { assert Written(FormatCounter(Counter(Value: 2, Limit: 5))) == 17; }
'''),
        ("tagged-union-declarations-and-elimination", '''module UnionReplay;
public union Option<TValue> {
    None();
    Some(TValue Value);
}
public union Status {
    Idle();
    Busy(Nat Step);
    Split(Nat Left, Nat Right);
}
public definition TValue UnwrapOr<TValue>(Option<TValue> item, TValue fallback) =>
    match (item) {
        None() => fallback,
        Some(Value: inner) => inner,
    };
public definition Nat MeasureStatus(Status status) =>
    match (status) {
        Idle() => 0,
        Busy(Step: current) => current,
        Split(Left: left, Right: right) => left + right,
    };
public Nat UnwrapGuarded(Option<Nat> item, Nat fallback) {
    let Some(Value: current) = item else {
        return fallback;
    }
    return if (item is Some(inner)) current + inner else fallback;
}
public lemma UnwrapSome(Nat value, Nat fallback)
    ensures UnwrapOr(Some(Value: value), fallback) == value
    proof { assert UnwrapOr(Some(Value: value), fallback) == value; }
public lemma MeasureSplit()
    ensures MeasureStatus(Split(Left: 3, Right: 4)) == 7
    proof { assert MeasureStatus(Split(Left: 3, Right: 4)) == 7; }
public lemma GuardedSome()
    ensures UnwrapGuarded(Some(5), 0) == 10
    proof { assert UnwrapGuarded(Some(5), 0) == 10; }
public lemma OptionRoundTrip(Option<Nat> item)
    ensures (match (item) {
        None() => None<Nat>(),
        Some(value) => Some<Nat>(value),
    }) == item
    proof {
        match (item) {
            case None():
                assert (match (None<Nat>()) {
                    None() => None<Nat>(),
                    Some(value) => Some<Nat>(value),
                }) == None<Nat>();
            case Some(value):
                assert (match (Some<Nat>(value)) {
                    None() => None<Nat>(),
                    Some(inner) => Some<Nat>(inner),
                }) == Some<Nat>(value);
        }
    }
'''),
        ("structural-recursion-inductive-proofs-dependent-records-existentials-and-propagation", '''module Phase2Replay;
public definition Nat AddRec(Nat a, Nat b) decreases a =>
    match (a) {
        0 => b,
        Succ(k) => Succ(AddRec(k, b)),
    };
public Nat DoubleRec(Nat n) decreases n {
    match (n) {
        case 0:
            return 0;
        case Succ(k):
            return Succ(Succ(DoubleRec(k)));
    }
}
public lemma AddZeroRight(Nat n) ensures n + 0 == n
    proof {
        match (n) {
            case 0:
                assert 0 + 0 == 0;
            case Succ(k):
                assert Succ(k) + 0 == Succ(k) by AddZeroRight(k);
        }
    }
public lemma AddSuccRight(Nat a, Nat b) ensures a + Succ(b) == Succ(a + b)
    proof {
        match (a) {
            case 0:
                assert 0 + Succ(b) == Succ(0 + b);
            case Succ(k):
                assert Succ(k) + Succ(b) == Succ(Succ(k) + b) by AddSuccRight(k, b);
        }
    }
public theorem AddComm(Nat a, Nat b) ensures a + b == b + a
    proof {
        match (a) {
            case 0:
                assert 0 + b == b + 0 by AddZeroRight(b);
            case Succ(k):
                assert Succ(k) + b == b + Succ(k) by {
                    assert Succ(k + b) == Succ(b + k) by AddComm(k, b);
                    assert b + Succ(k) == Succ(b + k) by AddSuccRight(b, k);
                }
        }
    }
public lemma DoubleIsAddSelf(Nat n) ensures DoubleRec(n) == n + n
    proof {
        match (n) {
            case 0:
                assert DoubleRec(0) == 0 + 0;
            case Succ(k):
                assert DoubleRec(Succ(k)) == Succ(k) + Succ(k) by {
                    assert Succ(Succ(DoubleRec(k))) == Succ(Succ(k + k)) by DoubleIsAddSelf(k);
                    assert k + Succ(k) == Succ(k + k) by AddSuccRight(k, k);
                }
        }
    }
public record BoundedVec<TElement>(Nat Length, Vec<TElement, Length> Items) {
    public Nat Size => this.Length;
}
public record BoundedIndex(Nat Limit, Fin<Limit> Index);
public definition BoundedVec<Nat> SingletonBounded() =>
    BoundedVec(Length: 1, Items: VCons(7, VNil<Nat>()));
public definition Nat BoundedHead(BoundedIndex b, Vec<Nat, b.Limit> values) =>
    At(values, b.Index);
public definition BoundedIndex ResetBounded(BoundedIndex b) =>
    b with { Limit = 1, Index = FZero<0>() };
public definition Nat UnpackBoundedSize<TElement>(BoundedVec<TElement> packed) =>
    match (packed) {
        BoundedVec(Length: n, Items: _) => n,
    };
public lemma SingletonBoundedSize() ensures SingletonBounded().Size == 1
    proof { assert SingletonBounded().Size == 1; }
public lemma UnpackSingletonBounded() ensures UnpackBoundedSize(SingletonBounded()) == 1
    proof { assert UnpackBoundedSize(SingletonBounded()) == 1; }
public lemma ExistsWitness(Nat n) ensures exists (Nat m) => m + 0 == n
    proof {
        assert exists (Nat m) => m + 0 == n by {
            assert n + 0 == n by AddZeroRight(n);
        }
    }
public union Option<TValue> {
    None();
    Some(TValue Value);
}
public union Result<TValue, TError> {
    Err(TError Error);
    Ok(TValue Value);
}
public definition Option<Nat> AddOptions(Option<Nat> left, Option<Nat> right) =>
    Some(left? + right?);
public Result<Nat, bool> AddResults(Result<Nat, bool> left, Result<Nat, bool> right) {
    let a = left?;
    let b = right?;
    return Ok(a + b);
}
public lemma PropagateSome() ensures AddOptions(Some(3), Some(4)) == Some(7)
    proof { assert AddOptions(Some(3), Some(4)) == Some(7); }
public lemma PropagateNone() ensures AddOptions(None<Nat>(), Some(4)) == None<Nat>()
    proof { assert AddOptions(None<Nat>(), Some(4)) == None<Nat>(); }
public lemma PropagateOk() ensures AddResults(Ok<Nat, bool>(2), Ok<Nat, bool>(5)) == Ok<Nat, bool>(7)
    proof { assert AddResults(Ok<Nat, bool>(2), Ok<Nat, bool>(5)) == Ok<Nat, bool>(7); }
public lemma PropagateErr() ensures AddResults(Err<Nat, bool>(true), Ok<Nat, bool>(5)) == Err<Nat, bool>(true)
    proof { assert AddResults(Err<Nat, bool>(true), Ok<Nat, bool>(5)) == Err<Nat, bool>(true); }
'''),
    )
    negatives = (
        ("static-parameter-runtime-input", "Nat F(const Nat value) => value; Nat Wrong(Nat runtime) => F(runtime);", "type"),
        ("static-parameter-ignored-runtime-input", "Nat Ignore(Nat value) => 0; Nat F(const Nat value) => value; "
         "Nat Wrong(Nat runtime) => F(Ignore(runtime));", "type"),
        ("static-parameter-higher-order-runtime-input", "alias F = Fn(const Nat index) -> Nat; "
         "definition Nat Wrong(F function, Nat runtime) => function(runtime);", "type"),
        ("static-callable-requirement-erasure", "alias F = Fn(const Nat index) -> Nat; "
         "definition Fn(Nat index) -> Nat Wrong(F function) => function;", "type"),
        ("wrong-call-domain", "definition Nat Identity(Nat x) => x; "
         "definition Nat Wrong() => Identity(true);", "type"),
        ("unequal-vector-index", "definition Vec<Nat,0> Wrong() => VCons(1, VNil<Nat>());", "type"),
        ("out-of-bounds-index", "definition Nat Wrong() => At(VNil<Nat>(), FZero<0>());", "type"),
        ("false-equality-proof", "lemma Wrong() ensures 1 == 2 proof { assert 1 == 2; }", "type"),
        ("false-by-expression", "lemma Same(Nat n) ensures n == n proof { assert n == n; } "
         "lemma Wrong() ensures 1 == 2 proof { assert 1 == 2 by Same(1); }", "type"),
        ("non-proof-by-expression", "lemma Wrong() ensures 1 == 1 proof { assert 1 == 1 by 1; }", "type"),
        ("unrelated-by-block", "lemma Wrong(Nat n) ensures n == n proof { assert n == n by { assert 1 == 1; } }", "type"),
        ("obsolete-refl-combinator", "lemma Wrong() ensures 1 == 1 proof { return Refl(1); }", "name"),
        ("non-proposition", "lemma Wrong() ensures 3 proof { return 3; }", "type"),
        ("unwitnessed-existential-binder", "lemma Wrong() ensures exists (Nat value) => value == value "
         "proof { assert value == value; }", "name"),
        ("existential-invalid-witness", "lemma Wrong() ensures exists (Nat value) => value == 1 "
         "proof { assert exists (Nat value) => value == 1 by 0; }", "type"),
        ("recursion-non-decreasing", "definition Nat Bad(Nat n) => Bad(n);", "type"),
        ("recursion-wrong-decreases-parameter",
         "definition Nat Bad(Nat a, Nat b) decreases a => match (b) { 0 => 0, Succ(k) => Bad(a, k) };", "type"),
        ("recursion-non-nat-decreases", "definition Nat Bad(bool flag) decreases flag => 0;", "type"),
        ("recursion-unknown-decreases", "definition Nat Bad(Nat n) decreases missing => 0;", "name"),
        ("recursion-unapplied-self",
         "definition Nat Use(Fn(Nat) -> Nat f) => f(0); "
         "definition Nat Bad(Nat n) => match (n) { 0 => 0, Succ(k) => Use(Bad) };", "type"),
        ("dependent-record-partial-index-update",
         "public record Bounded(Nat Limit, Fin<Limit> Index); "
         "definition Bounded Wrong(Bounded b) => b with { Limit = 5 };", "type"),
        ("propagate-non-union-operand",
         "public union Option<T> { None(); Some(T Value); } "
         "Option<Nat> Wrong(Nat n) { return Some(n?); }", "type"),
        ("propagate-incompatible-return",
         "public union Option<T> { None(); Some(T Value); } "
         "Nat Wrong(Option<Nat> x) { return x?; }", "type"),
        ("universe-self-typing", "definition Type Wrong() => type Type;", "type"),
        ("unresolved-inference", "definition _ Unknown() => VNil();", "inference"),
        ("unfinished-proof", "lemma Missing() ensures 1 == 1;", "unsupported"),
        ("proof-hole", "definition Nat Hole() => ?proof;", "inference"),
        ("unsupported-contract", "definition Nat Contract() requires true => 0;", "unsupported"),
        ("unbound-value", "definition Nat Wrong() => missing;", "name"),
        ("unknown-call-label", "definition Nat Id(Nat value) => value; "
         "definition Nat Wrong() => Id(missing: 1);", "name"),
        ("out-of-order-call-label", "definition Nat Pick(Nat first,Nat second) => first; "
         "definition Nat Wrong() => Pick(second: 1,first: 2);", "name"),
        ("duplicate-call-label", "definition Nat Pick(Nat first,Nat second) => first; "
         "definition Nat Wrong() => Pick(first: 1,first: 2);", "name"),
        ("positional-after-label", "definition Nat Pick(Nat first,Nat second) => first; "
         "definition Nat Wrong() => Pick(first: 1,2);", "name"),
        ("unnamed-callable-label", "definition Nat Use(Fn(Nat) -> Nat function) => function(value: 1);", "name"),
        ("unnamed-builtin-label", "definition Nat Wrong() => Succ(value: 1);", "name"),
        ("implementation-name-not-interface", "definition Fn(Nat published) -> Nat Build() => implementation => implementation; "
         "definition Nat Wrong() => Build()(implementation: 1);", "name"),
        ("labeled-dependent-index-mismatch", "definition Vec<Nat,n> Keep(Nat n,Vec<Nat,n> values) => values; "
         "definition Vec<Nat,0> Wrong() => Keep(n: 1,values: VNil<Nat>());", "type"),
        ("labeled-false-equality", "definition Nat Id(Nat value) => value; "
         "lemma Wrong() ensures Id(value: 1) == 2 proof { assert Id(value: 1) == 2; }", "type"),
        ("unsupported-use-grade", "definition Nat Graded(Nat value @ 1) => value;", "unsupported"),
        ("unsupported-source-loan", "definition Nat Loan(ref Nat value) => value;", "unsupported"),
        ("constant-runtime-input", "Nat Wrong(Nat runtime) { const Nat value = runtime; return value; }", "type"),
        ("constant-ordinary-let-input", "Nat Wrong() { let runtime = 3; const Nat value = runtime; return value; }", "type"),
        ("constant-ignored-runtime-input", "definition Nat Ignore(Nat unused) => 0; "
         "Nat Wrong(Nat runtime) { const Nat value = Ignore(runtime); return value; }", "type"),
        ("constant-dead-runtime-input", "Nat Wrong(Nat runtime) { "
         "const Nat value = (() => { if(false) { return runtime; } else { return 0; } })(); return value; }", "type"),
        ("constant-ghost-input", "Nat Wrong<ghost Nat index>() { const Nat value = index; return value; }", "type"),
        ("constant-wrong-type", "const Nat Wrong = true;", "type"),
        ("constant-forward-input", "const Nat First = Later; const Nat Later = 3;", "name"),
        ("constant-cyclic-input", "const Nat First = First;", "name"),
        ("constant-noncallable", "const Nat Value = 3; definition Nat Wrong() => Value();", "type"),
        ("constant-false-proof", "const Nat Value = 1; lemma Wrong() ensures Value == 2 proof { assert Value == 2; }", "type"),
        ("omitted-explicit-unit", "definition Nat Id(Unit token) => 1; definition Nat Wrong() => Id();", "type"),
        ("explicit-nullary-unit", "definition Nat Empty() => 1; definition Nat Wrong() => Empty(());", "type"),
        ("empty-lambda-explicit-interface", "definition Fn(Unit token) -> Nat Wrong() => () => 1;", "type"),
        ("explicit-lambda-empty-interface", "definition Fn() -> Nat Wrong() => (Unit token) => 1;", "type"),
        ("nullary-value-explicit-interface", "definition Nat Empty() => 1; "
         "definition Nat Use(Fn(Unit) -> Nat function) => 0; definition Nat Wrong() => Use(Empty);", "type"),
        ("explicit-value-nullary-interface", "definition Nat Explicit(Unit token) => 1; "
         "definition Nat Use(Fn() -> Nat function) => 0; definition Nat Wrong() => Use(Explicit);", "type"),
        ("omitted-unnamed-explicit-unit", "definition Nat Wrong(Fn(Unit) -> Nat function) => function();", "type"),
        ("non-exhaustive-nat-match", "definition Nat Wrong(Nat value) => match (value) { 0 => 0 };", "type"),
        ("non-exhaustive-bool-match", "definition Nat Wrong(bool flag) => match (flag) { true => 1 };", "type"),
        ("duplicate-pattern-binder", "definition Nat Wrong((Nat, Nat) pair) => let (x, x) = pair in x;", "name"),
        ("refutable-local-pattern", "definition Nat Wrong(Nat value) => let Succ(previous) = value in previous;", "type"),
        ("constant-product-growth", f"const Nat Wrong = {10 ** 200} * {10 ** 200};", "limit"),
        ("standalone-interpolated-template", 'definition Vec<Nat, 4> Wrong(Nat id) => $"x={id}";', "type"),
        ("format-write-missing-ref",
         'definition TextBuilder<16> Wrong(TextBuilder<16> b, Nat id) => Format.Write(b, $"x={id:x4}");', "type"),
        ("format-write-non-interpolated",
         'definition TextBuilder<16> Wrong(TextBuilder<16> b) => Format.Write(ref b, """plain""");', "type"),
        ("format-write-unformattable-hole",
         'definition TextBuilder<16> Wrong(TextBuilder<16> b, Unit u) => Format.Write(ref b, $"u={u}");', "type"),
        ("format-write-target-alias-read",
         'definition TextBuilder<16> Wrong(TextBuilder<16> b) => Format.Write(ref b, $"n={Written(b):x4}");', "type"),
        ("format-write-capacity-mismatch",
         'definition TextBuilder<32> Wrong(TextBuilder<16> b) => Format.Write(ref b, $"ok");', "type"),
        ("if-expression-non-bool-condition",
         "definition Nat Wrong(Nat n) => if (n) 1 else 0;", "type"),
        ("if-expression-branch-mismatch",
         "definition Nat Wrong(bool flag) => if (flag) 1 else false;", "type"),
        ("labeled-pattern-unknown-label",
         "public record Pair(Nat Left, Nat Right); "
         "definition Nat Wrong(Pair p) => match (p) { Pair(Missing: x, Right: y) => x };", "name"),
        ("labeled-pattern-out-of-order",
         "public record Pair(Nat Left, Nat Right); "
         "definition Nat Wrong(Pair p) => match (p) { Pair(Right: y, Left: x) => x };", "name"),
        ("labeled-pattern-positional-after-label",
         "public record Pair(Nat Left, Nat Right); "
         "definition Nat Wrong(Pair p) => match (p) { Pair(Left: x, y) => x };", "name"),
        ("labeled-pattern-unnamed-constructor",
         "definition Nat Wrong(Nat n) => match (n) { 0 => 0, Succ(value: k) => k };", "name"),
        ("with-update-non-record",
         "definition Nat Wrong(Nat n) => n with { Value = 1 };", "type"),
        ("with-update-unknown-field",
         "public record Counter(Nat Value); "
         "definition Counter Wrong(Counter c) => c with { Missing = 1 };", "name"),
        ("with-update-out-of-order-fields",
         "public record Pair(Nat Left, Nat Right); "
         "definition Pair Wrong(Pair p) => p with { Right = 1, Left = 2 };", "name"),
        ("with-update-duplicate-field",
         "public record Pair(Nat Left, Nat Right); "
         "definition Pair Wrong(Pair p) => p with { Left = 1, Left = 2 };", "name"),
        ("with-update-field-type-mismatch",
         "public record Counter(Nat Value); "
         "definition Counter Wrong(Counter c) => c with { Value = true };", "type"),
        ("let-else-non-exiting-else",
         "Nat Wrong(Nat n) { let Succ(k) = n else { let unused = 0; } return k; }", "type"),
        ("let-else-else-type-mismatch",
         "Nat Wrong(Nat n) { let Succ(k) = n else { return true; } return k; }", "type"),
        ("let-else-missing-continuation",
         "Nat Wrong(Nat n) { let Succ(k) = n else { return 0; } }", "type"),
        ("property-unknown-member",
         "public record Counter(Nat Value); "
         "definition Nat Wrong(Counter c) => c.Missing;", "name"),
        ("record-duplicate-member",
         "public record Counter(Nat Value) { public Nat Value => 0; }", "name"),
        ("union-non-exhaustive-match",
         "public union Option<T> { None(); Some(T Value); } "
         "definition Nat Wrong(Option<Nat> x) => match (x) { None() => 0 };", "type"),
        ("union-refutable-local-let",
         "public union Option<T> { None(); Some(T Value); } "
         "definition Nat Wrong(Option<Nat> x) => let Some(v) = x in v;", "type"),
        ("union-duplicate-constructor",
         "public union Bad { Case(); Case(Nat Value); }", "name"),
        ("union-pattern-unknown-label",
         "public union Option<T> { None(); Some(T Value); } "
         "definition Nat Wrong(Option<Nat> x) => match (x) { None() => 0, Some(Missing: v) => v };", "name"),
        ("format-write-target-alias-in-binary-hole",
         'definition TextBuilder<16> Wrong(TextBuilder<16> b) => Format.Write(ref b, $"n={Written(b) + 1:x4}");', "type"),
    )
    pure = Fixture("pure-expression-operators", b"""module PureExpressions;
public Nat Difference(Nat left, Nat right) => left - right;
public bool Negate(bool value) => !value;
public bool Both(bool left, bool right) => left && right;
public bool Either(bool left, bool right) => left || right;
public bool DifferentNat(Nat left, Nat right) => left != right;
public bool DifferentBool(bool left, bool right) => left != right;
public bool Less(Nat left, Nat right) => left < right;
public bool Greater(Nat left, Nat right) => left > right;
public bool AtLeast(Nat left, Nat right) => left >= right;
public bool Repeated(bool value) => !!value;
public Nat Mixed() => 2 + 3 * 4 - 5;
public Nat LeftAssociative() => 10 - 3 - 2;
public bool Precedence() => !false || false && false;
public const Nat Underflow = 2 - 5;
public const bool Static = !false && 2 < 3 || false;
""", pure=True, observations=(
        ("f_Difference 2 5", "0"), ("f_Difference 8 3", "5"),
        ("f_Negate true", "false"), ("f_Negate false", "true"),
        ("f_Both true false", "false"), ("f_Both true true", "true"),
        ("f_Either false true", "true"), ("f_Either false false", "false"),
        ("f_DifferentNat 2 3", "true"), ("f_DifferentNat 3 3", "false"),
        ("f_DifferentBool true false", "true"), ("f_DifferentBool false false", "false"),
        ("f_Less 2 3", "true"), ("f_Less 3 3", "false"),
        ("f_Greater 3 2", "true"), ("f_Greater 2 3", "false"),
        ("f_AtLeast 3 3", "true"), ("f_AtLeast 2 3", "false"),
        ("f_Repeated true", "true"), ("f_Mixed", "9"),
        ("f_LeftAssociative", "5"), ("f_Precedence", "true"),
        ("c_Underflow", "0"), ("c_Static", "true")))
    division = Fixture("pure-division-remainder", b"""module PureDivision;
public Nat Quotient(Nat dividend, Nat divisor) => dividend / divisor;
public Nat Remainder(Nat dividend, Nat divisor) => dividend % divisor;
public Nat Mixed() => 2 + 19 % 6 * 3;
public Nat LeftAssociative() => 30 / 4 % 3;
public Nat Grouped() => 20 / (3 * 2);
public Nat DivThenMul() => 20 / 3 * 2;
public Nat ModThenMul() => 20 % 6 * 2;
public Nat StaticDivisor(const Nat divisor, Nat value) {
    const Nat offset = 17 % divisor;
    return value / divisor + offset;
}
public Nat Specialized(Nat value) => StaticDivisor(divisor: 5, value: value);
public const Nat StaticQuotient = 17 / 5;
public const Nat StaticRemainder = 17 % 5;
public const Nat ZeroQuotient = 17 / 0;
public const Nat ZeroRemainder = 17 % 0;
""", pure=True, observations=(
        ("f_Quotient 17 5", "3"), ("f_Remainder 17 5", "2"),
        ("f_Quotient 5 8", "0"), ("f_Remainder 5 8", "5"),
        ("f_Quotient 5 5", "1"), ("f_Remainder 5 5", "0"),
        ("f_Quotient 17 0", "0"), ("f_Remainder 17 0", "17"),
        ("f_Quotient 0 0", "0"), ("f_Remainder 0 0", "0"),
        ("f_Quotient 0 5", "0"), ("f_Remainder 0 5", "0"),
        ("f_Quotient 17 1", "17"), ("f_Remainder 17 1", "0"),
        ("f_Mixed", "5"), ("f_LeftAssociative", "1"),
        ("f_Grouped", "3"), ("f_DivThenMul", "12"), ("f_ModThenMul", "4"),
        ("f_Specialized 23", "6"), ("f_StaticDivisor 0 23", "17"),
        ("c_StaticQuotient", "3"), ("c_StaticRemainder", "2"),
        ("c_ZeroQuotient", "0"), ("c_ZeroRemainder", "17")))
    pure_negatives = (
        ("pure-negation-type", "public bool Wrong() => !1;", "type"),
        ("pure-logical-type", "public bool Wrong() => false || 2;", "type"),
        ("pure-ordering-type", "public bool Wrong() => true < false;", "type"),
        ("pure-inequality-type", "public bool Wrong() => 1 != false;", "type"),
        ("pure-subtraction-type", "public Nat Wrong() => true - 1;", "type"),
        ("pure-division-type", "public Nat Wrong() => true / 2;", "type"),
        ("pure-remainder-type", "public Nat Wrong() => 2 % false;", "type"),
        ("pure-division-static-dependency", "public Nat Wrong(Nat runtime) { "
         "const Nat Value = runtime / 0; return Value; }", "unsupported"),
        ("pure-skipped-name", "public bool Wrong() => false && missing;", "name"),
        ("pure-skipped-runtime-dependency", "public bool Wrong(bool runtime) { "
         "const bool Value = false && runtime; return Value; }", "unsupported"),
    )
    dependent_playground = Fixture("dependent-playground-observations", b'''module DependentPlaygroundReplay;
public definition T Identity<T>(T value) => value;
public definition U Apply<T,U>(Fn(T value) -> U function,T value) => function(value);
public definition Nat HigherOrder() => Apply(function: value => value + 1, value: 41);
public definition Vec<Nat,3> Samples() => VCons(10, VCons(20, VCons(30, VNil<Nat>())));
public definition Nat Second() => At(Samples(), FSucc(FZero<1>()));
public definition bool SelectedValue() => Second() == 20;
public definition Vec<T,n> Copy<T,ghost Nat n>(Vec<T,n> values) => values;
public definition Fn(Nat n,Vec<Nat,n> values) -> Vec<Nat,n> Preserve() =>
    (Nat n,Vec<Nat,n> values) => values;
public definition Vec<Nat,1> Original() => VCons(42, VNil<Nat>());
public definition Nat PreservedValue() =>
    At(Preserve()(n: 1, values: Copy(Original())), FZero<0>());
public definition Vec<Nat,10> HeaderTag() => """[vela-hdr]""";
public TextBuilder<36> FormatPacket(Nat id, bool ok) {
    let TextBuilder<36> builder = EmptyBuilder();
    let TextBuilder<36> withHeader = Format.Write(ref builder, $"hdr={HeaderTag()} ");
    return Format.Write(ref withHeader, $"id=0x{id:x4} ok={ok}");
}
public definition Nat PacketWritten() => Written(FormatPacket(42, true));
public definition bool PacketFits() => Fits(FormatPacket(42, true));
public record Counter(Nat Value, Nat Limit) {
    public bool AtLimit => this.Value >= this.Limit;
    public Nat Remaining => this.Limit - this.Value;
}
public Nat DefaultStep => 1;
public definition Counter Advance(Counter counter, Nat step) =>
    if (counter.AtLimit) counter
    else counter with { Value = counter.Value + step };
public Nat StepIfPositive(Nat value, Counter counter) {
    let Succ(previous) = value else {
        return counter.Value;
    }
    let Counter(Value: base, Limit: limit) = counter;
    return if (previous is Succ(inner)) base + inner + limit else base + limit;
}
public definition Nat AdvancedRemaining() =>
    Advance(Counter(Value: 2, Limit: 5), DefaultStep).Remaining;
public definition Nat GuardedStep() =>
    StepIfPositive(2, Counter(Value: 10, Limit: 5));
''', observations=(
        ("vela_d2_HigherOrder Corelib.Init.Datatypes.tt", "42"),
        ("vela_d4_Second Corelib.Init.Datatypes.tt", "20"),
        ("vela_d5_SelectedValue Corelib.Init.Datatypes.tt", "true"),
        ("vela_d9_PreservedValue Corelib.Init.Datatypes.tt", "42"),
        ("vela_d12_PacketWritten Corelib.Init.Datatypes.tt", "32"),
        ("vela_d13_PacketFits Corelib.Init.Datatypes.tt", "true"),
        ("vela_d23_AdvancedRemaining Corelib.Init.Datatypes.tt", "2"),
        ("vela_d24_GuardedStep Corelib.Init.Datatypes.tt", "15")))
    return (Fixture("authored-example", example), pure, division, dependent_playground,
            *(Fixture(name, ("module PureNegativeReplay; " + source).encode(), expected, pure=True)
              for name, source, expected in pure_negatives),
            *(Fixture(name, source.encode()) for name, source in positives),
            *(Fixture(name, ("module NegativeReplay; " + source).encode(), expected)
              for name, source, expected in negatives))


def _sha256(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _write(path: Path, value: object) -> None:
    with atomic_path(path) as pending:
        pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8", newline="")


def _opam(arguments: list[str]) -> list[str]:
    return ["opam", "exec", "--switch", proofenv.ROCQ_SWITCH, "--", *arguments]


def _run(arguments: list[str], directory: Path, log: Path,
         steps: list[dict[str, object]], *, source: bytes | None = None) -> str:
    if log.exists():
        log = log.with_name(f"{log.stem}-{len(steps)}{log.suffix}")
    started = time.monotonic()
    row: dict[str, object] = {"command": arguments, "directory": str(directory)}
    try:
        done = subprocess.run(arguments, cwd=directory, input=source, capture_output=True,
                              timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"")
        log.write_bytes(output)
        row.update({"status": "timeout", "seconds": round(time.monotonic() - started, 6),
                    "log": str(log), "log_sha256": _sha256(output)})
        steps.append(row)
        raise RuntimeError(f"Vela replay command exceeded {TIMEOUT} seconds") from error
    except OSError as error:
        output = str(error).encode("utf-8")
        log.write_bytes(output)
        row.update({"status": "unavailable", "log": str(log), "log_sha256": _sha256(output)})
        steps.append(row)
        raise
    output = done.stdout + done.stderr
    log.write_bytes(output)
    row.update({"status": "passed" if done.returncode == 0 else "failed", "exit": done.returncode,
                "seconds": round(time.monotonic() - started, 6),
                "log": str(log), "log_sha256": _sha256(output)})
    steps.append(row)
    if done.returncode:
        raise RuntimeError(f"Vela replay command exited {done.returncode}: "
                           + output.decode("utf-8", errors="replace")[-3000:])
    return done.stdout.decode("utf-8")


def _inputs(root: Path) -> dict[str, str]:
    paths = (
        EXAMPLE,
        "tools/opam/rocq.lock",
        "tools/vos/proofenv.py",
        "tools/vos/env.py",
        "tools/vos/vela/elaborate.py",
        "tools/vos/vela/elaborate_types.py",
        "tools/vos/vela/elaborate_protocol.py",
        "tools/vos/vela/elaborate_whnf.py",
        "tools/vos/vela/elaborate_patterns.py",
        "tools/vos/vela/elaborate_proofs.py",
        "tools/vos/vela/elaborate_statements.py",
        "tools/vos/vela/elaborate_strings.py",
        "tools/vos/vela/elaborate_solver.py",
        "tools/vos/vela/elaborate_intrinsics.py",
        "tools/vos/vela/elaborate_declarations.py",
        "tools/vos/vela/authoring.py",
        "tools/vos/vela/ast.py",
        "tools/vos/vela/__init__.py",
        "tools/vos/vela/elaboration_check.py",
        "tools/vos/atomic.py",
    )
    return {**vela_parser._inputs(root),
            **{name: _sha256((root / name).read_bytes()) for name in paths}}


def _toolchain(root: Path, directory: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    lock = (root / "tools/opam/rocq.lock").read_text(encoding="utf-8")
    if set(re.findall(r'"rocq-core\.([^"\s]+)"', lock)) != {proofenv.ROCQ_VERSION}:
        raise ValueError("Vela replay prover differs from the proof snapshot")
    version = _run(_opam(["rocq", "c", "--version"]), directory,
                   directory / "toolchain.log", steps).strip()
    found = re.search(r"\bversion\s+([^\s]+)", version)
    if found is None or found[1] not in {proofenv.ROCQ_VERSION, proofenv.ROCQ_VERSION.removesuffix(".0")}:
        raise ValueError("Vela replay compiler differs from the locked prover")
    compiler = _run(_opam(["ocamlc", "-version"]), directory,
                    directory / "ocaml.log", steps).strip()
    if compiler != proofenv.OCAML_VERSION:
        raise ValueError("Vela replay OCaml differs from the proof snapshot")
    binary = _run(["opam", "var", "bin", "--switch", proofenv.ROCQ_SWITCH], directory,
                  directory / "tool-path.log", steps).strip()
    binary_dir = Path(binary)
    if not binary_dir.is_absolute():
        raise ValueError("Vela replay tool directory must be absolute")
    return {"switch": proofenv.ROCQ_SWITCH, "rocq": version, "ocamlc": compiler,
            "binary_sha256": {name: _sha256((binary_dir / name).read_bytes())
                              for name in ("rocq", "rocqchk", "ocamlc")}}


def _runtime(directory: Path, steps: list[dict[str, object]]) -> dict[str, object]:
    """Bind the actual runtime roots, including user-contrib and plugin inputs."""
    config = _run(_opam(["rocq", "c", "-config"]), directory,
                  directory / "runtime-config.log", steps)
    where = _run(_opam(["rocqchk", "-where"]), directory,
                 directory / "runtime-where.log", steps).strip()
    listing = _run(_opam(["rocq", "top", "-q", "-quiet"]), directory,
                   directory / "runtime-loadpath.log", steps, source=b"Print LoadPath.\n")
    settings = dict(line.split("=", 1) for line in config.splitlines() if "=" in line)
    if any(key not in settings or not Path(settings[key]).is_absolute()
           for key in ("COQLIB", "COQCORELIB")):
        raise ValueError("Vela replay prover library configuration is unsupported")
    if not where or not Path(where).is_absolute():
        raise ValueError("Vela replay kernel library path is unsupported")
    roots = {Path(settings[key]).resolve() for key in ("COQLIB", "COQCORELIB")}
    roots.add(Path(where).resolve())
    lines = re.sub(r"\n\s+(/)", r" \1", listing).splitlines()
    if not lines or lines[0] != "Installed / Logical Path / Physical path:":
        raise ValueError("Vela replay prover load-path listing is unsupported")
    for line in lines[1:]:
        found = re.fullmatch(r"\s*(?:i\s+)?(?:<>|[\w.]+)\s+(/.+)", line)
        if found is None:
            raise ValueError("Vela replay prover load-path row is unsupported")
        path = Path(found[1]).resolve()
        if path != directory.resolve():
            roots.add(path)
    minimal = sorted(path for path in roots
                     if not any(path != other and path.is_relative_to(other) for other in roots))
    files: dict[str, str] = {}
    for root in minimal:
        if not root.is_dir():
            raise ValueError("Vela replay library root is missing")
        for path in sorted(root.rglob("*")):
            if path.is_symlink() and path.is_dir():
                raise ValueError("Vela replay library has a directory alias")
            if path.is_file():
                files[str(path)] = _sha256(path.read_bytes())
    if not files:
        raise ValueError("Vela replay runtime inventory is empty")
    return {"config": config, "load_path": listing, "files_sha256": files}


def _work_root(root: Path) -> Path:
    directory = env.lane_root(env.lane_of(root)) / "vela-elaboration"
    kind = env.filesystem(directory)
    if not kind or kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS:
        raise ValueError("Vela replay outputs require a persistent native filesystem")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _parser_outputs(compiled: vela_parser.Build) -> dict[str, str]:
    outputs = cast("dict[str, str]", compiled.receipt["generated_sha256"])
    current = {name: _sha256((compiled.directory / name).read_bytes())
               for name in (*vela_parser.GENERATED, "vela-parser")}
    if current != outputs:
        raise ValueError("Vela replay parser output changed after its build")
    return current


def _case(compiled: vela_parser.Build, case: Fixture, directory: Path, index: int,
          steps: list[dict[str, object]]) -> dict[str, object]:
    """A parsing failure can never satisfy a semantic negative fixture."""
    stem = f"Case{index:03d}"
    source_path = directory / f"{stem}.vela"
    source_path.write_bytes(case.source)
    parsed = vela_parser.parse_source(compiled, case.source, surface=not case.pure)
    syntax_path = directory / f"{stem}.syntax.json"
    _write(syntax_path, parsed)
    row: dict[str, object] = {"name": case.name, "source": str(source_path),
                              "source_sha256": _sha256(case.source), "expected": case.expected,
                              "consumer": "pure" if case.pure else "mathematical",
                              "syntax": str(syntax_path), "syntax_sha256": _sha256(syntax_path.read_bytes())}
    consume = vela.translate_ast if case.pure else vela_elaborate.elaborate
    try:
        translated = consume(case.source, parsed)
    except VelaError as error:
        row.update({"category": error.kind, "line": error.line, "column": error.column,
                    "message": error.message})
        if error.kind != case.expected or case.expected == "accepted":
            raise ValueError(
                f"Vela replay {case.name}: expected {case.expected}, got {error.kind} "
                f"at {error.line}:{error.column}: {error.message}"
            ) from error
        return row
    if case.expected != "accepted":
        raise ValueError(f"Vela replay {case.name}: expected {case.expected}, source was accepted")
    repeated = consume(case.source, parsed)
    if translated != repeated:
        raise ValueError(f"Vela replay {case.name}: elaboration is nondeterministic")
    module = "Vela_" + translated.module.replace(".", "_")
    checks = "".join(
        f"\nDefinition vela_replay_check_{index} : Corelib.Init.Logic.eq "
        f"({module}.{expression}) ({expected}) := Corelib.Init.Logic.eq_refl ({expected}).\n"
        for index, (expression, expected) in enumerate(case.observations))
    target = directory / f"{stem}.v"
    target.write_text(translated.gallina + checks, encoding="utf-8", newline="")
    _run(_opam(["rocq", "c", "-q", "-R", str(directory), "VelaElaboration", target.name]),
         directory, directory / f"{stem}.compile.log", steps)
    export_pattern = r"[fc]_[A-Za-z_][A-Za-z0-9_]*" if case.pure else r"vela_d[0-9]+_[A-Za-z_][A-Za-z0-9_]*"
    exports = re.findall(r"^Definition (" + export_pattern + r")\s*(?:\(|:)",
                         translated.gallina, flags=re.MULTILINE)
    if not exports:
        raise ValueError(f"Vela replay {case.name}: no generated exports to audit")
    audited = [f"{module}.{name}" for name in exports]
    audited.extend(f"vela_replay_check_{index}" for index in range(len(case.observations)))
    query = directory / f"{stem}Assumptions.v"
    query.write_text(f"From VelaElaboration Require Import {stem}.\n"
                     + "".join(f"Print Assumptions {stem}.{name}.\n" for name in audited),
                     encoding="utf-8", newline="")
    assumptions = _run(_opam(["rocq", "c", "-q", "-R", str(directory), "VelaElaboration", query.name]),
                       directory, directory / f"{stem}.assumptions.log", steps)
    if [line.strip() for line in assumptions.splitlines() if line.strip()] != [
            "Closed under the global context"] * len(audited):
        raise ValueError(f"Vela replay {case.name}: generated exports have unqualified assumptions")
    artifact = directory / f"{stem}.vo"
    row.update({"category": "accepted", "module": translated.module,
                "gallina": str(target), "gallina_sha256": _sha256(target.read_bytes()),
                "assumptions": str(query), "assumptions_sha256": _sha256(query.read_bytes()),
                "assumption_exports": exports,
                "observations": [list(value) for value in case.observations],
                "library": f"VelaElaboration.{stem}", "vo": str(artifact),
                "vo_sha256": _sha256(artifact.read_bytes())})
    return row


def _observations(rows: list[dict[str, object]], steps: list[dict[str, object]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for row in rows:
        for field in ("source", "syntax", "gallina", "assumptions", "vo"):
            if field in row:
                path = Path(str(row[field]))
                digest = _sha256(path.read_bytes())
                expected = str(row[f"{field}_sha256"])
                if digest != expected:
                    raise ValueError("Vela replay artifact changed during qualification")
                files[str(path)] = digest
    for step in steps:
        path = Path(str(step["log"]))
        digest = _sha256(path.read_bytes())
        if digest != step["log_sha256"]:
            raise ValueError("Vela replay process transcript changed during qualification")
        files[str(path)] = digest
    return files


def qualify(root: Path) -> dict[str, object]:
    """Fresh native syntax/term/kernel replay with no production-language verdict."""
    work = _work_root(root)
    with FileLock(work / "qualification.lock", timeout=1):
        latest = work / "qualification.json"
        latest.unlink(missing_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="replay-", dir=work))
        steps: list[dict[str, object]] = []
        rows: list[dict[str, object]] = []
        attempt: dict[str, object] = {"schema": 1, "scope": "vela-elaboration-kernel-replay",
                                      "status": "running", "directory": str(directory),
                                      "steps": steps, "fixtures": rows, "checked_parser": False,
                                      "source_correspondence": False, "production_admission": False}
        _write(directory / "attempt.json", attempt)
        try:
            inputs = _inputs(root)
            tools = _toolchain(root, directory, steps)
            runtime = _runtime(directory, steps)
            compiled = vela_parser.build(root)
            parser_receipt = copy.deepcopy(compiled.receipt)
            outputs = _parser_outputs(compiled)
            attempt.update({"inputs": inputs, "toolchain": tools, "runtime": runtime,
                            "parser": parser_receipt, "parser_outputs": outputs})
            for index, case in enumerate(fixtures(vela_parser.read_source(root / EXAMPLE))):
                rows.append(_case(compiled, case, directory, index, steps))
                _write(directory / "attempt.json", attempt)
            libraries = [str(row["library"]) for row in rows if row["category"] == "accepted"]
            _require(bool(libraries), "Vela replay has no accepted library to kernel-check")
            _run(_opam(["rocqchk", "-R", str(directory), "VelaElaboration", *libraries]),
                 directory, directory / "kernel.log", steps)
            _require(_inputs(root) == inputs and _toolchain(root, directory, steps) == tools
                     and _runtime(directory, steps) == runtime,
                     "Vela replay inputs, toolchain or runtime changed during qualification")
            _require(compiled.receipt == parser_receipt and _parser_outputs(compiled) == outputs
                     and vela_parser._toolchain(root) == parser_receipt["toolchain"],
                     "Vela replay parser identity changed during qualification")
            attempt.update({"status": "passed", "kernel_checked": True,
                            "artifacts_sha256": _observations(rows, steps)})
            _write(directory / "attempt.json", attempt)
            _write(latest, attempt)
        except Exception as error:
            attempt.update({"status": "failed", "kernel_checked": False,
                            "error": f"{type(error).__name__}: {error}"})
            _write(directory / "attempt.json", attempt)
            raise
        else:
            return attempt
