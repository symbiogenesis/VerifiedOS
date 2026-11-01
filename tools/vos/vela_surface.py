# SPDX-License-Identifier: Apache-2.0
"""Independent expected syntax and rejection cases for Vela's wider surface.

These cases describe source behavior, not semantic acceptance. In particular,
unknown names, duplicate declarations and invalid resource use must still parse.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vos.vela import MAX_SOURCE_BYTES, VelaError

if TYPE_CHECKING:
    from vos.vela_parser import Json


@dataclass(frozen=True)
class Fixture:
    name: str
    source: str
    kinds: tuple[str, ...]


POSITIVE: tuple[Fixture, ...] = (
    Fixture("kinded-telescopes-and-associated-families", """// café: kinds have spans distinct from their binders.
module KindedFamilies;
universe u;
alias Scoped<T : Type<u>, region 'loan> = Fn(scoped ref<'loan> T value) -> ();
alias Plain<U> = U;
trait Family<T : Type<u>> {
    type Value<U : Type<u>> : Type<u> where Formed(U);
    type Selected : Type<u> where Stable(T) = T;
    type Legacy;
    predicate Readable(T value) requires Ready(value) = Stable(value);
    predicate Closed(T value) where Law(T);
}
""", ("generic_parameter", "associated_type", "predicate", "contract", "function_type")),
    Fixture("type-valued-dependent-matches", """// café: structural types stay inside explicit type expressions.
module TypeFamilies;
universe u;
definition Type<u> LoanType<T : Type<u>>(bool exclusive) where Stable(T) =
    match (exclusive) as mode : Type<u> {
        case true => type ref T;
        case false => type in T;
    };
definition Type<u> Product<T>() = type (owned T, tracked Receipt);
definition Type<u> UnitType() = type ();
definition Type<u> Callback<T>() = type (Fn<region 'local>(
    scoped ref<'local> T value @ NatExact(1)) -> ()
    with { restores Valid(value); });
public void Inspect() { Compare((type Nat), (type bool)); }
""", ("definition", "type_expression", "match_expression", "match_motive", "tuple_type", "unit_type")),
    Fixture("callable-kinds-and-contract-effect-ownership", """// café: grouping fixes which interface owns each effect.
module CallableKinds;
universe u;
alias Higher<F : (Fn(Type<u> value) -> Type<u>)> = F;
trait Kinded<T : Type<u>> {
    type Build : (Fn(Type<u>) -> Type<u>) where Formed(T);
}
union Factories<T> {
    Bare(Fn() -> T callback) : Fn() -> T effects(Read) requires Available(callback);
    Grouped() : (Fn() -> T effects(Read)) effects writes(Storage);
}
public void RequiresType()
    requires type (Fn() -> bool effects(Read))
    effects writes(Storage);
""", ("generic_parameter", "group_type", "function_type", "constructor", "type_expression", "effects")),
    Fixture("typed-callable-values-and-scoped-loans", """// café: a callable value reuses its annotation's exact resource roles.
module CallableValues;
universe u;
public void Use<T : Type<u>, captures C, grade q : NatExact>(in Cell<T> cell) {
    let update = FnMut<region 'r>(scoped ref<'r> T slot @ q) -> ()
        captures C effects(Write)
        with { requires Valid(slot); restores Closed(final(slot)); }
        => { Mutate(ref slot); return; };
    cell.WithWrite(update);
    let consume = FnOnce(owned T item @ NatExact(1)) -> T
        with { ensures Returned(result); } => move item;
    let classify = Fn(bool flag) -> Type<u> =>
        match (flag) { case true => type T; case false => type (); };
}
""", ("typed_lambda", "function_type", "modified_type", "contract", "type_expression", "match_expression")),
    Fixture("typed-callable-expression-composition", """// café: explicit signatures compose wherever values occur.
module CallableComposition;
public void Compose() {
    Fn(Nat n) -> Nat => n;
    Apply(Fn(Nat x) -> Nat => x + 1, FnOnce() -> () => { return; });
    Fn(Nat) -> Nat annotated = Fn(Nat item) -> Nat => item;
    let returning = Fn() -> (Fn(Nat) -> Nat) => Fn(Nat value) -> Nat => value;
    let graded = Fn(Nat input @ Grade.Of(Fn(Nat sample) -> Nat => sample)) -> Nat => input;
    let inferred = (Nat value @ Grade.Of(Fn() -> Nat => { return 1; })) => value;
}
""", ("typed_lambda", "function_type", "expression_statement", "typed_local", "lambda", "group_type")),
    Fixture("indexed-family-and-constructor-contracts", """// café: family and constructor laws retain different owners.
module IndexedFamilies;
universe u;
union Outcome<T : Type<u>> where Separated(T) {
    Ready(owned T value @ NatExact(1)) : Outcome<T> ensures Retained(value);
    Rejected(tracked Receipt receipt) : Outcome<T> restores Closed(receipt);
    Empty();
}
inductive Vec<T : Type<u>, ghost Nat n> where Admissible(T) {
    Nil() : Vec<T, 0> ensures EmptyVector(result);
    Cons(T head, Vec<T, n> tail) : Vec<T, (n + 1)> requires Bounded(n);
}
coinductive Stream<T> where Guarded(T) {
    More(T head, Stream<T> tail) : Stream<T> ensures Productive(result);
}
definition Nat Count<T>(in Outcome<T> value) requires Available(value)
    ensures Stable(result) = 0;
union Legacy { Done(); }
definition Nat Zero() = 0;
""", ("union", "inductive", "coinductive", "constructor", "contract", "definition")),
    Fixture("stable-literal-generic-arguments", """// café: generic literal spelling is not normalized.
module StableArguments;
alias Flags = FlagsOf<true, false>;
alias Label = Named<"wire", 'x', ?missing>;
alias Mixed = Indexed<0002usize, true, (n + 1), type (owned Packet, tracked Receipt)>;
public void Use() { Select::<true, "tag", 'z', ?choice>(value); }
""", ("bool", "string", "character", "hole", "type_argument", "generic_application")),
    Fixture("typed-resource-errors-remain-syntax", """module InvalidTypedResources;
universe u;
alias NonType<T : Nat> = T;
definition Type<u> ErasedChoice(ghost bool flag) =
    match (flag) { case true => type Packet; case false => type (); };
public async void Invalid(owned Packet packet, tracked Receipt receipt) {
    let duplicate = Fn(owned Packet p @ NatExact(0)) -> (Packet, Packet)
        => (move p, move p);
    let escape = Fn<region 'local>(scoped ref<'local> Packet p) -> ref<'local> Packet
        => ref p;
    let suspended = FnOnce(scoped ref Packet p) -> ()
        => { await Ready(); return; };
    Use(move receipt, move receipt);
}
""", ("generic_parameter", "type_expression", "typed_lambda", "unary", "tuple")),
    Fixture("effect-operation-resource-contracts", """// café: contract and grade spans use original UTF-8 bytes.
module ResourceEffects;
public effect Exchange<T, ghost Nat n> {
    owned Buffer<T, n> Replace(owned Buffer<T, n> replacement @ NatExact(1),
        tracked Permit<n> permit) resumes(0..1)
        requires Available(replacement)
        ensures Returned(result)
        restores Closed(result)
        effects writes(replacement);
    ref<'input> T Borrow(ref Buffer<T, n> input) resumes(1)
        requires Nonempty(input) restores Preserved(input, final(result));
    void Observe() requires ObserverReady();
    void Plain();
}
""", ("effect", "effect_operation", "generic_parameter", "modified_type", "contract", "effects")),
    Fixture("container-resource-contracts", """// café: container obligations stay outside their members.
module ResourceContainers;
public struct LocalCell<T, grade q : NatExact>
    where Shape(T)
    invariant Closed(self)
{
    private T Value @ q;
    public void Close() requires Opened(self) ensures Closed(self);
}
public interface Storage<T> where StorageLaw(T) {
    operation T Read() requires Readable(self) ensures Stable(result);
    struct Nested invariant InnerLaw() {}
}
public trait Repeatable<T, grade q : NatExact> where Admits(T, q) {
    public (Box<T, q>, Box<T, q>) Split(owned Box<T, q> value)
        requires Dup(value);
}
public machine Counter invariant Bounded(value) {
    state Nat value = 0;
    transition Step() when (value < 10) { next value = value + 1; }
}
public hardware Clocked where PhysicalLaw() invariant Bounded(count) {
    register Nat count = 0;
    rule Tick() { next count = count + 1; }
}
private struct Empty {}
""", ("struct", "interface", "trait", "machine", "hardware", "contract", "field", "operation")),
    Fixture("named-handler-capabilities", """// café: repeated names retain distinct binding spans.
module NamedHandlers;
public Nat Nested() {
    return handle (handle (inner.Read()) as inner {
        Read() with nested => resume nested(outer.Read()),
        return x => x,
    }) as outer {
        Read() with k => resume k(0),
        return value => value,
    };
}
public Nat Reinstall() {
    let restored = handle shallow (current.Read()) as current {
        Read() with k => rehandle (resume k(1)) as replacement {
            Read() with resumed => resume resumed(2),
            return raw => raw,
        },
        return done => done,
    };
    let unnamed = handle (Pure()) { return value => value, };
    return restored;
}
public Nat Shadow() {
    return handle (handle (same.Read()) as same { return inner => inner, })
        as same { return outer => outer, };
}
""", ("handle", "rehandle", "resume", "call", "member")),
    Fixture("effect-resource-errors-remain-syntax", """module InvalidEffectResources;
public effect Unsafe<T> {
    owned T Duplicate(owned T value @ NatExact(0)) resumes(0..2)
        requires Missing(value) restores Unproved(result);
}
public struct Broken invariant false { tracked Permit Debt; }
public Nat Escape(ref BorrowCell<byte> cell) {
    return handle (chosen.Read()) as chosen {
        Read() with k => {
            let stolen = chosen;
            cell.WithTryWrite((scoped ref byte loan) => {
                await Ready();
                return chosen.Read();
            });
            dispose k;
            return resume k(0);
        },
        return value => chosen,
    };
}
""", ("effect_operation", "struct", "handle", "lambda", "dispose", "resume")),
    Fixture("dependent-match-expressions-and-motives", """// café: motive and field locations are original UTF-8 bytes.
module Elimination;
public Vec<byte, packet.Length> Unpack(owned Packed packet) {
    return match (move packet) as packed : Vec<byte, packed.Length> {
        case Packed(let count, let bytes) => bytes;
    };
}
public Nat Inspect(owned Selection selected) {
    match (move selected) as choice : Nat {
        case Ready(let payload): return payload.Length;
        case Rejected(let debt): Close(move debt); return 0;
    }
}
public Nat Nested(bool flag) {
    return 2 + match (flag) {
        case true => match (other) { case false => 3; case true => 4; };
        case false => 5;
    } * 3;
}
public Result<ref<'workspace.bytes> byte, Error> Borrow(ref Workspace workspace) {
    return Wrap(match (Find(ref workspace)) as outcome : LoanResult<outcome> {
        case Ok(let selected) => Ok(selected);
        case Err(let error) => Err(error);
    });
}
""", ("match_expression", "expression_case", "match_motive", "match", "case", "modified_type")),
    Fixture("graded-struct-fields", """// café: grades have spans separate from initializers.
module GradedFields;
public struct Box<T, grade q : NatExact> {
    public T Value @ q;
    private tracked Permit Debt @ NatExact(1);
    public Nat Count @ (q + 1) = 0;
    private Nat Plain;
}
""", ("struct", "field", "generic_parameter", "modified_type")),
    Fixture("generic-library-implementations", """module GenericInstances;
public impl<T, grade q : NatExact> Dup<Box<T, q>>
    where Repeatable(T, q)
    requires Available(T)
{
    public (Box<T, q>, Box<T, q>) Split(owned Box<T, q> box)
        ensures SplitLaw(old(box), result);
}
private impl (Fn() -> Nat effects(Read)) where Reusable(Read) {}
""", ("impl", "generic_parameter", "contract", "function", "tuple_type")),
    Fixture("locally-quantified-callable-contracts", """// café: callback and enclosing contracts remain distinct.
module ScopedCallbacks;
alias Update<T, captures C> = Fn<region 'loan, grade q : NatExact>(
    scoped ref<'loan> T value @ q) -> () captures C effects(Write)
    with { requires Valid(value); restores Valid(final(value)); };
public void Apply<T>(in Fn<region 'local>(scoped ref<'local> T selected) -> ()
    with { requires CallbackReady(selected); restores CallbackClosed(selected); } callback)
    requires CallerReady(callback)
    ensures CallerClosed(callback);
alias Plain = Fn(byte) -> byte;
""", ("alias", "function_type", "generic_parameter", "modified_type", "contract")),
    Fixture("dependent-elimination-errors-remain-syntax", """module InvalidElimination;
public async Nat Bad(ref BorrowCell<byte> cell, tracked Permit permit) {
    let incompatible = match (cell.TryWrite()) as observed : Bytes<observed.Length> {
        case Acquired(let writer, let debt) => (move permit, move permit);
        case BorrowConflict => 0;
    };
    let escaping = match (incompatible) as erased : Never<missing> {
        case _ => (scoped ref byte loan) => { await Ready(); return loan; };
    };
    return escaping;
}
""", ("match_expression", "match_motive", "tuple", "lambda", "wildcard_pattern", "unary")),
    Fixture("dependent-callable-telescopes", """// café: positions below count original UTF-8 bytes.
module CallableTypes;
alias Dependent<captures C, grade q : NatExact> =
    Fn(Nat n, in Span<byte, n> bytes @ q) -> Vec<byte, n> captures C effects(Read);
alias Unnamed = Fn(byte) -> byte;
alias Consuming = FnOnce(owned Buffer storage, tracked Permit permit) -> (owned Buffer, tracked Permit);
alias Higher = Fn(in Fn(Nat width) -> Vec<byte, width> build, Nat count) -> (Vec<byte, count>, ());
public void Use<grade q : NatExact>(in Fn(Nat count) -> Vec<byte, count> build) {
    let project = (Nat n @ q, byte value @ NatExact(1)) => (n, value);
    Apply((scoped ref byte selected @ NatExact(1)) => { selected = 0byte; });
}
""", ("alias", "function_type", "parameter", "lambda_parameter", "tuple_type", "tuple")),
    Fixture("product-types-values-and-patterns", """module Products;
alias Pair<T, U> = (T, U);
alias Group = (Nat);
alias Empty = ();
public (owned Buffer, (tracked Permit, ())) Package(owned Buffer buffer, tracked Permit permit) {
    return (move buffer, (move permit, ()));
}
public () Consume((owned Buffer, (tracked Permit, ())) package) {
    let (let owner, (let receipt, ())) = package;
    var (let left, let right) = (1, 2);
    match ((move owner, (move receipt, ()))) {
        case (let live, (let token, ())):
            Finish(move live, move token);
    }
    match (left) { case _: return (); }
}
""", ("tuple_type", "group_type", "unit_type", "tuple", "unit", "tuple_pattern",
      "unit_pattern", "wildcard_pattern", "let_pattern", "var_pattern")),
    Fixture("grade-and-comparison-boundaries", """module GradedClosures;
public void Use() {
    let first = (Nat x @ (left < right)) => x;
    let second = (Core.Byte x @ Grade.Combine(q, r), Nat y @ q * r + s) => y;
    let third = (Core.Box<(')')> x @ q) => x;
    let comparison = (left < right, low > high);
    let dormant = () => ();
}
""", ("lambda", "lambda_parameter", "binary", "tuple", "unit")),
    Fixture("callback-expressions-in-grades", """module CallbackGrades;
public void Declared(Nat x @ Grade.Of((Nat n) => {
    let marker = "}; ) @";
    let delimiter = '}';
    /* }; ) @ */ return n;
}));
public void Use() {
    let callback = (Nat x @ Grade.Of((Nat n) => {
        let marker = "}; ) @";
        let delimiter = '}';
        /* }; ) @ */ return n;
    })) => x;
}
""", ("parameter", "lambda_parameter", "lambda", "block", "string", "character", "return")),
    Fixture("explicit-structural-type-arguments", """module TypeArguments;
alias Returned = Result<type (owned Packet, tracked Receipt), Error>;
alias Function = Box<type Fn(Nat n) -> Vec<byte, n>>;
alias Grouped = Box<type (Nat)>;
alias Unit = Box<type ()>;
alias Value = Indexed<((a, b))>;
public void Use() { Construct::<type (Nat, bool)>(value); }
""", ("tuple_type", "function_type", "group_type", "unit_type", "tuple", "generic_application")),
    Fixture("structural-local-and-lambda-annotations", """module StructuralAnnotations;
public void Use(ref Span<byte> text) {
    ref<'self.text> (Span<byte>) local = ref text;
    (owned Packet, tracked Receipt) package = source;
    () empty = ();
    let pairIdentity = ((owned Packet, tracked Receipt) pair) => pair;
    let unitIdentity = (() value) => value;
    let groupedIdentity = ((Nat) number) => number;
}
""", ("typed_local", "modified_type", "group_type", "tuple_type", "unit_type", "lambda")),
    Fixture("unbraced-conditionals-and-annotation-lookahead", """module Unbraced;
public void Bare(bool ready) { if (ready) value = 1; }
public void Paired(bool ready) { if (ready) value = 1; else value = 2; }
public void Nearest(bool ready, bool permitted) {
    if (ready) if (permitted) value = 1; else value = 2;
}
public void Chain(bool ready, bool permitted) {
    if (ready) value = 1; else if (permitted) value = 2; else value = 3;
}
public void Trivia(bool ready) { if /* (not a type) */ (ready) value = 1; }
""", ("if", "assignment")),
    Fixture("dependent-resources-and-borrow-restoration", """module Resources;
public record Packed<T>(usize Length, owned Buffer<T, Length> Storage,
    ghost Bounded<Length> Evidence);
public union Initialized<ghost Nat n> {
    Ready(owned Buffer<byte, n, Full> buffer, tracked PreparationClosed receipt);
    Rejected(owned Buffer<byte, n, Empty> buffer, tracked PreparationClosed receipt);
}
public Result<ref<'workspace.bytes> byte, Error> Select(ref Workspace workspace)
    effects writes(workspace.bytes), writes(workspace.audit)
    restores result is Ok(let slot) ==> workspace.bytes.Model == old(workspace.bytes.Model).Set(0, final(slot))
{
    ref Span<byte> parent = ref workspace.bytes;
    ref byte child = ref parent[0usize];
    child = 1byte;
    workspace.audit = 1;
    return Ok(child);
}
public Initialized<n> Prepare<ghost Nat n>(owned Buffer<byte, n, Empty> buffer,
    tracked PreparationOpen obligation) {
    let initialized = Initialize(move buffer);
    let receipt = Finish(move obligation);
    return Ready(move initialized, move receipt);
}
public void Inspect(owned Packed<byte> packet) {
    match (packet) {
        case Packed(let length, let storage, let evidence):
            Observe(length, in storage);
            Dispose(move storage);
    }
}
""", ("record", "union", "modified_type", "lifetime", "contract", "is", "typed_local")),
    Fixture("library-cells-and-guard-release", """module Cells;
public Result Update(ref BorrowCell<byte> cell, byte value) {
    let outcome = cell.WithTryWrite((scoped ref byte selected) => {
        selected = value;
        return ();
    });
    match (outcome) {
        case Updated(()): return Ok();
        case BorrowConflict: return Err(Conflict);
        case CapacityExhausted: return Err(Capacity);
    }
}
private Result WithWrite(ref BorrowCell<byte> cell,
    in Fn(scoped ref byte selected) -> () callback) {
    match (cell.TryWrite()) {
        case Acquired(let writer, let debt):
            callback(ref writer.Value);
            cell.ReleaseWrite(move writer, move debt);
            return Ok();
        case BorrowConflict: return Err(Conflict);
    }
}
public void Replace(ref LocalCell<Buffer> cell, owned Buffer replacement) {
    let displaced = cell.Replace(move replacement);
    Dispose(move displaced);
}
""", ("function_type", "lambda", "unit_type", "unit", "unit_pattern", "match", "call")),
    Fixture("library-modalities-and-obligations", """module Modalities;
public domain Presence {
    carrier bool;
    zero false; one true; add (||); mul (&&);
    admits (==); interpret Use.Presence; laws PresenceLaws;
}
public record Box<T, grade q : NatExact>(T Value @ q);
public (Box<T, q>, Box<T, q>) Duplicate<T, grade q : NatExact>(owned Box<T, q> value)
    where Dup(value)
    ensures Split(old(value), result);
public void Close<T>(owned T value) where Dispose(value);
public async T SuspendValue<T>(owned T value)
    where Suspend(value)
    ensures Preserved(old(value), result)
{
    await Checkpoint();
    return move value;
}
on cancel { Close(move value); }
""", ("record", "parameter", "tuple_type", "contract", "function")),
    Fixture("resource-errors-remain-syntax", """module InvalidResources;
public async void Invalid(ref BorrowCell<Buffer> cell, tracked Permit permit) {
    let copied = (move permit, move permit);
    match (copied) { case _: return; }
    ghost Nat oldLength = cell.Snapshot().Length;
    let changed = cell.Replace(move replacement);
    Use(cell[oldLength]);
    cell.WithTryWrite((scoped ref Buffer loan) => {
        await Ready();
        return loan;
    });
    cell.ReleaseWrite(move writer, move debt);
    cell.ReleaseWrite(move writer, move debt);
}
""", ("tuple", "wildcard_pattern", "typed_local", "lambda", "unary")),
    Fixture("modules-and-abstraction", """module Library.Storage;
import Core.Buffers;
alias Word = u64;
namespace Internal {
    public interface Storage<T> {
        type Handle;
        predicate Owns(Handle handle);
        operation void Read();
        proof ReadLaw;
    }
    public trait Eq<T> { bool Equal(T other); }
    public impl Eq<u64> { public bool Equal(u64 other) { return true; } }
}
""", ("import", "alias", "namespace", "interface", "trait", "impl")),
    Fixture("dependent-data-and-lifetimes", """module Packets;
public record Packet<region 'source>(
    usize Length, in<'source> Span<byte> Data, ghost Nat Count)
    invariant Length == Count;
public union Delivery<ghost Nat n> {
    Accepted(owned Packet<n> packet, tracked Permit<n> receipt);
    Cancelled(owned Packet<n> packet);
}
public struct Log<T, ghost Nat capacity> {
    private usize length;
    private Slots<T, capacity> slots;
    public view Entries = slots[0..length];
    public view Tail = slots[length], length grows;
    public void Push(ref self.Tail, T item)
        requires self.Length < capacity
        ensures self.Model == old(self.Model).Append(item);
}
""", ("record", "union", "struct", "view", "generic_parameter", "modified_type")),
    Fixture("function-types-grades-and-contracts", """module Maps;
public Result<ref<'table> Value, Error> Find<ghost Nat n, captures C, grade q : NatExact>(
    ref Table<Key, Value, n> table,
    in Fn(byte) -> byte captures C effects(Choose) transform @ q)
    where Duplicable(C)
    requires n > 0
    effects reads(C), writes(table)
    ensures result is Ok(let slot) ==> slot == old(table.Model).Get(0)
    restores result is Ok(let slot) ==> table.Model == old(table.Model).Set(0, final(slot));
public void Use(owned Packet packet, tracked Permit permit, scoped ref byte selected);
""", ("function_type", "generic_parameter", "parameter", "modified_type")),
    Fixture("control-loans-and-proof", """module Fill;
public void Fill(ref Span<byte> target) {
    var seen = 0usize;
    ref byte first = ref target[0usize];
    for (let i in 0usize..target.Length)
        invariant i <= target.Length
    {
        target[i] = 0byte;
        seen += 1;
        proof { ?step; }
    }
    while (seen < target.Length) decreases target.Length - seen {
        seen += 1;
        if (seen == 3) { continue; } else { break; }
    }
    match (Parse(in target)) {
        case Ok(let packet): Forward(in packet.Data);
        case Err(let error): Report(error);
    }
    if (true) return;
    return;
}
""", ("for", "while", "match", "proof", "hole", "if", "return")),
    Fixture("typed-locals-and-scoped-callbacks", """module ScopedLoans;
public void Lend(ref Span<byte> target, byte value) {
    Span<byte> local = target;
    ghost Seq<byte> before = target.Model;
    Result<Span<byte>, Error> nested = parsed;
    WithElement(ref target, 0, (scoped ref byte selected) => { selected = value; });
    Apply(ref target, (ref Span<byte> selected) => { selected[0usize] = 0byte; });
}
""", ("lambda", "modified_type", "type", "call")),
    Fixture("annotation-and-comparison-boundaries", """module AnnotationBoundaries;
public void Mix(ref Core.Span<byte> target) {
    let less = a < b;
    Core.Span< /* annotation comment */
        byte> local = target;
    Result<Core.Span<byte>, Error> nested = parsed;
    Call(a < b, c > d);
    let pair = (a < b, c > d);
    Apply((ref Core.Span< /* callback comment */ byte> selected) => {
        selected[0usize] = 0byte;
    });
}
""", ("typed_local", "lambda", "tuple", "binary", "modified_type")),
    Fixture("literal-sensitive-lambda-annotations", r"""module LiteralAnnotations;
public void F() {
    let direct = (Nat x, V<(')')> y) => x;
    let escaped = (Nat x, V<('\\')> y) => x;
}
""", ("lambda", "lambda_parameter", "type", "character")),
    Fixture("expressions-and-closures", """module Expressions;
public void Compute() {
    let tuple = (0001usize, true, false);
    let mapped = Map::<byte>(input, (byte x) => x + 1);
    let dormant = (() => Ready());
    let selected = input[1..4];
    let result = Read()?.Value;
    let logical = !false && 1 + 2 * 3 <= 7 || false ==> true;
    let signed = -4 + 8 / 2 - 3 % 2;
    let bits = ~mask & other | third ^ fourth;
    let text = "// { await }";
    let character = 'x';
}
""", ("tuple", "lambda", "binary", "unary", "call", "index", "nat")),
    Fixture("lawful-grade-domain", """module Grades;
public domain NatExact {
    carrier Nat;
    zero 0; one 1; add (+); mul (*);
    admits (==);
    interpret Use.Exact;
    laws NatExactLaws;
}
""", ("domain",)),
    Fixture("generic-effect-families", """module EffectFamilies;
public effect State<T> {
    T Get();
    void Put(T value);
}
public Nat Run<effect E>(in Fn() -> Nat effects(E) body) {
    return body();
}
""", ("effect", "generic_parameter", "function_type")),
    Fixture("effects-handlers-and-disposal", """module Effects;
public effect Choose { bool Choose() resumes(0..2); }
public effect Reject { never Reject(Error error); }
public usize Pick(in Fn() -> usize body) {
    let chosen = handle (body()) {
        Choose() with k => Max(resume k(false), resume k(true)),
        return score => score,
    };
    let checked = handle shallow (Validate()) {
        Reject(error) with k => { dispose k; return Err(error); },
        return _ => Ok(),
    };
    let forwarded = handle shallow (body()) {
        Choose() with k => rehandle (resume k(true)) {
            Choose() with nested => resume nested(false),
            return inner => inner,
        },
        return outer => outer,
    };
    return chosen;
}
""", ("effect", "handle", "rehandle", "resume", "dispose")),
    Fixture("structured-tasks-and-cleanup", """module Tasks;
public async Delivery<n> Accept<ghost Nat n>(
    owned Packet<n> packet, in Counter counter, tracked Permit<n> allowance)
    effects reads(packet), calls(Forward, counter.Add)
{
    await Forward(in packet);
    let receipt = commit counter.Add(move allowance, packet.Length);
    return Accepted(move packet, receipt);
}
on cancel { return Cancelled(move packet); }
public async Result Serve(ref Frames frames, owned Packet packet) {
    scope (ref frames) {
        let dormant = Accept(move packet);
        match (spawn dormant) {
            case Spawned(let task): return Ok(await task);
            case Full(let unstarted, let verdict): return Err(move unstarted);
        }
    }
}
""", ("function", "scope", "match", "unary", "return")),
    Fixture("mathematical-definitions-and-proofs", """module Mathematics;
universe u;
public definition Nat Twice(Nat x) = x + x;
public definition Type<u> Identity<T>(T value) = T;
public inductive Natural { Zero(); Succ(Natural predecessor); }
public inductive Vec<T, ghost Nat n> {
    Nil() : Vec<T, 0>;
    Cons(ghost Nat m, T head, Vec<T,m> tail) : Vec<T,(m+1)>;
}
public coinductive Stream<T> { More(T head, Stream<T> tail); }
public lemma Reflexive(Nat n): forall (Nat x) => x == x
    proof { calc { n + 0 == n; n == n; } assert n == n; ?step; }
public theorem Witness(): exists (Nat n) => n == 0;
""", ("universe", "definition", "inductive", "coinductive", "lemma", "theorem", "quantifier", "calc")),
    Fixture("represented-numeric-patterns", """module Patterns;
public bool IsLow(byte value) {
    match (value) {
        case 0u8: return true;
        case 0b01: return false;
    }
}
""", ("match", "return")),
    Fixture("machine-and-hardware", """module Machine;
public machine Counter {
    state Nat value = 0;
    transition Step() when (value < 10) { next value = value + 1; }
}
public hardware RegisterCounter {
    register u64 count = 0;
    rule Tick() when (count < 10) { next count = count + 1; }
    schedule Main { Tick; }
    cycle 1;
}
""", ("machine", "hardware", "state", "register", "transition", "rule", "schedule", "cycle", "next")),
    Fixture("semantic-errors-are-syntax", """module InvalidMeaning;
public UnknownType F(ghost Nat n) {
    let copied = (move authority, move authority);
    await n;
    return true + 1;
}
public UnknownType F() { return missing; }
""", ("function", "binary", "tuple")),
)


NEGATIVE: tuple[tuple[str, bytes, str], ...] = (
    ("ungrouped-callable-kind", b"module M; alias A<F : Fn() -> Nat> = F;", "syntax"),
    ("ungrouped-associated-callable-kind", b"module M; trait F { type A : Fn() -> Nat; }", "syntax"),
    ("ungrouped-callable-type-expression", b"module M; definition Type<u> F() = type Fn() -> Nat;", "syntax"),
    ("typed-callable-statement-missing-body", b"module M; void F() { Fn() -> Nat =>; }", "syntax"),
    ("typed-callable-argument-missing-body", b"module M; void F() { Apply(Fn() -> Nat =>); }", "syntax"),
    ("typed-callable-return-missing-body", b"module M; void F() { let f = Fn() -> (Fn() -> Nat) =>; }", "syntax"),
    ("type-binder-missing-kind", b"module M; alias Box<T :> = T;", "syntax"),
    ("type-binder-missing-name", b"module M; alias Box<: Type<u>> = T;", "syntax"),
    ("associated-missing-kind", b"module M; trait F { type Value :; }", "syntax"),
    ("associated-missing-law", b"module M; trait F { type Value : Type<u> where; }", "syntax"),
    ("associated-kind-after-law", b"module M; trait F { type Value where Stable(T) : Type<u>; }", "syntax"),
    ("type-expression-missing-type", b"module M; definition Type<u> F() = type;", "syntax"),
    ("type-expression-missing-component", b"module M; definition Type<u> F() = type (T,);", "syntax"),
    ("type-expression-incomplete-callable", b"module M; definition Type<u> F() = type Fn(T) ->;", "syntax"),
    ("typed-lambda-missing-result", b"module M; void F() { let f = Fn(T x) -> => x; }", "syntax"),
    ("typed-lambda-missing-arrow", b"module M; void F() { let f = Fn(T x) -> T x; }", "syntax"),
    ("typed-lambda-missing-body", b"module M; void F() { let f = FnOnce(T x) -> T =>; }", "syntax"),
    ("typed-lambda-missing-local-region", b"module M; void F() { let f = Fn<region>(T x) -> T => x; }", "syntax"),
    ("typed-lambda-incomplete-law", b"module M; void F() { let f = Fn(T x) -> T with { restores; } => x; }", "syntax"),
    ("typed-lambda-undelimited-law", b"module M; void F() { let f = Fn(T x) -> T requires Valid(x) => x; }", "syntax"),
    ("sum-missing-law", b"module M; union Result<T> where { Ok(T value); }", "syntax"),
    ("constructor-missing-law", b"module M; union Result { Ok() : Result ensures; }", "syntax"),
    ("constructor-result-after-law", b"module M; union Result { Ok() ensures Ready() : Result; }", "syntax"),
    ("definition-missing-law", b"module M; definition Nat F() requires = 0;", "syntax"),
    ("predicate-missing-law", b"module M; predicate P(Nat n) where = true;", "syntax"),
    ("literal-generic-missing-neighbor", b"module M; alias A = Indexed<true,>;", "syntax"),
    ("typed-callable-generic-depth", b"module M; void F() { let f = Fn<T : "
     + b"Box<" * 257 + b"T" + b">" * 257 + b">() -> T => value; }", "limit"),
    ("effect-missing-precondition", b"module M; effect E { Nat Get() requires; }", "syntax"),
    ("effect-missing-restoration", b"module M; effect E { Nat Get() resumes(1) restores; }", "syntax"),
    ("effect-missing-effects", b"module M; effect E { Nat Get() effects; }", "syntax"),
    ("effect-missing-contract-terminator", b"module M; effect E { Nat Get() ensures Ready(result) }", "syntax"),
    ("effect-resumes-after-contract", b"module M; effect E { Nat Get() requires Ready() resumes(1); }", "syntax"),
    ("container-missing-law", b"module M; trait Repeatable<T> where {}", "syntax"),
    ("container-missing-invariant", b"module M; struct Cell<T> invariant {}", "syntax"),
    ("container-contract-semicolon", b"module M; interface I where Law(); {}", "syntax"),
    ("handler-missing-capability", b"module M; Nat F() { return handle (Read()) as {}; }", "syntax"),
    ("handler-capability-before-expression", b"module M; Nat F() { return handle as chosen (Read()) {}; }", "syntax"),
    ("handler-capability-type-annotation", b"module M; Nat F() { return handle (Read()) as chosen : E {}; }", "syntax"),
    ("shallow-missing-capability", b"module M; Nat F() { return handle shallow (Read()) as {}; }", "syntax"),
    ("rehandle-missing-capability", b"module M; Nat F() { return rehandle (resume k(0)) as {}; }", "syntax"),
    ("handler-double-capability", b"module M; Nat F() { return handle (Read()) as first as second {}; }", "syntax"),
    ("missing-match-motive-binder", b"module M; public Nat F() { return match (x) as : Nat { case _ => 0; }; }", "syntax"),
    ("missing-match-motive-colon", b"module M; public Nat F() { return match (x) as p Nat { case _ => 0; }; }", "syntax"),
    ("missing-match-motive-type", b"module M; public Nat F() { return match (x) as p : { case _ => 0; }; }", "syntax"),
    ("empty-expression-match", b"module M; public Nat F() { return match (x) {}; }", "syntax"),
    ("expression-match-colon-arm", b"module M; public Nat F() { return match (x) { case _ : 0; }; }", "syntax"),
    ("expression-match-mixed-arms", b"module M; public Nat F() { return match (x) { case true => 0; case false : 1; }; }", "syntax"),
    ("expression-match-missing-value", b"module M; public Nat F() { return match (x) { case _ => ; }; }", "syntax"),
    ("expression-match-missing-semicolon", b"module M; public Nat F() { return match (x) { case _ => 0 }; }", "syntax"),
    ("match-motive-depth", b"module M; public Nat F() { return match (x) as p : "
     + b"Box<" * 257 + b"Nat" + b">" * 257 + b" { case _ => 0; }; }", "limit"),
    ("field-missing-grade", b"module M; struct Box { Nat Value @; }", "syntax"),
    ("field-grade-after-initializer", b"module M; struct Box { Nat Value = 0 @ q; }", "syntax"),
    ("impl-incomplete-telescope", b"module M; impl<T,> Dup<T> {}", "syntax"),
    ("impl-incomplete-contract", b"module M; impl<T> Dup<T> where {}", "syntax"),
    ("impl-ungrouped-callable", b"module M; impl Fn() -> Nat effects(Read) where Reusable(Read) {}", "syntax"),
    ("callable-incomplete-telescope", b"module M; alias F = Fn<region>() -> Nat;", "syntax"),
    ("callable-incomplete-law-block", b"module M; alias F = Fn() -> Nat with { requires Ready() };", "syntax"),
    ("callable-law-without-delimiter", b"module M; alias F = Fn() -> Nat with requires Ready();", "syntax"),
    ("incomplete-callable-binder", b"module M; alias F = Fn(Nat n, ) -> Nat;", "syntax"),
    ("incomplete-callable-grade", b"module M; alias F = Fn(Nat n @) -> Nat;", "syntax"),
    ("incomplete-lambda-grade", b"module M; public void F() { let f = (Nat n @) => n; }", "syntax"),
    ("incomplete-generic-alias", b"module M; alias F<T,> = T;", "syntax"),
    ("singleton-product-type", b"module M; alias P = (Nat,);", "syntax"),
    ("singleton-product-value", b"module M; public void F() { let p = (1,); }", "syntax"),
    ("singleton-product-pattern", b"module M; public void F() { let (let x,) = p; }", "syntax"),
    ("incomplete-product-binding", b"module M; public void F() { let (let x, let) = p; }", "syntax"),
    ("missing-product-value", b"module M; public void F() { let (let x, let y) = ; }", "syntax"),
    ("product-type-depth", b"module M; alias P = " + b"(Nat," * 257
     + b"Nat" + b")" * 257 + b";", "limit"),
    ("product-pattern-depth", b"module M; public void F() { match (p) { case "
     + b"(let x," * 257 + b"()" + b")" * 257 + b": return; } }", "limit"),
    ("graded-lambda-lookahead-depth", b"module M; public void F() { let f = (Nat n @ "
     + b"(" * 257 + b"q" + b")" * 257 + b") => n; }", "limit"),
    ("grade-callback-block-lookahead-depth", b"module M; public void F() { let f = (Nat x @ Grade.Of((Nat n) => "
     + b"{" * 257 + b"return n;" + b"}" * 257 + b")) => x; }", "limit"),
    ("grouped-type-lookahead-depth", b"module M; public void F() { "
     + b"(" * 257 + b"Nat" + b")" * 257 + b" local = value; }", "limit"),
    ("missing-generic-argument", b"module M; public Result<Packet,> Parse();", "syntax"),
    ("incomplete-record", b"module M; public record Packet(Nat Count", "syntax"),
    ("incomplete-handler", b"module M; public Nat F() { return handle (G()) { return x =>", "syntax"),
    ("missing-effect-result", b"module M; public effect E { Choose() resumes(1); }", "syntax"),
    ("missing-match-colon", b"module M; public void F() { match (x) { case Ok(let x) return; } }", "syntax"),
    ("incomplete-cancel", b"module M; public async Nat F() { return 0; } on cancel", "syntax"),
    ("unterminated-string", b'module M; public void F() { let text = "unterminated', "syntax"),
    ("unterminated-comment", b"module M; /* unterminated {", "syntax"),
    ("chained-comparison", b"module M; public bool F() { return a < b < c; }", "syntax"),
    ("generic-looking-comparison-group", b"module M; public bool F() { return (a < b > c); }", "syntax"),
    ("generic-looking-comparison-argument", b"module M; public void F() { Call(a < b > c, x); }", "syntax"),
    ("trailing-input", b"module M; public void F(); garbage", "syntax"),
    ("invalid-utf8", b"// invalid \xff\nmodule M; public void F();", "encoding"),
    ("literal-limit", b"module M; public Nat F() { return " + b"9" * 257 + b"; }", "limit"),
    ("hex-literal-limit", b"module M; public Nat F() { return 0x" + b"f" * 257 + b"; }", "limit"),
    ("binary-literal-limit", b"module M; public Nat F() { return 0b" + b"1" * 257 + b"; }", "limit"),
    ("delimiter-limit", b"module M; public Nat F() { return " + b"(" * 2000 + b"0" + b")" * 2000 + b"; }", "limit"),
    ("generic-annotation-lookahead-limit", b"module M; public void F() { " + b"Box<" * 257
     + b"Nat" + b">" * 257 + b" local = value; }", "limit"),
    ("syntax-depth-limit", b"module M; public Nat F() { return " + b" + ".join([b"1"] * 2000) + b"; }", "limit"),
    ("source-limit", b" " * (MAX_SOURCE_BYTES + 1), "limit"),
)


def nodes(value: Json) -> Iterator[dict[str, Json]]:
    """Visit AST roles without inferring their source syntax."""
    if isinstance(value, dict):
        if isinstance(value.get("kind"), str):
            yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def _object(value: Json, description: str) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise TypeError(f"surface fixture lacks {description}")
    return value


def _named(value: Json, kind: str, name: str) -> dict[str, Json]:
    matches: list[dict[str, Json]] = []
    for node in nodes(value):
        candidate = node.get("name")
        if node.get("kind") == kind and isinstance(candidate, dict) and candidate.get("text") == name:
            matches.append(node)
    if len(matches) != 1:
        raise ValueError(f"surface oracle expected one {kind} named {name}")
    return matches[0]


def _texts(value: Json) -> list[str]:
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return [text]
        return [text for child in value.values() for text in _texts(child)]
    if isinstance(value, list):
        return [text for child in value for text in _texts(child)]
    return []


def _type_roles(result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Find")
    returned = _object(function.get("result"), "dependent return type")
    if returned.get("kind") != "type" or _texts(returned.get("name")) != ["Result"]:
        raise ValueError("surface dependent result head differs")
    arguments = returned.get("arguments")
    if not isinstance(arguments, list) or len(arguments) != 2:
        raise ValueError("surface dependent result arguments differ")
    loan = _object(arguments[0], "returned exclusive loan")
    if loan.get("kind") != "modified_type" or loan.get("modifier") != "ref":
        raise ValueError("surface returned-loan mode differs")
    if _texts(loan.get("lifetime")) != ["'table"] or _texts(loan.get("type")) != ["Value"]:
        raise ValueError("surface returned-loan lifetime/value roles differ")
    parameters = function.get("parameters")
    if not isinstance(parameters, list) or len(parameters) != 2:
        raise ValueError("surface function parameter roles differ")
    transform = _object(parameters[1], "graded closure parameter")
    if _texts(transform.get("name")) != ["transform"] or _texts(transform.get("grade")) != ["q"]:
        raise ValueError("surface use grade is not attached to its parameter")
    shared = _object(transform.get("type"), "closure loan")
    if shared.get("kind") != "modified_type" or shared.get("modifier") != "in":
        raise ValueError("surface closure shared-loan role differs")
    closure = _object(shared.get("type"), "closure function type")
    if closure.get("kind") != "function_type" or closure.get("mode") != "Fn":
        raise ValueError("surface closure call mode differs")
    if _texts(closure.get("captures")) != ["C"] or _texts(closure.get("effects")) != ["Choose"]:
        raise ValueError("surface capture/effect suffix is not attached to its function type")
    contracts = function.get("contracts")
    if not isinstance(contracts, list):
        raise TypeError("surface dependent contracts lost their clause roles")
    for role in ("ensures", "restores"):
        clauses = [_object(clause, "contract") for clause in contracts
                   if isinstance(clause, dict) and clause.get("role") == role]
        if len(clauses) != 1:
            raise ValueError(f"surface expected one {role} clause")
        implication = _object(clauses[0].get("value"), "contract implication")
        if implication.get("kind") != "binary" or _texts(implication.get("operator")) != ["==>"]:
            raise ValueError("surface implication no longer heads its contract")
        tested = _object(implication.get("left"), "implication pattern test")
        if tested.get("kind") != "is" or _texts(tested) != ["result", "Ok", "slot"]:
            raise ValueError("surface pattern test no longer binds before implication")
        consequence = _object(implication.get("right"), "implication consequence")
        if consequence.get("kind") != "binary" or _texts(consequence.get("operator")) != ["=="]:
            raise ValueError("surface contract equality no longer binds inside implication")


def _cancellation_roles(result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Accept")
    if function.get("modifiers") != ["public", "async"]:
        raise ValueError("surface async modifiers differ")
    body = _object(function.get("body"), "async normal body")
    cancel = _object(function.get("cancel"), "async cancellation body")
    if body.get("kind") != "block" or cancel.get("kind") != "block":
        raise ValueError("surface cancellation body lost its block role")
    if "Accepted" not in _texts(body) or "Cancelled" in _texts(body):
        raise ValueError("surface normal/cancellation paths were conflated")
    if "Cancelled" not in _texts(cancel) or "Accepted" in _texts(cancel):
        raise ValueError("surface cancellation result lost its own body")


def _receiver_roles(result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Push")
    parameters = function.get("parameters")
    if not isinstance(parameters, list) or len(parameters) != 2:
        raise ValueError("surface named-view receiver parameter count differs")
    receiver = _object(parameters[0], "named-view receiver")
    if receiver.get("name") is not None or receiver.get("grade") is not None:
        raise ValueError("surface unnamed receiver fabricated a binding or grade")
    loan = _object(receiver.get("type"), "receiver exclusive loan")
    if loan.get("kind") != "modified_type" or loan.get("modifier") != "ref":
        raise ValueError("surface named-view receiver lost its exclusive mode")
    if _texts(loan.get("type")) != ["self.Tail"]:
        raise ValueError("surface named-view receiver place differs")


def _constructor(container: dict[str, Json], name: str) -> dict[str, Json]:
    matches: list[dict[str, Json]] = []
    for node in nodes(container):
        spelling = node.get("name")
        if isinstance(spelling, dict) and spelling.get("text") == name:
            matches.append(node)
    if len(matches) != 1:
        raise ValueError(f"surface expected one constructor named {name}")
    return matches[0]


def _effect_generic_roles(result: dict[str, Json]) -> None:
    family = _named(result.get("ast"), "effect", "State")
    parameters = family.get("generics")
    if not isinstance(parameters, list) or len(parameters) != 1:
        raise ValueError("surface effect family lost its generic type parameter")
    parameter = _object(parameters[0], "effect family generic")
    if parameter.get("mode") != "type" or _texts(parameter.get("name")) != ["T"]:
        raise ValueError("surface effect family generic has the wrong role")
    function = _named(result.get("ast"), "function", "Run")
    binders = function.get("generics")
    if not isinstance(binders, list) or len(binders) != 1:
        raise ValueError("surface effect-polymorphic function lost its binder")
    binder = _object(binders[0], "effect parameter")
    if binder.get("mode") != "effect" or _texts(binder.get("name")) != ["E"]:
        raise ValueError("surface effect parameter was conflated with an ordinary type")
    closures = [node for node in nodes(function) if node.get("kind") == "function_type"]
    if len(closures) != 1 or _texts(closures[0].get("effects")) != ["E"]:
        raise ValueError("surface polymorphic effect lost its function-type role")


def _type_head(value: Json, name: str, arity: int) -> list[Json]:
    typed = _object(value, "type annotation")
    arguments = typed.get("arguments")
    if (typed.get("kind") != "type" or _texts(typed.get("name")) != [name]
            or not isinstance(arguments, list) or len(arguments) != arity):
        raise ValueError(f"surface expected {name} type annotation with {arity} argument(s)")
    return arguments


def _typed_local_roles(result: dict[str, Json]) -> None:
    local = _named(result.get("ast"), "typed_local", "local")
    _type_head(_type_head(local.get("type"), "Span", 1)[0], "byte", 0)
    before = _named(result.get("ast"), "typed_local", "before")
    erased = _object(before.get("type"), "ghost local annotation")
    if erased.get("kind") != "modified_type" or erased.get("modifier") != "ghost":
        raise ValueError("surface ghost typed local lost its erased modifier")
    _type_head(_type_head(erased.get("type"), "Seq", 1)[0], "byte", 0)
    nested = _named(result.get("ast"), "typed_local", "nested")
    arguments = _type_head(nested.get("type"), "Result", 2)
    _type_head(_type_head(arguments[0], "Span", 1)[0], "byte", 0)
    _type_head(arguments[1], "Error", 0)
    parameters = [node for node in nodes(result.get("ast")) if node.get("kind") == "lambda_parameter"]
    if len(parameters) != 2:
        raise ValueError("surface scoped/generic callback parameter count differs")
    annotations = [_object(parameter.get("type"), "callback parameter annotation") for parameter in parameters]
    scoped, generic = annotations
    if scoped.get("kind") != "modified_type" or scoped.get("modifier") != "scoped":
        raise ValueError("surface callback lost its scoped modifier")
    exclusive = _object(scoped.get("type"), "scoped exclusive callback annotation")
    if exclusive.get("kind") != "modified_type" or exclusive.get("modifier") != "ref":
        raise ValueError("surface callback conflated scoped and exclusive modifiers")
    _type_head(exclusive.get("type"), "byte", 0)
    if generic.get("kind") != "modified_type" or generic.get("modifier") != "ref":
        raise ValueError("surface generic callback lost its exclusive modifier")
    _type_head(_type_head(generic.get("type"), "Span", 1)[0], "byte", 0)


def _sequence(value: Json, description: str) -> list[Json]:
    if not isinstance(value, list):
        raise TypeError(f"surface fixture lacks {description}")
    return value


def _exact_span(source: bytes, value: dict[str, Json], spelling: bytes) -> None:
    start = source.index(spelling)
    if value.get("span") != [start, start + len(spelling)]:
        raise ValueError(f"surface original-byte span differs for {spelling!r}")


def _contract_roles(owner: dict[str, Json], roles: list[str]) -> list[dict[str, Json]]:
    clauses = [_object(value, "declaration contract")
               for value in _sequence(owner.get("contracts"), "declaration contracts")]
    if [clause.get("role") for clause in clauses] != roles:
        raise ValueError("surface contract roles differ or belong to the wrong declaration")
    return clauses


def _kinded_family_roles(source: bytes, result: dict[str, Json]) -> None:
    scoped = _named(result.get("ast"), "alias", "Scoped")
    generic = _object(_sequence(scoped.get("generics"), "kinded telescope")[0], "kinded binder")
    if generic.get("mode") != "type" or _texts(generic.get("name")) != ["T"]:
        raise ValueError("surface explicit kind changed the generic binder's role")
    _type_head(generic.get("type"), "Type", 1)
    _exact_span(source, generic, b"T : Type<u>")
    plain = _named(result.get("ast"), "alias", "Plain")
    bare = _object(_sequence(plain.get("generics"), "bare telescope")[0], "bare binder")
    if bare.get("mode") != "type" or bare.get("type") is not None:
        raise ValueError("surface bare generic acquired an authored kind")
    family = _named(result.get("ast"), "trait", "Family")
    value = _named(family, "associated_type", "Value")
    _type_head(value.get("kind_annotation"), "Type", 1)
    _contract_roles(value, ["where"])
    _exact_span(source, value, b"type Value<U : Type<u>> : Type<u> where Formed(U);")
    if value.get("definition") is not None:
        raise ValueError("surface abstract associated family acquired a definition")
    selected = _named(family, "associated_type", "Selected")
    _type_head(selected.get("kind_annotation"), "Type", 1)
    _type_head(selected.get("definition"), "T", 0)
    _contract_roles(selected, ["where"])
    legacy = _named(family, "associated_type", "Legacy")
    if legacy.get("kind_annotation") is not None or legacy.get("contracts") != []:
        raise ValueError("surface unannotated associated type fabricated a kind or law")
    readable = _named(family, "predicate", "Readable")
    clauses = _contract_roles(readable, ["requires"])
    _exact_span(source, clauses[0], b"requires Ready(value)")
    if _texts(readable.get("definition")) != ["Stable", "value"]:
        raise ValueError("surface predicate contract displaced its defining expression")
    closed = _named(family, "predicate", "Closed")
    _contract_roles(closed, ["where"])
    if closed.get("definition") is not None:
        raise ValueError("surface predicate signature acquired a defining expression")


def _type_expression_roles(source: bytes, result: dict[str, Json]) -> None:
    family = _named(result.get("ast"), "definition", "LoanType")
    _contract_roles(family, ["where"])
    elimination = _object(family.get("value"), "type-valued elimination")
    motive = _object(elimination.get("motive"), "type-family motive")
    if elimination.get("kind") != "match_expression" or _texts(motive.get("name")) != ["mode"]:
        raise ValueError("surface type family lost its dependent elimination")
    _type_head(motive.get("type"), "Type", 1)
    arms = _sequence(elimination.get("cases"), "type-family branches")
    for arm, truth, mode in zip(arms, (True, False), ("ref", "in"), strict=True):
        branch = _object(arm, "type-family branch")
        if _object(branch.get("pattern"), "type-family pattern").get("value") is not truth:
            raise ValueError("surface type-family branch discriminant differs")
        expression = _object(branch.get("value"), "type expression")
        annotation = _object(expression.get("type"), "injected loan type")
        if expression.get("kind") != "type_expression" or annotation.get("modifier") != mode:
            raise ValueError("surface type expression erased its loan mode")
        _type_head(annotation.get("type"), "T", 0)
        _exact_span(source, expression, f"type {mode} T".encode())
    for name, kind, spelling in (("Product", "tuple_type", b"type (owned T, tracked Receipt)"),
                                 ("UnitType", "unit_type", b"type ()"),
                                 ("Callback", "group_type", None)):
        definition = _named(result.get("ast"), "definition", name)
        expression = _object(definition.get("value"), "type-valued definition")
        annotation = _object(expression.get("type"), "injected structural type")
        if expression.get("kind") != "type_expression" or annotation.get("kind") != kind:
            raise ValueError("surface injected structural type has the wrong role")
        if spelling is not None:
            _exact_span(source, expression, spelling)
        if name == "Callback":
            callable_type = _object(annotation.get("type"), "grouped injected callable")
            _contract_roles(callable_type, ["restores"])
            if callable_type.get("kind") != "function_type" or callable_type.get("mode") != "Fn":
                raise ValueError("surface injected callable type lost its call mode")


def _callable_kind_effect_roles(source: bytes, result: dict[str, Json]) -> None:
    higher = _named(result.get("ast"), "alias", "Higher")
    generic = _object(_sequence(higher.get("generics"), "higher-kinded binder")[0], "callable kind binder")
    kind = _object(generic.get("type"), "grouped callable kind")
    signature = _object(kind.get("type"), "callable kind signature")
    if kind.get("kind") != "group_type" or signature.get("kind") != "function_type":
        raise ValueError("surface callable kind lost its grouping or signature role")
    _exact_span(source, kind, b"(Fn(Type<u> value) -> Type<u>)")
    associated = _named(result.get("ast"), "associated_type", "Build")
    annotation = _object(associated.get("kind_annotation"), "associated callable kind")
    if annotation.get("kind") != "group_type":
        raise ValueError("surface associated callable kind lost its explicit boundary")
    _exact_span(source, annotation, b"(Fn(Type<u>) -> Type<u>)")
    _contract_roles(associated, ["where"])
    factories = _named(result.get("ast"), "union", "Factories")
    bare = _constructor(factories, "Bare")
    callable_result = _object(bare.get("result"), "bare callable constructor result")
    if callable_result.get("kind") != "function_type" or _texts(callable_result.get("effects")) != ["Read"]:
        raise ValueError("surface constructor moved bare callable effects outside its result")
    _contract_roles(bare, ["requires"])
    grouped = _constructor(factories, "Grouped")
    boundary = _object(grouped.get("result"), "grouped callable constructor result")
    callable_result = _object(boundary.get("type"), "grouped result signature")
    if boundary.get("kind") != "group_type" or _texts(callable_result.get("effects")) != ["Read"]:
        raise ValueError("surface grouped callable result lost its own effect bound")
    contracts = _sequence(grouped.get("contracts"), "constructor effect contract")
    if (len(contracts) != 1 or _object(contracts[0], "constructor effects").get("kind") != "effects"
            or _texts(contracts[0]) != ["writes", "Storage"]):
        raise ValueError("surface grouped callable swallowed its constructor's effects")
    operation = _named(result.get("ast"), "function", "RequiresType")
    clauses = _sequence(operation.get("contracts"), "type-valued precondition and effects")
    if len(clauses) != 2:
        raise ValueError("surface type-valued contract swallowed the enclosing effect contract")
    precondition, effects = [_object(value, "type-valued operation contract") for value in clauses]
    expression = _object(precondition.get("value"), "type-valued precondition")
    if (precondition.get("role") != "requires" or expression.get("kind") != "type_expression"
            or effects.get("kind") != "effects" or _texts(effects) != ["writes", "Storage"]):
        raise ValueError("surface type expression confused callable and declaration effects")
    _exact_span(source, precondition, b"requires type (Fn() -> bool effects(Read))")
    grouped_type = _object(expression.get("type"), "precondition's grouped callable")
    if _texts(_object(grouped_type.get("type"), "precondition signature").get("effects")) != ["Read"]:
        raise ValueError("surface precondition lost the injected callable's own effects")


def _typed_callable_roles(source: bytes, result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Use")
    for name, mode, body_kind in (("update", "FnMut", "block"), ("consume", "FnOnce", "unary"),
                                  ("classify", "Fn", "match_expression")):
        binding = _named(function, "let", name)
        closure = _object(binding.get("value"), "explicit callable value")
        signature = _object(closure.get("signature"), "callable value signature")
        body = _object(closure.get("body"), "callable value body")
        if (closure.get("kind") != "typed_lambda" or signature.get("kind") != "function_type"
                or signature.get("mode") != mode or body.get("kind") != body_kind):
            raise ValueError("surface explicit callable confused signature, call mode or body")
        if name == "update":
            generics = _sequence(signature.get("generics"), "callable value local binders")
            if len(generics) != 1 or _object(generics[0], "local region").get("mode") != "region":
                raise ValueError("surface callable value lost its locally bound region")
            _exact_span(source, _object(generics[0], "local region"), b"region 'r")
            parameter = _object(_sequence(signature.get("parameters"), "callable parameters")[0], "scoped slot")
            scoped = _object(parameter.get("type"), "scoped slot annotation")
            loan = _object(scoped.get("type"), "exclusive slot loan")
            if (scoped.get("modifier") != "scoped" or loan.get("modifier") != "ref"
                    or _texts(loan.get("lifetime")) != ["'r"] or _texts(parameter.get("grade")) != ["q"]):
                raise ValueError("surface callable value displaced its scoped loan or grade")
            _exact_span(source, parameter, b"scoped ref<'r> T slot @ q")
            if _texts(signature.get("captures")) != ["C"] or _texts(signature.get("effects")) != ["Write"]:
                raise ValueError("surface callable value lost captures or effect bounds")
            clauses = _contract_roles(signature, ["requires", "restores"])
            _exact_span(source, clauses[1], b"restores Closed(final(slot))")
            if "Mutate" not in _texts(body) or "Closed" in _texts(body):
                raise ValueError("surface callable signature laws leaked into its executable body")
        elif name == "consume":
            _contract_roles(signature, ["ensures"])
            _exact_span(source, body, b"move item")
        else:
            _contract_roles(signature, [])
            _type_head(signature.get("result"), "Type", 1)
            expressions = [node for node in nodes(body) if node.get("kind") == "type_expression"]
            if len(expressions) != 2:
                raise ValueError("surface shared callable lost its type-valued branches")


def _typed_callable_composition_roles(source: bytes, result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Compose")
    statements = _sequence(_object(function.get("body"), "composition body").get("statements"),
                           "composition statements")
    first = _object(statements[0], "standalone callable statement")
    standalone = _object(first.get("value"), "standalone callable value")
    if first.get("kind") != "expression_statement" or standalone.get("kind") != "typed_lambda":
        raise ValueError("surface standalone callable became an annotation or declaration")
    _exact_span(source, standalone, b"Fn(Nat n) -> Nat => n")
    call = _object(_object(statements[1], "callback application statement").get("value"), "callback application")
    arguments = [_object(value, "nested callable argument")
                 for value in _sequence(call.get("arguments"), "nested callable arguments")]
    if call.get("kind") != "call" or [value.get("kind") for value in arguments] != ["typed_lambda", "typed_lambda"]:
        raise ValueError("surface nested callable arguments lost their expression roles")
    second_signature = _object(arguments[1].get("signature"), "zero-argument callback signature")
    if second_signature.get("mode") != "FnOnce" or second_signature.get("parameters") != []:
        raise ValueError("surface zero-argument callback lost its call mode or empty telescope")
    annotated = _named(function, "typed_local", "annotated")
    annotation = _object(annotated.get("type"), "local callable annotation")
    initializer = _object(annotated.get("value"), "local callable initializer")
    if annotation.get("kind") != "function_type" or initializer.get("kind") != "typed_lambda":
        raise ValueError("surface callable local annotation and initializer became one signature")
    _exact_span(source, initializer, b"Fn(Nat item) -> Nat => item")
    returned = _object(_named(function, "let", "returning").get("value"), "callable factory")
    returned_signature = _object(returned.get("signature"), "factory signature")
    result_type = _object(returned_signature.get("result"), "factory result type")
    if (returned.get("kind") != "typed_lambda" or returned_signature.get("parameters") != []
            or result_type.get("kind") != "group_type"
            or _object(result_type.get("type"), "returned callable type").get("kind") != "function_type"
            or _object(returned.get("body"), "returned callable value").get("kind") != "typed_lambda"):
        raise ValueError("surface callable factory confused nested signature and value roles")
    for name, kind in (("graded", "typed_lambda"), ("inferred", "lambda")):
        closure = _object(_named(function, "let", name).get("value"), "graded callback")
        signature = _object(closure.get("signature"), "graded explicit signature") if kind == "typed_lambda" else closure
        parameter = _object(_sequence(signature.get("parameters"), "graded parameters")[0], "graded parameter")
        grade = _object(parameter.get("grade"), "callback-computed grade")
        callback = _object(_sequence(grade.get("arguments"), "grade-operation arguments")[0], "grade callback")
        if closure.get("kind") != kind or grade.get("kind") != "call" or callback.get("kind") != "typed_lambda":
            raise ValueError("surface grade lookahead confused its nested typed callback")
        if name == "inferred":
            _exact_span(source, _object(callback.get("body"), "grade callback block"), b"{ return 1; }")


def _typed_resource_error_roles(source: bytes, result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Invalid")
    duplicate = _object(_named(function, "let", "duplicate").get("value"), "invalid repeated-use callable")
    signature = _object(duplicate.get("signature"), "invalid repeated-use signature")
    parameter = _object(_sequence(signature.get("parameters"), "invalid callable parameter")[0], "zero-use owner")
    grade = _object(parameter.get("grade"), "authored zero-use grade")
    zero = _object(_sequence(grade.get("arguments"), "grade arguments")[0], "zero allowance")
    body = _object(duplicate.get("body"), "duplicated owner value")
    values = _sequence(body.get("values"), "duplicated owner components")
    if zero.get("value") != "0" or body.get("kind") != "tuple" or [_texts(value) for value in values] != [
            ["move", "p"], ["move", "p"]]:
        raise ValueError("surface syntax sanitized invalid grade or repeated ownership use")
    suspended = _object(_named(function, "let", "suspended").get("value"), "invalid suspended loan")
    checkpoints = [node for node in nodes(suspended.get("body"))
                   if node.get("kind") == "unary" and _texts(node.get("operator")) == ["await"]]
    if len(checkpoints) != 1:
        raise ValueError("surface syntax lost the explicit await under a scoped loan")
    _exact_span(source, checkpoints[0], b"await Ready()")


def _indexed_family_contract_roles(source: bytes, result: dict[str, Json]) -> None:
    for kind, name, law in (("union", "Outcome", "Separated"), ("inductive", "Vec", "Admissible"),
                             ("coinductive", "Stream", "Guarded")):
        family = _named(result.get("ast"), kind, name)
        clauses = _contract_roles(family, ["where"])
        if _texts(clauses[0].get("value")) != [law, "T"]:
            raise ValueError("surface indexed-family law escaped its declaration")
    outcome = _named(result.get("ast"), "union", "Outcome")
    ready = _constructor(outcome, "Ready")
    _type_head(ready.get("result"), "Outcome", 1)
    clauses = _contract_roles(ready, ["ensures"])
    _exact_span(source, clauses[0], b"ensures Retained(value)")
    parameter = _object(_sequence(ready.get("parameters"), "ready owner")[0], "ready owner")
    if _texts(parameter.get("grade")) != ["NatExact"]:
        raise ValueError("surface constructor law displaced the owner's use grade")
    _contract_roles(_constructor(outcome, "Rejected"), ["restores"])
    _contract_roles(_constructor(outcome, "Empty"), [])
    cons = _constructor(_named(result.get("ast"), "inductive", "Vec"), "Cons")
    _contract_roles(cons, ["requires"])
    arguments = _type_head(cons.get("result"), "Vec", 2)
    if _object(arguments[1], "successor index").get("kind") != "group":
        raise ValueError("surface constructor contracts consumed the dependent result index")
    _contract_roles(_named(result.get("ast"), "definition", "Count"), ["requires", "ensures"])
    _contract_roles(_named(result.get("ast"), "union", "Legacy"), [])
    _contract_roles(_named(result.get("ast"), "definition", "Zero"), [])


def _stable_generic_literal_roles(source: bytes, result: dict[str, Json]) -> None:
    flags = _type_head(_named(result.get("ast"), "alias", "Flags").get("type"), "FlagsOf", 2)
    if [(_object(value, "Boolean index").get("kind"), _object(value, "Boolean index").get("value"))
            for value in flags] != [("bool", True), ("bool", False)]:
        raise ValueError("surface generic Boolean literals became names or normalized values")
    label = _type_head(_named(result.get("ast"), "alias", "Label").get("type"), "Named", 3)
    for value, kind, spelling in zip(label, ("string", "character", "hole"),
                                      (b'"wire"', b"'x'", b"?missing"), strict=True):
        literal = _object(value, "stable literal argument")
        if literal.get("kind") != kind:
            raise ValueError("surface generic literal changed its syntax role")
        if kind == "hole":
            if _texts(literal.get("name")) != [spelling.decode()]:
                raise ValueError("surface generic named hole lost its spelling")
        elif literal.get("value") != spelling.decode():
            raise ValueError("surface generic literal lost its quoted spelling")
        _exact_span(source, literal, spelling)
    mixed = _type_head(_named(result.get("ast"), "alias", "Mixed").get("type"), "Indexed", 4)
    numeric = _object(mixed[0], "represented generic index")
    if numeric.get("value") != "0002" or numeric.get("suffix") != "usize":
        raise ValueError("surface stable arguments changed represented numeric spelling")
    _exact_span(source, numeric, b"0002usize")
    if [_object(value, "mixed generic argument").get("kind") for value in mixed] != [
            "nat", "bool", "group", "type_argument"]:
        raise ValueError("surface stable arguments displaced expression and structural-type roles")
    application = next(node for node in nodes(result.get("ast")) if node.get("kind") == "generic_application")
    if [_object(value, "explicit stable argument").get("kind")
            for value in _sequence(application.get("arguments"), "explicit stable arguments")] != [
            "bool", "string", "character", "hole"]:
        raise ValueError("surface generic expression application lost its stable literals")


def _effect_resource_roles(source: bytes, result: dict[str, Json]) -> None:
    effect = _named(result.get("ast"), "effect", "Exchange")
    operation = _named(effect, "effect_operation", "Replace")
    result_type = _object(operation.get("result"), "effect owned reply")
    if result_type.get("modifier") != "owned":
        raise ValueError("surface effect reply lost its ownership modifier")
    arguments = _type_head(result_type.get("type"), "Buffer", 2)
    if _texts(arguments) != ["T", "n"]:
        raise ValueError("surface effect reply lost its stable dependent index")
    parameters = _sequence(operation.get("parameters"), "effect parameters")
    replacement = _object(parameters[0], "effect replacement")
    permit = _object(parameters[1], "effect permit")
    grade = _object(replacement.get("grade"), "effect parameter grade")
    if (len(parameters) != 2 or _texts(replacement.get("name")) != ["replacement"]
            or _texts(grade.get("callee")) != ["NatExact"]
            or _object(permit.get("type"), "effect tracked permit").get("modifier") != "tracked"):
        raise ValueError("surface effect parameter grade and authority roles differ")
    _exact_span(source, replacement, b"owned Buffer<T, n> replacement @ NatExact(1)")
    _exact_span(source, grade, b"NatExact(1)")
    bound = _object(operation.get("resumes"), "effect resumption bound")
    if (bound.get("kind") != "range" or _object(bound.get("start"), "bound start").get("value") != "0"
            or _object(bound.get("end"), "bound end").get("value") != "1"):
        raise ValueError("surface resumption allowance became a parameter-use grade")
    _exact_span(source, bound, b"0..1")
    contracts = _sequence(operation.get("contracts"), "effect resource contracts")
    if [_object(value, "effect contract").get("role", _object(value, "effect contract").get("kind"))
            for value in contracts] != ["requires", "ensures", "restores", "effects"]:
        raise ValueError("surface effect resource contracts lost their ordered roles")
    for clause, spelling in zip(contracts, (b"requires Available(replacement)", b"ensures Returned(result)",
                                            b"restores Closed(result)", b"effects writes(replacement)"), strict=True):
        _exact_span(source, _object(clause, "effect contract"), spelling)
    observer = _named(effect, "effect_operation", "Observe")
    if observer.get("resumes") is not None or _texts(observer.get("contracts")) != ["ObserverReady"]:
        raise ValueError("surface effect contracts require or swallow a resumption bound")
    plain = _named(effect, "effect_operation", "Plain")
    if plain.get("contracts") != [] or plain.get("resumes") is not None:
        raise ValueError("surface plain effect operation fabricated contracts or a bound")
    borrowed = _named(effect, "effect_operation", "Borrow")
    loan = _object(borrowed.get("result"), "effect returned loan")
    if loan.get("modifier") != "ref" or _texts(loan.get("lifetime")) != ["'input"]:
        raise ValueError("surface effect contract displaced its returned-loan lifetime")
    _exact_span(source, loan, b"ref<'input> T")


def _container_resource_roles(source: bytes, result: dict[str, Json]) -> None:
    expected = (("struct", "LocalCell", ["where", "invariant"]),
                ("interface", "Storage", ["where"]), ("trait", "Repeatable", ["where"]),
                ("machine", "Counter", ["invariant"]), ("hardware", "Clocked", ["where", "invariant"]))
    for kind, name, roles in expected:
        container = _named(result.get("ast"), kind, name)
        contracts = _sequence(container.get("contracts"), "container resource contracts")
        if [_object(value, "container contract").get("role") for value in contracts] != roles:
            raise ValueError(f"surface {kind} {name} lost its own resource contracts")
    cell = _named(result.get("ast"), "struct", "LocalCell")
    _exact_span(source, _object(_sequence(cell.get("contracts"), "cell contracts")[1], "cell invariant"),
                b"invariant Closed(self)")
    if _texts(_named(cell, "field", "Value").get("grade")) != ["q"]:
        raise ValueError("surface container contract displaced a field grade")
    closed = _named(cell, "function", "Close")
    if _texts(closed.get("contracts")) != ["Opened", "self", "Closed", "self"]:
        raise ValueError("surface container invariant swallowed its member's contracts")
    storage = _named(result.get("ast"), "interface", "Storage")
    read = _named(storage, "operation", "Read")
    if _texts(read.get("contracts")) != ["Readable", "self", "Stable", "result"]:
        raise ValueError("surface interface law swallowed its operation contracts")
    nested = _named(storage, "struct", "Nested")
    if _texts(nested.get("contracts")) != ["InnerLaw"]:
        raise ValueError("surface nested container law was attached to its parent")
    if _named(result.get("ast"), "struct", "Empty").get("contracts") != []:
        raise ValueError("surface unconstrained container fabricated resource contracts")


def _named_handler_roles(source: bytes, result: dict[str, Json]) -> None:
    def capability(handler: dict[str, Json], expected: str) -> None:
        binding = _object(handler.get("capability"), "handler capability binder")
        if _texts(binding) != [expected]:
            raise ValueError("surface handler capability was attached to another handler")
        start = source.index(b"as " + expected.encode()) + len(b"as ")
        if binding.get("span") != [start, start + len(expected)]:
            raise ValueError("surface handler capability lost its original-byte binder span")

    nested = _named(result.get("ast"), "function", "Nested")
    terminal = next(node for node in nodes(nested) if node.get("kind") == "return")
    outer = _object(terminal.get("value"), "outer handler")
    inner = _object(outer.get("value"), "inner handler")
    capability(outer, "outer")
    capability(inner, "inner")
    if outer.get("shallow") is not False or inner.get("shallow") is not False:
        raise ValueError("surface named deep handlers changed mode")
    call = _object(inner.get("value"), "explicit operation call")
    if call.get("kind") != "call" or _texts(call.get("callee")) != ["inner", "Read"]:
        raise ValueError("surface named capability call acquired a new operation primitive")
    clauses = _sequence(inner.get("clauses"), "inner handler clauses")
    operation = _object(clauses[0], "inner operation clause")
    resumed = _object(operation.get("body"), "forwarding resumption")
    if (_texts(operation.get("continuation")) != ["nested"]
            or resumed.get("kind") != "resume" or _texts(resumed.get("value")) != ["outer", "Read"]):
        raise ValueError("surface explicit forwarding lost its outer capability or continuation")
    reinstall = _named(result.get("ast"), "function", "Reinstall")
    handlers = [node for node in nodes(reinstall) if node.get("kind") in {"handle", "rehandle"}]
    shallow = next(node for node in handlers if node.get("shallow") is True)
    rehandled = next(node for node in handlers if node.get("kind") == "rehandle")
    capability(shallow, "current")
    capability(rehandled, "replacement")
    if rehandled not in list(nodes(shallow.get("clauses"))):
        raise ValueError("surface rehandler was detached from the shallow operation clause")
    unnamed = [node for node in handlers if node.get("capability") is None]
    if len(unnamed) != 1 or "capability" not in unnamed[0]:
        raise ValueError("surface unnamed handler lacks its explicit null capability field")
    shadow = _named(result.get("ast"), "function", "Shadow")
    bindings = [_object(node.get("capability"), "shadowed handler capability")
                for node in nodes(shadow) if node.get("kind") == "handle"]
    starts = (source.index(b"as same") + 3, source.index(b"as same", source.index(b"as same") + 1) + 3)
    spans = [binding.get("span") for binding in bindings]
    if (len(bindings) != 2 or any(_texts(binding) != ["same"] for binding in bindings)
            or any([start, start + 4] not in spans for start in starts)):
        raise ValueError("surface same-spelled handler binders lost their distinct source identities")


def _dependent_match_roles(source: bytes, result: dict[str, Json]) -> None:
    unpack = _named(result.get("ast"), "function", "Unpack")
    expression = next(node for node in nodes(unpack) if node.get("kind") == "match_expression")
    motive = _object(expression.get("motive"), "dependent expression motive")
    if motive.get("kind") != "match_motive" or _texts(motive.get("name")) != ["packed"]:
        raise ValueError("surface dependent match lost its scrutinee binder")
    _exact_span(source, motive, b"as packed : Vec<byte, packed.Length>")
    binder = source.index(b"as packed") + len(b"as ")
    if _object(motive.get("name"), "motive binder").get("span") != [binder, binder + len(b"packed")]:
        raise ValueError("surface motive name span was conflated with a branch binder")
    arguments = _type_head(motive.get("type"), "Vec", 2)
    if _texts(arguments[1]) != ["packed.Length"]:
        raise ValueError("surface motive lost its dependent result index")
    _exact_span(source, _object(motive.get("type"), "motive result type"), b"Vec<byte, packed.Length>")
    arm = _object(_sequence(expression.get("cases"), "dependent expression arms")[0], "dependent arm")
    if arm.get("kind") != "expression_case" or _texts(arm.get("pattern")) != ["Packed", "count", "bytes"]:
        raise ValueError("surface expression match lost its distinct branch bindings")
    _exact_span(source, _object(arm.get("pattern"), "dependent arm pattern"), b"Packed(let count, let bytes)")
    if _texts(arm.get("value")) != ["bytes"] or "statements" in arm:
        raise ValueError("surface expression arm value became a statement body")
    value_start = source.index(b"=> bytes;") + len(b"=> ")
    if _object(arm.get("value"), "dependent arm value").get("span") != [value_start, value_start + 5]:
        raise ValueError("surface expression arm value span differs")
    inspect = _named(result.get("ast"), "function", "Inspect")
    statement = next(node for node in nodes(inspect) if node.get("kind") == "match")
    annotated = _object(statement.get("motive"), "statement motive")
    if _texts(annotated.get("name")) != ["choice"]:
        raise ValueError("surface statement match lost its motive")
    _type_head(annotated.get("type"), "Nat", 0)
    if any(_object(case, "statement arm").get("kind") != "case"
           or "statements" not in _object(case, "statement arm")
           for case in _sequence(statement.get("cases"), "statement arms")):
        raise ValueError("surface statement match became an expression arm")
    nested = _named(result.get("ast"), "function", "Nested")
    matches = [node for node in nodes(nested) if node.get("kind") == "match_expression"]
    if len(matches) != 2 or any(match.get("motive") is not None for match in matches):
        raise ValueError("surface inferred nested matches fabricated a motive")
    returned = next(node for node in nodes(nested) if node.get("kind") == "return")
    addition = _object(returned.get("value"), "match-containing addition")
    product = _object(addition.get("right"), "match-containing product")
    if (_texts(addition.get("operator")) != ["+"] or _texts(product.get("operator")) != ["*"]
            or _object(product.get("left"), "multiplicative match").get("kind") != "match_expression"):
        raise ValueError("surface match expression changed surrounding operator precedence")
    borrow = _named(result.get("ast"), "function", "Borrow")
    loan = _object(_type_head(borrow.get("result"), "Result", 2)[0], "returned branch loan")
    if loan.get("modifier") != "ref" or _texts(loan.get("lifetime")) != ["'workspace.bytes"]:
        raise ValueError("surface dependent branch lost its place-named result loan")
    call = next(node for node in nodes(borrow)
                if node.get("kind") == "call" and _texts(node.get("callee")) == ["Wrap"])
    argument = _object(_sequence(call.get("arguments"), "call match argument")[0], "match argument")
    if argument.get("kind") != "match_expression" or _texts(argument.get("motive")) != ["outcome", "LoanResult", "outcome"]:
        raise ValueError("surface match expression failed to compose with a call")


def _field_grade_roles(source: bytes, result: dict[str, Json]) -> None:
    box = _named(result.get("ast"), "struct", "Box")
    value = _named(box, "field", "Value")
    if _texts(value.get("grade")) != ["q"] or value.get("value") is not None:
        raise ValueError("surface field grade was dropped or became an initializer")
    start = source.index(b"Value @ q") + len(b"Value @ ")
    if _object(value.get("grade"), "field use grade").get("span") != [start, start + 1]:
        raise ValueError("surface field grade lost its own byte span")
    debt = _named(box, "field", "Debt")
    if (_object(debt.get("type"), "tracked field").get("modifier") != "tracked"
            or _texts(_object(debt.get("grade"), "tracked field grade").get("callee")) != ["NatExact"]):
        raise ValueError("surface tracked field's modifier and grade were conflated")
    count = _named(box, "field", "Count")
    _exact_span(source, count, b"public Nat Count @ (q + 1) = 0;")
    _exact_span(source, _object(count.get("grade"), "computed field grade"), b"(q + 1)")
    initialized = _object(count.get("value"), "graded field initializer")
    if initialized.get("kind") != "nat" or initialized.get("value") != "0":
        raise ValueError("surface graded field lost its separate initializer")
    if _named(box, "field", "Plain").get("grade") is not None:
        raise ValueError("surface ungraded field acquired an implicit grade")


def _generic_impl_roles(result: dict[str, Json]) -> None:
    implementations = [node for node in nodes(result.get("ast")) if node.get("kind") == "impl"]
    if len(implementations) != 2:
        raise ValueError("surface generic and callable implementation count differs")
    implementation, callable_impl = implementations
    generics = _sequence(implementation.get("generics"), "implementation telescope")
    if [_object(value, "implementation binder").get("mode") for value in generics] != ["type", "grade"]:
        raise ValueError("surface implementation lost its generic binder roles")
    contracts = _sequence(implementation.get("contracts"), "implementation contracts")
    if [_object(value, "implementation contract").get("role") for value in contracts] != ["where", "requires"]:
        raise ValueError("surface implementation contracts leaked into its members")
    _type_head(_type_head(implementation.get("type"), "Dup", 1)[0], "Box", 2)
    member = _named(implementation, "function", "Split")
    clauses = _sequence(member.get("contracts"), "implementation member contracts")
    if len(clauses) != 1 or _object(clauses[0], "member postcondition").get("role") != "ensures":
        raise ValueError("surface generic instance swallowed its member postcondition")
    grouped = _object(callable_impl.get("type"), "grouped callable implementation target")
    target = _object(grouped.get("type"), "callable implementation target")
    if (grouped.get("kind") != "group_type" or target.get("kind") != "function_type"
            or _texts(target.get("effects")) != ["Read"] or target.get("contracts") != []
            or _texts(callable_impl.get("contracts")) != ["Reusable", "Read"]):
        raise ValueError("surface callable target effects absorbed its implementation law")


def _scoped_callable_roles(source: bytes, result: dict[str, Json]) -> None:
    alias = _named(result.get("ast"), "alias", "Update")
    callable_type = _object(alias.get("type"), "locally quantified callable")
    generics = _sequence(callable_type.get("generics"), "callable generic telescope")
    if [_object(value, "callable generic").get("mode") for value in generics] != ["region", "grade"]:
        raise ValueError("surface callable failed to bind its own region and grade")
    _exact_span(source, _object(generics[0], "local region"), b"region 'loan")
    parameter = _object(_sequence(callable_type.get("parameters"), "scoped callable parameter")[0], "scoped parameter")
    scoped = _object(parameter.get("type"), "scoped annotation")
    loan = _object(scoped.get("type"), "locally named loan")
    if (scoped.get("modifier") != "scoped" or loan.get("modifier") != "ref"
            or _texts(loan.get("lifetime")) != ["'loan"] or _texts(parameter.get("grade")) != ["q"]):
        raise ValueError("surface callable lost scoped loan or binder-grade composition")
    _exact_span(source, parameter, b"scoped ref<'loan> T value @ q")
    if _texts(callable_type.get("captures")) != ["C"] or _texts(callable_type.get("effects")) != ["Write"]:
        raise ValueError("surface callable contracts displaced captures or effects")
    clauses = _sequence(callable_type.get("contracts"), "callable contracts")
    if [_object(value, "callable contract").get("role") for value in clauses] != ["requires", "restores"]:
        raise ValueError("surface locally quantified callable lost its contract block")
    _exact_span(source, _object(clauses[1], "callable restoration"), b"restores Valid(final(value))")
    operation = _named(result.get("ast"), "function", "Apply")
    outer = _sequence(operation.get("contracts"), "enclosing operation contracts")
    if [_object(value, "outer contract").get("role") for value in outer] != ["requires", "ensures"]:
        raise ValueError("surface callback contracts escaped their delimiter")
    callbacks = [node for node in nodes(operation) if node.get("kind") == "function_type"]
    if len(callbacks) != 1 or _texts(callbacks[0].get("contracts")) != ["CallbackReady", "selected", "CallbackClosed", "selected"]:
        raise ValueError("surface enclosing operation swallowed callback contracts")
    plain = _object(_named(result.get("ast"), "alias", "Plain").get("type"), "plain callable")
    if plain.get("generics") != [] or plain.get("contracts") != []:
        raise ValueError("surface plain callable fabricated generic binders or laws")


def _callable_telescope_roles(source: bytes, result: dict[str, Json]) -> None:
    alias = _named(result.get("ast"), "alias", "Dependent")
    generics = _sequence(alias.get("generics"), "alias telescope")
    if [_object(value, "alias generic").get("mode") for value in generics] != ["captures", "grade"]:
        raise ValueError("surface generic alias lost capture/grade binder kinds")
    callable_type = _object(alias.get("type"), "dependent callable type")
    parameters = _sequence(callable_type.get("parameters"), "callable telescope")
    if len(parameters) != 2 or callable_type.get("mode") != "Fn":
        raise ValueError("surface dependent callable telescope differs")
    length, data = [_object(value, "callable parameter") for value in parameters]
    if any(value.get("kind") != "parameter" for value in (length, data)):
        raise ValueError("surface callable parameters are not uniform binder nodes")
    if _texts(length.get("name")) != ["n"] or length.get("grade") is not None:
        raise ValueError("surface callable index binder acquired the next parameter's grade")
    _type_head(length.get("type"), "Nat", 0)
    _exact_span(source, length, b"Nat n")
    name_start = source.index(b"Nat n") + len(b"Nat ")
    if _object(length.get("name"), "index binder name").get("span") != [name_start, name_start + 1]:
        raise ValueError("surface callable binder name lost its own byte span")
    if _texts(data.get("name")) != ["bytes"] or _texts(data.get("grade")) != ["q"]:
        raise ValueError("surface callable grade is not attached to the byte-view parameter")
    _exact_span(source, data, b"in Span<byte, n> bytes @ q")
    grade_start = source.index(b"bytes @ q") + len(b"bytes @ ")
    if _object(data.get("grade"), "callable grade").get("span") != [grade_start, grade_start + 1]:
        raise ValueError("surface callable grade lost its own byte span")
    loan = _object(data.get("type"), "callable argument loan")
    if loan.get("modifier") != "in":
        raise ValueError("surface dependent argument loan mode differs")
    _type_head(loan.get("type"), "Span", 2)
    returned = _object(callable_type.get("result"), "dependent result")
    arguments = _type_head(returned, "Vec", 2)
    if _texts(arguments[1]) != ["n"]:
        raise ValueError("surface dependent result no longer names its input binder")
    _exact_span(source, returned, b"Vec<byte, n>")
    index_start = source.index(b"Vec<byte, n>") + len(b"Vec<byte, ")
    if _object(arguments[1], "result index").get("span") != [index_start, index_start + 1]:
        raise ValueError("surface result index span was conflated with its declaration")
    if _texts(callable_type.get("captures")) != ["C"] or _texts(callable_type.get("effects")) != ["Read"]:
        raise ValueError("surface dependent callable lost its capture/effect suffix")
    unnamed = _object(_named(result.get("ast"), "alias", "Unnamed").get("type"), "unnamed callable")
    argument = _object(_sequence(unnamed.get("parameters"), "unnamed telescope")[0], "unnamed argument")
    if argument.get("kind") != "parameter" or argument.get("name") is not None or argument.get("grade") is not None:
        raise ValueError("surface unnamed callable argument fabricated a binding or grade")
    higher = _object(_named(result.get("ast"), "alias", "Higher").get("type"), "higher callable")
    outer = _object(_sequence(higher.get("parameters"), "higher telescope")[0], "higher parameter")
    nested = _object(_object(outer.get("type"), "nested loan").get("type"), "nested callable")
    if nested.get("kind") != "function_type" or _texts(outer.get("name")) != ["build"]:
        raise ValueError("surface nested callable swallowed its enclosing binder")
    nested_parameter = _object(_sequence(nested.get("parameters"), "nested telescope")[0], "nested index")
    if _texts(nested_parameter.get("name")) != ["width"]:
        raise ValueError("surface nested callable lost its independent index binder")
    lambda_parameter = _named(result.get("ast"), "lambda_parameter", "n")
    if _texts(lambda_parameter.get("grade")) != ["q"]:
        raise ValueError("surface lambda parameter lost its use grade")
    _exact_span(source, lambda_parameter, b"Nat n @ q")
    value = _named(result.get("ast"), "lambda_parameter", "value")
    grade = _object(value.get("grade"), "lambda grade application")
    if grade.get("kind") != "call" or _texts(grade.get("callee")) != ["NatExact"]:
        raise ValueError("surface lambda grade is not an ordinary domain application")
    _exact_span(source, value, b"byte value @ NatExact(1)")


def _product_roles(source: bytes, result: dict[str, Json]) -> None:
    pair = _object(_named(result.get("ast"), "alias", "Pair").get("type"), "product alias")
    if pair.get("kind") != "tuple_type" or len(_sequence(pair.get("types"), "product components")) != 2:
        raise ValueError("surface product type lost component roles")
    _exact_span(source, pair, b"(T, U)")
    group = _object(_named(result.get("ast"), "alias", "Group").get("type"), "group type")
    if group.get("kind") != "group_type":
        raise ValueError("surface single type parentheses became a product")
    _type_head(group.get("type"), "Nat", 0)
    _exact_span(source, group, b"(Nat)")
    unit = _object(_named(result.get("ast"), "alias", "Empty").get("type"), "unit alias")
    if unit.get("kind") != "unit_type":
        raise ValueError("surface unit type conflated with value syntax")
    _exact_span(source, unit, b"()")
    package = _named(result.get("ast"), "function", "Package")
    returned = _object(package.get("result"), "resource product result")
    outer = _sequence(returned.get("types"), "resource product types")
    if returned.get("kind") != "tuple_type" or len(outer) != 2:
        raise ValueError("surface returned resource product shape differs")
    first, second = [_object(value, "resource component") for value in outer]
    inner = _sequence(second.get("types"), "nested resource types")
    if (first.get("modifier") != "owned" or second.get("kind") != "tuple_type"
            or len(inner) != 2 or _object(inner[0], "receipt type").get("modifier") != "tracked"
            or _object(inner[1], "empty type").get("kind") != "unit_type"):
        raise ValueError("surface product erased resource modifiers or nesting")
    destructures = [node for node in nodes(result.get("ast")) if node.get("kind") == "let_pattern"]
    if len(destructures) != 1:
        raise ValueError("surface local product elimination lost its statement role")
    destructure = destructures[0]
    _exact_span(source, destructure, b"let (let owner, (let receipt, ())) = package;")
    pattern = _object(destructure.get("pattern"), "local product pattern")
    _exact_span(source, pattern, b"(let owner, (let receipt, ()))")
    fields = _sequence(pattern.get("patterns"), "product pattern fields")
    if pattern.get("kind") != "tuple_pattern" or len(fields) != 2:
        raise ValueError("surface local product pattern shape differs")
    binding = _object(fields[0], "owner binding")
    if binding.get("kind") != "binding_pattern" or _texts(binding.get("name")) != ["owner"]:
        raise ValueError("surface product owner field is not a binding pattern")
    _exact_span(source, binding, b"let owner")
    nested = _object(fields[1], "nested product pattern")
    nested_fields = _sequence(nested.get("patterns"), "nested product pattern fields")
    if (nested.get("kind") != "tuple_pattern" or len(nested_fields) != 2
            or _object(nested_fields[1], "unit pattern").get("kind") != "unit_pattern"):
        raise ValueError("surface dependent resource pattern flattened or dropped its unit")
    if _texts(destructure.get("value")) != ["package"]:
        raise ValueError("surface product binding source was not retained")
    wildcards = [node for node in nodes(result.get("ast")) if node.get("kind") == "wildcard_pattern"]
    if len(wildcards) != 1:
        raise ValueError("surface wildcard pattern became a constructor or binding")
    _exact_span(source, wildcards[0], b"_")


def _explicit_type_argument_roles(source: bytes, result: dict[str, Json]) -> None:
    returned = _named(result.get("ast"), "alias", "Returned")
    arguments = _type_head(returned.get("type"), "Result", 2)
    explicit = _object(arguments[0], "explicit type argument")
    product = _object(explicit.get("type"), "explicit product type")
    if explicit.get("kind") != "type_argument" or product.get("kind") != "tuple_type":
        raise ValueError("surface explicit structural type argument lost its discriminator")
    _exact_span(source, explicit, b"type (owned Packet, tracked Receipt)")
    _exact_span(source, product, b"(owned Packet, tracked Receipt)")
    value = _named(result.get("ast"), "alias", "Value")
    argument = _object(_type_head(value.get("type"), "Indexed", 1)[0], "generic tuple value")
    if argument.get("kind") != "group" or _object(argument.get("value"), "tuple value").get("kind") != "tuple":
        raise ValueError("surface parenthesized generic value was reinterpreted as a type")
    _exact_span(source, argument, b"((a, b))")


def _structural_annotation_roles(source: bytes, result: dict[str, Json]) -> None:
    local = _named(result.get("ast"), "typed_local", "local")
    annotation = _object(local.get("type"), "place-named grouped loan")
    if annotation.get("modifier") != "ref" or _texts(annotation.get("lifetime")) != ["'self.text"]:
        raise ValueError("surface structural local annotation lost its place-named loan")
    group = _object(annotation.get("type"), "grouped view type")
    if group.get("kind") != "group_type":
        raise ValueError("surface structural local grouping lost its type role")
    _type_head(group.get("type"), "Span", 1)
    _exact_span(source, annotation, b"ref<'self.text> (Span<byte>)")
    for name, kind, spelling in (("pair", "tuple_type", b"(owned Packet, tracked Receipt) pair"),
                                 ("value", "unit_type", b"() value"),
                                 ("number", "group_type", b"(Nat) number")):
        parameter = _named(result.get("ast"), "lambda_parameter", name)
        if _object(parameter.get("type"), "lambda structural annotation").get("kind") != kind:
            raise ValueError("surface structural lambda parameter lost its type role")
        _exact_span(source, parameter, spelling)


def _conditional_shape(value: Json) -> Json:
    if value is None:
        return None
    statement = _object(value, "unbraced statement")
    if statement.get("kind") == "if":
        condition = _object(statement.get("condition"), "unbraced condition")
        if condition.get("kind") != "name":
            raise ValueError("surface conditional parentheses became a type annotation")
        names: list[Json] = list(_texts(condition))
        return ["if", names, _conditional_shape(statement.get("then")),
                _conditional_shape(statement.get("else"))]
    if statement.get("kind") == "assignment":
        assigned = _object(statement.get("value"), "unbraced assigned value")
        if (_texts(statement.get("target")) != ["value"]
                or _texts(statement.get("operator")) != ["="] or assigned.get("kind") != "nat"):
            raise ValueError("surface unbraced assignment was reinterpreted as a declaration")
        return ["set", assigned.get("value")]
    raise ValueError("surface unbraced conditional lost its assignment/conditional body")


def _callback_grade_roles(result: dict[str, Json]) -> None:
    declaration = _named(result.get("ast"), "function", "Declared")
    declared = _named(declaration, "parameter", "x")
    use = _named(result.get("ast"), "function", "Use")
    inferred = _named(use, "lambda_parameter", "x")
    for parameter in (declared, inferred):
        grade = _object(parameter.get("grade"), "callback-valued grade")
        if grade.get("kind") != "call" or _texts(grade.get("callee")) != ["Grade", "Of"]:
            raise ValueError("surface callback-valued grade detached from its binder")
        arguments = _sequence(grade.get("arguments"), "grade callback arguments")
        if len(arguments) != 1:
            raise ValueError("surface grade callback call lost its argument boundary")
        callback = _object(arguments[0], "grade callback")
        if callback.get("kind") != "lambda":
            raise ValueError("surface grade callback lost its lambda role")
        nested = _sequence(callback.get("parameters"), "grade callback parameters")
        if len(nested) != 1 or _texts(_object(nested[0], "grade callback parameter").get("name")) != ["n"]:
            raise ValueError("surface grade callback binder was conflated with the outer binder")
        body = _object(callback.get("body"), "grade callback block")
        statements = _sequence(body.get("statements"), "grade callback statements")
        if body.get("kind") != "block" or len(statements) != 3:
            raise ValueError("surface grade lookahead lost a callback block or statement")
        marker, delimiter, returned = [_object(value, "grade callback statement") for value in statements]
        text = _object(marker.get("value"), "grade callback string")
        character = _object(delimiter.get("value"), "grade callback character")
        if (marker.get("kind") != "let" or _texts(marker.get("name")) != ["marker"]
                or text.get("kind") != "string" or text.get("value") != '"}; ) @"'
                or delimiter.get("kind") != "let" or _texts(delimiter.get("name")) != ["delimiter"]
                or character.get("kind") != "character" or character.get("value") != "'}'"):
            raise ValueError("surface grade lookahead interpreted literal delimiters as structure")
        if returned.get("kind") != "return" or _texts(returned.get("value")) != ["n"]:
            raise ValueError("surface grade callback lost its return after literal/comment delimiters")


def _unbraced_if_roles(result: dict[str, Json]) -> None:
    expected: dict[str, Json] = {
        "Bare": ["if", ["ready"], ["set", "1"], None],
        "Paired": ["if", ["ready"], ["set", "1"], ["set", "2"]],
        "Nearest": ["if", ["ready"], ["if", ["permitted"], ["set", "1"], ["set", "2"]], None],
        "Chain": ["if", ["ready"], ["set", "1"], ["if", ["permitted"], ["set", "2"], ["set", "3"]]],
        "Trivia": ["if", ["ready"], ["set", "1"], None],
    }
    for name, shape in expected.items():
        function = _named(result.get("ast"), "function", name)
        body = _object(function.get("body"), "conditional function body")
        statements = _sequence(body.get("statements"), "conditional body statements")
        if len(statements) != 1 or _conditional_shape(statements[0]) != shape:
            raise ValueError(f"surface unbraced conditional/nearest-else shape differs in {name}")


def _indexed_constructor_roles(result: dict[str, Json]) -> None:
    vector = _named(result.get("ast"), "inductive", "Vec")
    for name in ("Nil", "Cons"):
        constructor = _constructor(vector, name)
        returned = _object(constructor.get("result"), "indexed constructor result")
        if returned.get("kind") != "type" or _texts(returned.get("name")) != ["Vec"]:
            raise ValueError("surface indexed constructor result head differs")
        arguments = returned.get("arguments")
        if not isinstance(arguments, list) or len(arguments) != 2 or _texts(arguments[0]) != ["T"]:
            raise ValueError("surface indexed constructor type arguments differ")
        index = _object(arguments[1], "constructor result index")
        if name == "Nil":
            if index.get("kind") != "nat" or index.get("value") != "0":
                raise ValueError("surface empty-vector constructor lost its zero index")
        else:
            if index.get("kind") != "group":
                raise ValueError("surface successor constructor lost its grouped index")
            addition = _object(index.get("value"), "successor index")
            right = _object(addition.get("right"), "successor constant")
            if (addition.get("kind") != "binary" or _texts(addition.get("operator")) != ["+"]
                    or _texts(addition.get("left")) != ["m"] or right.get("kind") != "nat"
                    or right.get("value") != "1"):
                raise ValueError("surface successor constructor index roles differ")
    natural = _named(result.get("ast"), "inductive", "Natural")
    successor = _constructor(natural, "Succ")
    if "result" not in successor or successor["result"] is not None:
        raise ValueError("surface unindexed constructor needs an explicit absent result")


def _numeric_pattern_roles(source: bytes, result: dict[str, Json]) -> None:
    patterns = [node for node in nodes(result.get("ast")) if node.get("kind") == "nat_pattern"]
    expected = ((b"0u8", "0", "u8"), (b"0b01", "0b01", ""))
    if len(patterns) != len(expected):
        raise ValueError("surface represented numeric pattern count differs")
    for pattern, (spelling, digits, suffix) in zip(patterns, expected, strict=True):
        start = source.index(spelling)
        if (pattern.get("value") != digits or pattern.get("suffix") != suffix
                or pattern.get("span") != [start, start + len(spelling)]):
            raise ValueError("surface numeric pattern lost spelling, representation or byte span")


def _handler_roles(result: dict[str, Json]) -> None:
    handlers = [node for node in nodes(result.get("ast"))
                if node.get("kind") == "handle" and node.get("shallow") is False]
    if len(handlers) != 1:
        raise ValueError("surface deep/shallow handler association differs")
    clauses = handlers[0].get("clauses")
    if not isinstance(clauses, list) or len(clauses) != 2:
        raise ValueError("surface handler clause roles differ")
    operation = _object(clauses[0], "operation clause")
    returned = _object(clauses[1], "handler return clause")
    if (operation.get("kind") != "operation_clause"
            or _texts(operation.get("name")) != ["Choose"]
            or _texts(operation.get("continuation")) != ["k"]):
        raise ValueError("surface operation/continuation roles differ")
    if (returned.get("kind") != "return_clause" or _texts(returned.get("name")) != ["score"]
            or _texts(returned.get("body")) != ["score"]):
        raise ValueError("surface handler return clause became a return statement")
    resumptions = [node for node in nodes(operation.get("body")) if node.get("kind") == "resume"]
    if len(resumptions) != 2 or any(_texts(resume) != ["k"] for resume in resumptions):
        raise ValueError("surface multi-shot resumption association differs")
    rehandled = [node for node in nodes(result.get("ast")) if node.get("kind") == "rehandle"]
    if len(rehandled) != 1:
        raise ValueError("surface rehandle lost its own expression role")


def _literal_and_comment_boundaries(parse: Callable[[bytes], dict[str, Json]]) -> None:
    # Delimiter-looking bytes inside comments and strings are never nesting.
    source = (b"// " + b"{" * 300 + b"\r\n/* " + b"[" * 300
              + " caf\u00e9 */\r\nmodule M; public Nat F() { let s = \"".encode()
              + b"(" * 300 + " caf\u00e9\"; return 0001usize; }".encode())
    result = parse(source)
    literals = [node for node in nodes(result.get("ast")) if node.get("kind") == "nat"]
    if len(literals) != 1 or literals[0].get("value") != "0001" or literals[0].get("suffix") != "usize":
        raise ValueError("surface decimal spelling/representation oracle differs")
    start = source.index(b"0001usize")
    if literals[0].get("span") != [start, start + len(b"0001usize")]:
        raise ValueError("surface UTF-8 original-byte literal span differs")


def _expression_shape(value: dict[str, Json]) -> Json:
    if value.get("kind") == "nat":
        return ["nat", value.get("value"), value.get("suffix")]
    if value.get("kind") == "binary":
        operator = _object(value.get("operator"), "binary operator")
        return [operator.get("text"),
                _expression_shape(_object(value.get("left"), "left operand")),
                _expression_shape(_object(value.get("right"), "right operand"))]
    raise ValueError(f"unexpected surface oracle expression: {value.get('kind')}")


def _precedence_and_spans(parse: Callable[[bytes], dict[str, Json]]) -> None:
    source = b"module M; public Nat F() { return 1 + 2 * 3; }"
    result = parse(source)
    tree = _object(result.get("ast"), "root")
    if tree.get("kind") != "surface_file" or tree.get("span") != [0, 46]:
        raise ValueError("surface root kind/span oracle differs")
    name = _object(tree.get("name"), "module name")
    if name != {"text": "M", "span": [7, 8]}:
        raise ValueError("surface module-name oracle differs")
    declarations = tree.get("declarations")
    if not isinstance(declarations, list) or len(declarations) != 1:
        raise ValueError("surface declaration count differs")
    function = _object(declarations[0], "function")
    if function.get("kind") != "function" or function.get("span") != [10, 46]:
        raise ValueError("surface function kind/span oracle differs")
    if function.get("modifiers") != ["public"] or function.get("parameters") != []:
        raise ValueError("surface function modifier/parameter oracle differs")
    if function.get("name") != {"text": "F", "span": [21, 22]}:
        raise ValueError("surface function-name oracle differs")
    body = _object(function.get("body"), "body")
    if body.get("kind") != "block" or body.get("span") != [25, 46]:
        raise ValueError("surface block oracle differs")
    statements = body.get("statements")
    if not isinstance(statements, list) or len(statements) != 1:
        raise ValueError("surface statement oracle differs")
    terminal = _object(statements[0], "return")
    if terminal.get("kind") != "return" or terminal.get("span") != [27, 44]:
        raise ValueError("surface return oracle differs")
    expression = _object(terminal.get("value"), "return value")
    expected: Json = ["+", ["nat", "1", ""],
                      ["*", ["nat", "2", ""], ["nat", "3", ""]]]
    if _expression_shape(expression) != expected or expression.get("span") != [34, 43]:
        raise ValueError("surface precedence/operand oracle differs")
    operator = _object(expression.get("operator"), "addition")
    if operator != {"text": "+", "span": [36, 37]}:
        raise ValueError("surface operator byte-span oracle differs")
    trailing = parse(source + b"\r\n// caf\xc3\xa9")
    if trailing.get("ast") != tree or trailing.get("source_sha256") == result.get("source_sha256"):
        raise ValueError("surface trailing trivia/source binding differs")


def qualify(parse: Callable[[bytes], dict[str, Json]]) -> list[str]:
    """Exercise independent syntax cases; a failed oracle never passes a case."""
    _precedence_and_spans(parse)
    _literal_and_comment_boundaries(parse)
    passed = ["surface:independent-precedence-and-spans", "surface:literal-and-comment-boundaries"]
    for fixture in POSITIVE:
        result = parse(fixture.source.encode("utf-8"))
        found = {node.get("kind") for node in nodes(result.get("ast"))}
        missing = set(fixture.kinds) - found
        if missing:
            raise ValueError(f"surface fixture {fixture.name} lacks AST roles: {sorted(missing)}")
        if fixture.name == "function-types-grades-and-contracts":
            _type_roles(result)
        elif fixture.name == "kinded-telescopes-and-associated-families":
            _kinded_family_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "type-valued-dependent-matches":
            _type_expression_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "callable-kinds-and-contract-effect-ownership":
            _callable_kind_effect_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "typed-callable-values-and-scoped-loans":
            _typed_callable_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "typed-callable-expression-composition":
            _typed_callable_composition_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "typed-resource-errors-remain-syntax":
            _typed_resource_error_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "indexed-family-and-constructor-contracts":
            _indexed_family_contract_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "stable-literal-generic-arguments":
            _stable_generic_literal_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "effect-operation-resource-contracts":
            _effect_resource_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "container-resource-contracts":
            _container_resource_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "named-handler-capabilities":
            _named_handler_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "dependent-match-expressions-and-motives":
            _dependent_match_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "graded-struct-fields":
            _field_grade_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "generic-library-implementations":
            _generic_impl_roles(result)
        elif fixture.name == "locally-quantified-callable-contracts":
            _scoped_callable_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "dependent-data-and-lifetimes":
            _receiver_roles(result)
        elif fixture.name == "typed-locals-and-scoped-callbacks":
            _typed_local_roles(result)
        elif fixture.name == "effects-handlers-and-disposal":
            _handler_roles(result)
        elif fixture.name == "generic-effect-families":
            _effect_generic_roles(result)
        elif fixture.name == "structured-tasks-and-cleanup":
            _cancellation_roles(result)
        elif fixture.name == "mathematical-definitions-and-proofs":
            _indexed_constructor_roles(result)
        elif fixture.name == "represented-numeric-patterns":
            _numeric_pattern_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "dependent-callable-telescopes":
            _callable_telescope_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "product-types-values-and-patterns":
            _product_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "explicit-structural-type-arguments":
            _explicit_type_argument_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "structural-local-and-lambda-annotations":
            _structural_annotation_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "unbraced-conditionals-and-annotation-lookahead":
            _unbraced_if_roles(result)
        elif fixture.name == "callback-expressions-in-grades":
            _callback_grade_roles(result)
        passed.append(f"surface:{fixture.name}")
    for name, source, kind in NEGATIVE:
        try:
            parse(source)
        except VelaError as error:
            if error.kind != kind:
                raise ValueError(f"surface refusal {name}: expected {kind}, got {error.kind}") from error
        else:
            raise ValueError(f"surface refusal {name} unexpectedly parsed")
        passed.append(f"surface:refusal:{name}:{kind}")
    for newline in (b"\n", b"\r\n", b"\r"):
        source = b"// caf\xc3\xa9" + newline + b"module M;" + newline + b"public void F() { let x = #; }"
        try:
            parse(source)
        except VelaError as error:
            if (error.kind, error.line, error.column) != ("syntax", 3, 27):
                raise ValueError("surface newline/UTF-8 diagnostic oracle differs") from error
        else:
            raise ValueError("surface malformed expression unexpectedly parsed")
        annotation = (b"module M;" + newline + b"public void F() {" + newline
                      + b"    Core.Span<byte> local = #;" + newline + b"}")
        try:
            parse(annotation)
        except VelaError as error:
            if (error.kind, error.line, error.column) != ("syntax", 3, 29):
                raise ValueError("surface annotation-lookahead diagnostic position differs") from error
        else:
            raise ValueError("surface incomplete generic local unexpectedly parsed")
    passed.append("surface:newline-and-utf8-diagnostics")
    return passed
