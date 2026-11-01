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
    return chosen;
}
""", ("effect", "handle", "resume", "dispose")),
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
public inductive Natural { Zero(); Succ(Natural predecessor); }
public coinductive Stream<T> { More(T head, Stream<T> tail); }
public lemma Reflexive(Nat n): forall (Nat x) => x == x
    proof { assert n == n; ?step; }
public theorem Witness(): exists (Nat n) => n == 0;
""", ("universe", "definition", "inductive", "coinductive", "lemma", "theorem", "quantifier")),
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
    ("missing-generic-argument", b"module M; public Result<Packet,> Parse();", "syntax"),
    ("incomplete-record", b"module M; public record Packet(Nat Count", "syntax"),
    ("incomplete-handler", b"module M; public Nat F() { return handle (G()) { return x =>", "syntax"),
    ("missing-effect-result", b"module M; public effect E { Choose() resumes(1); }", "syntax"),
    ("missing-match-colon", b"module M; public void F() { match (x) { case Ok(let x) return; } }", "syntax"),
    ("incomplete-cancel", b"module M; public async Nat F() { return 0; } on cancel", "syntax"),
    ("unterminated-string", b'module M; public void F() { let text = "unterminated', "syntax"),
    ("unterminated-comment", b"module M; /* unterminated {", "syntax"),
    ("chained-comparison", b"module M; public bool F() { return a < b < c; }", "syntax"),
    ("trailing-input", b"module M; public void F(); garbage", "syntax"),
    ("invalid-utf8", b"// invalid \xff\nmodule M; public void F();", "encoding"),
    ("literal-limit", b"module M; public Nat F() { return " + b"9" * 257 + b"; }", "limit"),
    ("delimiter-limit", b"module M; public Nat F() { return " + b"(" * 2000 + b"0" + b")" * 2000 + b"; }", "limit"),
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
        raise ValueError(f"surface fixture lacks {description}")
    return value


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
    passed = ["surface:independent-precedence-and-spans"]
    for fixture in POSITIVE:
        result = parse(fixture.source.encode("utf-8"))
        found = {node.get("kind") for node in nodes(result.get("ast"))}
        missing = set(fixture.kinds) - found
        if missing:
            raise ValueError(f"surface fixture {fixture.name} lacks AST roles: {sorted(missing)}")
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
    passed.append("surface:newline-and-utf8-diagnostics")
    return passed
