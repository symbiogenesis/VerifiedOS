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
        return ["if", _texts(condition), _conditional_shape(statement.get("then")),
                _conditional_shape(statement.get("else"))]
    if statement.get("kind") == "assignment":
        assigned = _object(statement.get("value"), "unbraced assigned value")
        if (_texts(statement.get("target")) != ["value"]
                or _texts(statement.get("operator")) != ["="] or assigned.get("kind") != "nat"):
            raise ValueError("surface unbraced assignment was reinterpreted as a declaration")
        return ["set", assigned.get("value")]
    raise ValueError("surface unbraced conditional lost its assignment/conditional body")


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
