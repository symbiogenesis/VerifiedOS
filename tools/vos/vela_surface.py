# SPDX-License-Identifier: Apache-2.0
"""Independent expected syntax and rejection cases for Vela's wider surface.

These cases describe source behavior, not semantic acceptance. In particular,
unknown names, duplicate declarations and invalid resource use must still parse.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from vos.vela import MAX_SOURCE_BYTES, VelaError
from vos.vela_ast import trivia_end

if TYPE_CHECKING:
    from vos.vela_parser import Json


@dataclass(frozen=True)
class Fixture:
    name: str
    source: str
    kinds: tuple[str, ...]


POSITIVE: tuple[Fixture, ...] = (
    Fixture("familiar-generic-calls-and-expression-arms", """// café: token shape fixes every generic application.
module Familiar;
import Vela.Numerics;
alias Count = int;
alias Qualified = Vela.Numerics.ulong;
definition T Identity<T>(T value) => value;
definition Nat Choose(Option<Nat> option) => match (option) {
    Some(value) => Identity<Nat>(value), None() => 0,
};
void Calls() {
    let genericSingle = Outer(F<A, B>(7));
    let comparisons = Outer(F /* unsuccessful probe */ <
        A, B > 7);
    let ambiguous = f /* comment */ < n > (x);
    let groupedComparison = (f < n) > x;
    let memberCall = Library.F<List<T>, (a < b), 'input, type (T, U),>(x);
    let computedCall = factory()<T>(x);
    let explicitValue = Apply(Identity::<Nat>, value);
    let explicitCall = Identity::<Nat>(value);
    let nestedValue = Choose<(Identity<T>(value))>(x);
    let typed = Build<type[Family<T>(true)]>(x);
    let Box<type[Family<T>(true)]> annotated = value;
    let callback = (Box<type[Family<T>(true)]> item) => item;
}
""", ("definition", "generic_application", "match_expression", "expression_case", "binary",
      "member", "computed_type", "type_argument", "lifetime")),
    Fixture("bounded-collection-iteration", """// café: modes, type annotations and range compatibility are syntax facts.
module Iteration;
void Visit(ref Span<byte> target, in Span<byte> source)
    where ISequenceModel(source) && IBoundedIterable(target)
    requires source.Model.All(x => x > 0)
    requires source.Model.Any(x => x == 1) && source.Model.Contains(1)
    ensures target.Model.Take(1).Skip(0).Slice(0, 1).Count == 1
{
    foreach (let copied in source) { Inspect(copied); }
    foreach (let byte typed in source) invariant Valid(source) { continue; }
    foreach (in borrowed in source) { Inspect(in borrowed); break; }
    foreach (in Core.Byte<byte> shared in source) { Inspect(in shared); }
    foreach (ref selected in target) { Update(ref selected); }
    foreach (ref Core.Byte<byte> exclusive in target)
        invariant Valid(target) decreases Remaining(target)
    {
        foreach (let inner in source) { Inspect(inner); }
        return;
    }
    foreach (let index in 0..target.Length) { continue; }
    foreach (let grouped in ((0..target.Length))) { break; }
    foreach (let usize explicitRange in 0..target.Length) {}
    foreach (ref loanRange in 0..target.Length) {}
    foreach (let invalidCopy in owners) { Consume(move invalidCopy); Consume(move invalidCopy); }
    foreach (ref invalidLoan in sharedSource) { Escape(ref invalidLoan); }
}
""", ("foreach", "foreach_collection", "contract", "break", "continue", "return", "range", "unary")),
    Fixture("raw-strings-and-checked-formatting", r'''// café: raw strings and buffer-writing format templates keep exact byte spans.
module CheckedFormatting;
public const Span<byte> SingleRaw = """exact "quoted" \raw café""";
public const Span<byte> MultiRaw = """
    VERSION 1
    MODE "STRICT" \raw
    """;
public Result<usize, CapacityError> WriteHeader<ghost Nat capacity>(
    ref TextBuilder<capacity> builder, ref Span<byte> scratch, usize id, byte tag)
    where Format(usize) && Format(byte)
    effects writes(builder), writes(scratch)
{
    let first = Format.Write(ref builder, $"packet[{id}]={{tag:{tag:x2}}}")?;
    let second = Format.Write(target: ref scratch, template: $"id={Identity::<usize>(id)}")?;
    let matched = match (SingleRaw) {
        """"matched """ \raw"""" => first + second,
        _ => 0usize,
    };
    let invalidStandaloneHeap = $"allocated {id}";
    let invalidReceiverRead = Format.Write(ref builder, $"len={builder.Length}");
    return Ok(matched);
}
''', ("constant", "function", "contract", "call", "propagate", "string",
      "string_pattern", "interpolated_string", "match_expression")),
    Fixture("numeric-separator-values-patterns-and-indices", """// café: retain every authored digit and separator.
module NumericSeparators;
public const usize Capacity = 1_024usize;
public definition Nat Scale(Nat count) => count + 1_000;
public alias Sized = Buffer<byte, 1_024>;
public byte Classify(byte value) => match (value) {
    0b1010_0011byte => 0xA_3u8,
    0xFF_FFu16 => 1_0,
};
""", ("constant", "definition", "alias", "nat", "nat_pattern", "match_expression")),
    Fixture("callable-list-boundaries", """module CallableLists;
public void Forms() {
    let noParameters = () => Zero();
    let oneParameter = (single) => single;
    let manyParameters = (left, right) => Pair(left, right);
    let trailingParameter = (last,) => last;
    let noClauses = handle (Empty()) {};
    let oneClause = handle (Single()) { return item => item };
    let manyClauses = handle (Multiple()) {
        Choose(chosen) with k => resume k(chosen), return answer => answer
    };
    let trailingClause = rehandle shallow (Trailing()) { return final => final, };
    let arguments = Apply(/* café */ Input(), label: Nested(inner: value,),);
}
""", ("lambda", "lambda_parameter", "handle", "rehandle", "operation_clause",
      "return_clause", "argument", "resume")),
    Fixture("concise-authoring-syntax", """// caf?: omitted syntax retains exact binder and expression locations.
module Concise;
alias Nested<T,> = Pair<T, List<Nat,>,>;
record Package<T,>(T Value,);
union Decision<T,> { Some(T Value,); None(); }
public Nat Increment(Nat value,) => value + 1;
public Nat Checked(Nat value,)
    requires Allowed(value)
    ensures Good(result)
    effects Inspect(item => item)
    => Increment(value,);
public Nat Grouped(Nat value)
    requires (let copy = value in Good(copy))
    ensures (forall (Nat item) => item == item)
    => value;
public Fn(Nat) -> Nat Build() requires (ready) => item => item;
public void Use() {
    let identity = item => item;
    let grouped = (value) => value;
    let combine = (left, right,) => left + right;
    let typed = (Nat amount,) => amount;
    let graded = (scoped ref byte slot @ NatExact(1),) => Read(in slot);
    let instance = Build::<Nat,>(1,);
    let (owner, receipt) = pair;
    var Some((nested, _),) = candidate;
    match (candidate) {
        case Some(payload,): Consume(payload);
        case None(): Empty();
        case fallback: Inspect(fallback);
    }
}
public Nat OperatorContract() requires (+) => 0;
public Nat ResumeContract() requires resume k(value) => 0;
public void StructuralPatterns() {
    let eliminated = match (value) {
        () => 0,
        (left, right) => left,
        (Some(item)) => item,
    };
    Fn() -> usize effects(Choose) score = () => Score();
}
public void InvalidMeaning() => move owner;
""", ("lambda", "lambda_parameter", "expression_body", "generic_parameter",
      "generic_application", "binding_pattern", "constructor_pattern", "wildcard_pattern",
      "tuple_pattern", "let_pattern", "var_pattern", "group", "quantifier", "let_expression")),
    Fixture("generic-binders-and-typed-initializers", """// café: generic roles and initializer owners retain original byte spans.
module BinderComposition;
alias Family<T : Type<u>, U, ghost Nat extent, region 'scope, effect E, captures C,
    grade q : NatExact> =
    Fn<region 'call, grade uses : NatExact>(scoped in<'call> T item @ uses) -> Vec<U, extent>
    captures C effects(E) with { requires Repeatable(C, uses); };
public void Bind<T, ghost Nat n, region 'input, captures Env, grade allowance : NatExact>(
    scoped in<'input> Vec<T, n> input, in Fn(T) -> T captures Env mapper) {
    Vec<T, n> direct @ NatExact(n) = input;
    let scoped in<'input> Vec<T, n> immutable @ allowance = input;
    var Vec<T, n> mutable @ allowance = direct;
    let computed = let Vec<T, n> chosen @ allowance = direct in chosen;
    let ungraded = let Vec<T, n> plain = direct in plain;
    let inferred = input;
    let Some(payload) = Fetch(input);
}
""", ("alias", "generic_parameter", "function_type", "modified_type", "contract",
      "typed_local", "let", "var", "let_expression", "let_pattern")),
    Fixture("binder-initializer-errors-remain-syntax", """module InvalidBinderMeaning;
alias Bad<ghost Nat duplicate, effect duplicate, captures C, grade q : UnknownDomain> =
    Fn(owned Packet<duplicate> item @ q) -> Packet<duplicate> captures C;
public void Invalid<ghost Nat n, grade q : UnknownDomain>(owned Packet<n> owner) {
    Packet<n> shared @ NatExact(0) = move owner;
    let Packet<n> copied @ q = move owner;
    var FnOnce() -> Packet<n> repeated @ NatExact(2) = () => move owner;
    let escaped = let ghost Nat runtime = Read() in runtime;
}
""", ("generic_parameter", "function_type", "typed_local", "let", "var", "unary", "let_expression")),
    Fixture("explicit-values-loans-and-options", """// café: binding, parameter and absence roles keep original byte spans.
module ExplicitValues;
alias Initializer = Fn<region 'slot>(out<'slot> Nat slot) -> Unit;
public void Modes<region 'slot>(Nat value, in Nat read, ref Nat write,
    out<'slot> Nat output, owned Packet packet) {
    let frozen = value;
    Nat defaultFrozen = value;
    var mutable = value;
    let out<'slot> Nat annotatedOutput = output;
    let callback = (out Nat destination) => Initialize(out destination);
    Apply(value, in read, ref write, out output, move packet);
    let present = Some(Some(value));
    let absent = None();
    let propagated = ReadOption()?;
    let hole = ?proof;
    let words = "null ?? ?. out";
    // null ?? ?. out stay comment text.
}
definition Nat Consume(Option<Option<Nat>> choice) => match (choice) {
    Some(Some(n)) => n,
    Some(None()) => 0,
    None() => 0,
};
""", ("modified_type", "unary", "let", "typed_local", "var", "lambda",
      "call", "match_expression", "constructor_pattern", "propagate", "hole", "string")),
    Fixture("explicit-pointer-operators", """// café: symbolic prefixes never change operator values.
module PointerOperators;
public void Pointers(Ptr<Nat> p, Nat i, Nat n) {
    let address = &p[i];
    let read = *p[i];
    let nested = *&p[i];
    let offset = *(p + n);
    let advance = p + n * 2;
    let difference = p - other;
    let arithmetic = *p * n & mask;
    let bitwise = flags & *p;
    let field = (*p).Value;
    let multiply = (*);
    let conjunction = (&);
    let apply = (*)(2, 3);
    let derived = (&)(p);
    *p = n;
    *p += 1;
}
""", ("unary", "binary", "index", "group", "member", "operator", "call", "assignment")),
    Fixture("explicit-values-errors-remain-syntax", """module ExplicitErrors;
public void Invalid(in Nat shared, ref Nat exclusive, out Nat output, owned Packet packet) {
    let frozen = 1;
    Nat alsoFrozen = 1;
    frozen = 2;
    alsoFrozen += 1;
    let u8 narrow = 300u64;
    let mixed = 1u8 + 2u64;
    let bool truthy = 1;
    let Option<Nat> lifted = 1;
    let Nat extracted = Some(1);
    Apply(shared, exclusive, output, packet);
    Apply(ref shared, in exclusive, ref output, move packet);
    Overlap(ref exclusive, ref exclusive);
    shared = 1;
    SharedCell.Write(ref shared);
    let invalidAddress = &1;
    let invalidRead = *1;
    let uninitialized = output;
    return;
}
definition Nat Partial(Option<Nat> choice) => match (choice) {
    Some(value) => value,
};
""", ("let", "typed_local", "assignment", "unary", "call", "match_expression")),
    Fixture("expression-local-bindings", """// café: expression bindings retain initializer and body scopes separately.
module LocalExpressions;
universe u;
definition Type<u> Family<T : Type<u>>(bool pair) =>
    let chosen = Select::<T>(pair) in chosen;
alias Shared = type[let chosen = Family::<Nat>(true) in chosen];
definition Type<u> Inject<T : Type<u>>(bool pair) =>
    let chosen = Select::<T>(pair) in type type[chosen];
public Nat Read(scoped in<'source> Nat source)
    requires (let amount = Limit(source) in amount <= 10)
    ensures (let expected = old(source) in result == expected)
{
    let result = let borrowed = in source in Inspect(borrowed);
    let annotated = let Nat value @ (let demand = 1 in demand) = 7 in value;
    let inferredGraded = let value @ q = Compute() in value;
    let deconstructed = let Ready((owner, receipt)) = Prepare() in Finish(owner, receipt);
    let product = let (left, right) = Pair() in left + right;
    let grouped = (let value = 1 in value) + 2;
    let applied = (let callable = (+) in callable)(1, 2);
    let projected = (let item = Build() in item).Value;
    let callback = (Nat input) => let doubled = input + input in doubled;
    let matched = match (ready) {
        Ready(loan) => let borrowed = in loan in Inspect(borrowed),
    };
    return let outer = 1 in let inner = outer + 1 in inner;
}
definition Nat Shadow(Nat value) =>
    let value = value in let value = value + 1 in value;
definition Fn(Nat value) -> Nat Callback() =>
    Fn(Nat value) -> Nat with { requires (let valid = Valid(value) in valid); }
    => let copied = value in copied;
""", ("let_expression", "let", "let_pattern", "computed_type", "type_expression", "contract",
      "constructor_pattern", "tuple_pattern", "lambda", "typed_lambda", "match_expression")),
    Fixture("expression-binding-errors-remain-syntax", """module InvalidExpressionBindings;
definition T Duplicate(owned T owner) => let retained = move owner in (owner, retained);
definition T Missing() => let value = value in value;
definition T Refutable() => let Some(value) = None() in value;
definition T Dropped(tracked T token) => let value @ 0 = Effectful(move token) in ();
definition in<'local> T Escape() => let owner = Local() in in owner;
""", ("let_expression", "let_pattern", "modified_type", "unary", "tuple", "unit")),
    Fixture("shared-syntax-primitives", """// café: shared forms preserve byte spans and syntax roles.
module SyntaxPrimitives;
alias Product = (Unit, (Core.Value));
alias Generic = Box<type (Unit, (Core.Value))>;
public void Compose() {
    (Unit, (Core.Value)) local = seed;
    let callback = ((Unit, (Core.Value)) input) => input;
    let empty = () => ();
    let values = (0007, 0xAfu8, "café", '\\n', true, false);
    match (token) {
        case 0007: return;
        case 0xAfu8: return;
        case "café": return;
        case '\\n': return;
        case true: return;
        case false: return;
    }
}
definition bool Nested() => forall (Nat outer) => exists (Nat inner) => outer == inner;
""", ("tuple_type", "type", "group_type", "typed_local", "lambda", "quantifier",
      "nat", "string", "character", "bool", "nat_pattern", "string_pattern", "character_pattern", "bool_pattern")),
    Fixture("shared-operator-values", """// café: operators retain symbol and expression spans independently.
module SharedOperators;
definition Fn(Nat x, Nat y) -> Nat Addition() => (+);
alias Computed = type[Family((+))];
public Nat Use(Nat left, Nat right) requires Law((+)) {
    let all = ((+), (-), (*), (/), (%), (<), (<=), (>), (>=), (==), (!=),
               (&&), (||), (&), (|), (^), (==>), (<==>), (!), (~));
    let direct = (+)(left, right);
    let projected = (*).Apply(left, right);
    let specialised = (%)::<Nat>(left, right);
    let higher = Fold((+), 0, values);
    let callback = (Nat item) => (-)(item);
    let directGeneric = Apply::<(+)>();
    let groupedGeneric = Apply::<((+))>();
    return direct;
}
domain Arithmetic {
    carrier Nat;
    zero 0;
    one 1;
    add (+);
    mul (*);
    admits (<=);
    interpret Identity;
    laws ArithmeticLaws;
}
""", ("operator", "function_type", "computed_type", "tuple", "member", "generic_application", "lambda", "domain")),
    Fixture("shared-operator-precedence", """module OperatorPrecedence;
definition Nat Ladder() => 1 ==> 2 <==> 3 || 4 && 5 == 6..7 | 8 ^ 9 & 10 + 11 * 12;
definition Nat Additive() => 20 - 6 + 2;
definition Nat Multiplicative() => 24 / 4 % 3 * 2;
definition Nat Disjunction() => 1 || 2 || 3;
definition Nat Conjunction() => 1 && 2 && 3;
definition Nat BitOr() => 1 | 2 | 3;
definition Nat BitXor() => 1 ^ 2 ^ 3;
definition Nat BitAnd() => 1 & 2 & 3;
definition Nat Implication() => 1 ==> 2 ==> 3;
definition Nat Equivalence() => 1 <==> 2 <==> 3;
definition Nat Prefixes() => !~-1;
definition Nat Grouping() => (-1) + (2 + 3);
""", ("binary", "range", "unary", "group")),
    Fixture("recursive-local-patterns", """// caf\u00e9: constructors and groups retain distinct pattern roles.
module LocalPatterns;
public void Eliminate() {
    let Some(value) = optional;
    var Ready((owner, receipt)) = outcome;
    let Result.Empty() = absent;
    let (Some((nested))) = wrapped;
    let Outer(Inner(deep), (item, ())) = tree;
    let ((grouped)) = source;
    let inferred = optional;
    var mutable @ q = source;
    let sharedLoan = (in ref value);
    let exclusiveLoan = (ref ref value);
    let Core.Box<Nat> annotated = source;
    Core.Box<Nat> bareAnnotated = source;
    var Core.Box<Nat> mutableAnnotated @ q = source;
    let ref<'source> Core.Box<Nat> loanAnnotated = source;
    let Core.Result.Ready(qualified) = source;
    match (optional) { case (Some((matched))): return; }
    let tested = optional is (Some((testedValue)));
    return;
}
public void InvalidMeaning() {
    let Missing(duplicate, duplicate) = true;
    var Ready() = 0;
    let Some(_) = trackedToken;
    let applyWrongArity = (+)();
    let nonCallable = (~).Missing::<bool>(true, false);
}
""", ("let_pattern", "var_pattern", "constructor_pattern", "group_pattern", "tuple_pattern", "unit_pattern", "wildcard_pattern", "match", "is", "let", "var")),
    Fixture("computed-types-and-family-application", """// café: computed types retain their expression and original byte span.
module ComputedTypes;
universe u;
alias Selected<ghost bool choose> = type[ChooseType(choose)];
alias Wrapped = Box<type[PayloadType(true)]>;
alias Structural = (owned type[OwnerType()], tracked type[ReceiptType()]);
definition Type<u> Reinject() => type type[ReifiedType()];
alias Conditional = type[match (flag) {
    true => type owned Packet,
    false => type Unit,
}];
trait Family<T : type[KindOf()]> {
    type Item : type[UniverseOf(T)] = type[MemberType(T)];
}
record Packed(bool Enabled, type[FieldType(Enabled)] Value);
public type[ResultType(value)] Select(type[InputType()] value) {
    type[LocalType(value)] local @ NatExact(1) = value;
    var type[MutableType(value)] changed = local;
    let callback = (scoped ref<'value> type[LoanType(value)] loan @ q) => loan;
    let typed = Fn(type[CallbackInput()] selected) -> type[OutputType(selected)]
        with { restores Closed(selected); } => selected;
    Box<type[GenericType(value)]> boxed = source;
    Box<type[match (flag) { true => type Nat, false => type bool, }]> choiceBox = source;
    let nestedCallback = (Box<type[match (callbackFlag) { true => type Nat, false => type bool, }]> item) => item;
    let generic = Apply::<type[CallType(value)]>(local);
    return local;
}
""", ("computed_type", "match_expression", "type_expression", "typed_local", "lambda", "typed_lambda", "generic_application")),
    Fixture("alias-and-effect-family-contracts", """// café: aliases and effect families own laws independently of their members.
module FamilyContracts;
alias Borrowed<T, region 'r> where Stable(T) requires Available(T) = ref<'r> T;
alias Reusable<T, grade q : NatExact> where Admits(T, q) effects reads(T) =
    Fn(T value @ q) -> T effects(Read)
        with { requires Open(value); restores Closed(value); };
alias Plain<T> = T;
effect Exchange<T, grade q : NatExact>
    where ExchangeLaw(T, q)
    invariant Closed(this)
    effects calls(Storage)
{
    owned T Replace(owned T replacement @ q) resumes(0..1)
        requires ReplacementReady(replacement)
        ensures ReplyReady(result)
        restores ReplacementClosed(result);
    ref<'input> T Borrow(ref T input) requires BorrowReady(input);
}
effect PlainEffect { Nat Read(); }
""", ("alias", "effect", "contract", "effects", "function_type", "effect_operation", "range")),
    Fixture("literal-patterns-and-dependent-branches", r"""// café: patterns preserve literal spelling rather than decoding it.
module LiteralPatterns;
definition Nat Classify(char marker) => match (marker) as token : Nat {
    'x' => 1,
    '\n' => 2,
    _ => 3,
};
definition Nat Parse(Text text) => match (text) {
    "ready" => 4,
    "// {\"}" => 5,
    _ => 6,
};
public void Inspect(Text text) {
    match (text) {
        case "" : return;
        case '\\' : return;
        case Token(('(', "closed")) : return;
    }
}
""", ("character_pattern", "string_pattern", "match_expression", "match", "tuple_pattern", "constructor_pattern")),
    Fixture("empty-dependent-elimination", """// café: expression and statement eliminators keep distinct roles.
module EmptyElimination;
inductive Never {}
definition T Absurd<T>(Never impossible) => match (impossible) as whole : T {};
alias EmptyFamily<ghost Never empty> = type[match (empty) as witness : Type<u> {}];
public T Eliminate<T>(Never absent) { return match (absent) {}; }
public void Use(Never missing, Never last) {
    let nested = Apply((match (missing) {}));
    let callback = (Never denied) => (match (denied) as dead : Unit {});
    match (missing) {}
    match (missing) {};
    match (missing) {} (missing);
    match (missing) {} -1;
    match (missing) {} { return; }
    let combined = (match (last) {}).Member(0) + 1;
}
""", ("inductive", "group", "match_expression", "match_motive", "computed_type", "lambda", "match")),
    Fixture("family-type-errors-remain-syntax", """module InvalidFamilies;
alias Invalid where false = type[17];
effect Impossible<grade q : NatExact> where false { tracked Permit Read() ensures false; }
definition Type<u> Erased(ghost bool erased) => type type[RuntimeRead(erased)];
public async void Invalid(ref Buffer buffer, tracked Permit permit) {
    type[buffer.CurrentType()] stale = move permit;
    buffer.Replace(replacement);
    let escaping = (scoped ref type[Unknown()] loan) => { await Ready(); return loan; };
    let impossible = (match (true) {});
    Use(move stale, move stale);
}
""", ("computed_type", "effect", "contract", "lambda", "match_expression", "modified_type", "unary")),
    Fixture("local-grades-and-evaluation", """// café: local allowances do not absorb initializer effects.
module LocalGrades;
public void Bind<grade q : NatExact>(ref Buffer source) {
    let inferred @ q = Input.Read();
    var mutable @ NatExact(2) = 0;
    let byte annotated @ q = 1byte;
    var scoped ref<'source> byte loan @ NatExact(1) = ref source[0];
    scoped ref<'source> byte direct @ q = ref source[1];
    let callback @ Grade.Of(Fn(Nat probe) -> Nat => probe) = Fn(Nat item) -> Nat => item;
    Nat dormant @ NatExact(0) = Effects.Read();
    Nat genericGrade @ Grade.Of::<T, U>() = source;
    Nat typeGrade @ type Box<Fn() -> Nat with { requires Ready(); }, U> = source;
    let plain = 7;
    let (left, right) = Pair();
}
""", ("let", "var", "typed_local", "modified_type", "typed_lambda", "let_pattern")),
    Fixture("local-grade-errors-remain-syntax", """module InvalidLocalGrades;
public async void Invalid(tracked Permit permit, ref Buffer source) {
    let duplicated @ NatExact(1) = move permit;
    Use(move duplicated, move duplicated);
    let erased @ NatExact(0) = Effectful(move permit);
    let escaping @ NatExact(1) = FnOnce(scoped ref byte loan) -> byte => {
        await Ready();
        return loan;
    };
    var stale @ NatExact(0) = source.Snapshot();
    source.Replace(replacement);
    Use(source[stale.Length]);
}
""", ("typed_lambda", "unary", "index", "let", "var")),
    Fixture("domain-dictionaries-and-product-laws", """// café: dictionary members use ordinary paths, products and callbacks.
module DomainDictionaries;
domain Product<A : GradeDomain, B : GradeDomain>
    where Compatible(A, B)
    effects calls(A.interpret, B.interpret)
{
    carrier (A.carrier, B.carrier);
    zero (A.zero, B.zero);
    one (A.one, B.one);
    add Fn((A.carrier, B.carrier) left, (A.carrier, B.carrier) right)
        -> (A.carrier, B.carrier)
        with { requires CompatibleValues(left, right); } => PairAdd(left, right);
    mul ProductMultiply;
    admits ProductAdmits;
    interpret Fn((A.carrier, B.carrier) demand) -> Nat effects(Read) => InterpretPair(demand);
    laws ProductLaws(A.laws, B.laws);
}
domain Legacy {
    carrier Nat;
    zero 0; one 1; add (+); mul (*);
    admits (==); interpret Use.Exact; laws ExactLaws;
}
alias Associated = Library.NatExact.carrier;
definition NatExact.carrier AddZero(NatExact.carrier value) => NatExact.add(value, NatExact.zero);
public void Inspect<grade q : NatExact>() {
    NatExact.carrier selected @ q = NatExact.one;
    let identity = (NatExact.carrier operand) => operand;
    let multiply = NatExact.mul(selected, selected);
    let permitted = NatExact.admits(selected, selected);
    let interpreted = NatExact.interpret(selected);
    let lawsValue = NatExact.laws;
}
""", ("domain", "generic_parameter", "contract", "effects", "tuple_type", "typed_lambda", "member", "lambda")),
    Fixture("disposal-clause-lifecycles", """// café: operation, return and disposal bodies retain separate owners.
module DisposalClauses;
public Nat Run() {
    let deep = handle (Read()) as active {
        Choose() with k => resume k(true),
        return done => done,
        dispose cancelled => { Cleanup(cancelled); return (); },
    };
    let outerHandler = handle shallow (Work()) {
        Choose() with outer => rehandle shallow (resume outer(true)) as forwarded {
            return nested => nested,
            dispose innerReason => Cleanup(innerReason),
        },
        dispose shallowReason => { dispose continuation; return (); },
    };
    return deep;
}
""", ("handle", "rehandle", "operation_clause", "return_clause", "disposal_clause", "dispose")),
    Fixture("disposal-errors-remain-syntax", """module InvalidDisposal;
public void Invalid() {
    let duplicate = handle (Run()) as forbidden {
        dispose first => forbidden.Choose(),
        dispose second => { resume missing(true); dispose missing; return (); },
        return result => result,
    };
}
""", ("handle", "disposal_clause", "resume", "dispose", "member")),
    Fixture("generic-callable-annotation-composition", """// café: callable arrows and contract braces never close generic arguments.
module GenericCallableAnnotations;
public void Bind<T, grade q : NatExact>() {
    Box<Fn(Nat n) -> Vec<T, n>> direct @ q = source;
    Result<owned Box<FnOnce<region 'r>(scoped ref<'r> T item @ q) -> T
        captures Environment effects(Read)
        with { requires Valid(item); restores Closed(item); }>, Error> nested = source;
    let callback = (Box<FnMut(T item) -> Unit effects(Write)
        with { restores Closed(item); }> box @ q, Nat index) => box;
    Box<Fn() -> (Fn(T) -> T)> higher = source;
    Index<(Fn(Nat sample) -> Nat => sample), (left <==> right)> computed = source;
    Index<("-> >")> literal = source;
    let comparisons = (left < right, low > high);
}
""", ("typed_local", "function_type", "generic_parameter", "contract", "modified_type", "lambda", "typed_lambda", "binary")),
    Fixture("kinded-telescopes-and-associated-families", """// café: kinds have spans distinct from their binders.
module KindedFamilies;
universe u;
alias Scoped<T : Type<u>, region 'loan> = Fn(scoped ref<'loan> T value) -> Unit;
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
definition Type<u> LoanType<T : Type<u>>(bool exclusive) where Stable(T) =>
    match (exclusive) as mode : Type<u> {
        true => type ref T,
        false => type in T,
    };
definition Type<u> Product<T>() => type (owned T, tracked Receipt);
definition Type<u> UnitType() => type Unit;
definition Type<u> Callback<T>() => type (Fn<region 'local>(
    scoped ref<'local> T value @ NatExact(1)) -> Unit
    with { restores Valid(value); });
public void Inspect() { Compare((type Nat), (type bool)); }
""", ("definition", "type_expression", "match_expression", "match_motive", "tuple_type", "type")),
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
    requires (type (Fn() -> bool effects(Read)))
    effects writes(Storage);
""", ("generic_parameter", "group_type", "function_type", "constructor", "type_expression", "effects")),
    Fixture("typed-callable-values-and-scoped-loans", """// café: a callable value reuses its annotation's exact resource roles.
module CallableValues;
universe u;
public void Use<T : Type<u>, captures C, grade q : NatExact>(in Cell<T> cell) {
    let update = FnMut<region 'r>(scoped ref<'r> T slot @ q) -> Unit
        captures C effects(Write)
        with { requires Valid(slot); restores Closed(final(slot)); }
        => { Mutate(ref slot); return; };
    cell.WithWrite(update);
    let consume = FnOnce(owned T item @ NatExact(1)) -> T
        with { ensures Returned(result); } => move item;
    let classify = Fn(bool flag) -> Type<u> =>
        match (flag) { true => type T, false => type Unit, };
}
""", ("typed_lambda", "function_type", "modified_type", "contract", "type_expression", "match_expression")),
    Fixture("typed-callable-expression-composition", """// café: explicit signatures compose wherever values occur.
module CallableComposition;
public void Compose() {
    Fn(Nat n) -> Nat => n;
    Apply(Fn(Nat x) -> Nat => x + 1, FnOnce() -> Unit => { return; });
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
    ensures Stable(result) => 0;
union Legacy { Done(); }
definition Nat Zero() => 0;
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
definition Type<u> ErasedChoice(ghost bool flag) =>
    match (flag) { true => type Packet, false => type Unit, };
public async void Invalid(owned Packet packet, tracked Receipt receipt) {
    let duplicate = Fn(owned Packet p @ NatExact(0)) -> (Packet, Packet)
        => (move p, move p);
    let escape = Fn<region 'local>(scoped ref<'local> Packet p) -> ref<'local> Packet
        => ref p;
    let suspended = FnOnce(scoped ref Packet p) -> Unit
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
    invariant Closed(this)
{
    private T Value @ q;
    public void Close() requires Opened(this) ensures Closed(this);
}
public interface Storage<T> where StorageLaw(T) {
    operation T Read() requires Readable(this) ensures Stable(result);
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
        Packed(count, bytes) => bytes,
    };
}
public Nat Inspect(owned Selection selected) {
    match (move selected) as choice : Nat {
        case Ready(payload): return payload.Length;
        case Rejected(debt): Close(move debt); return 0;
    }
}
public Nat Nested(bool flag) {
    return 2 + match (flag) {
        true => match (other) { false => 3, true => 4, },
        false => 5,
    } * 3;
}
public Result<ref<'workspace.bytes> byte, Error> Borrow(ref Workspace workspace) {
    return Wrap(match (Find(ref workspace)) as outcome : LoanResult<outcome> {
        Ok(selected) => Ok(selected),
        Err(error) => Err(error),
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
    scoped ref<'loan> T value @ q) -> Unit captures C effects(Write)
    with { requires Valid(value); restores Valid(final(value)); };
public void Apply<T>(in Fn<region 'local>(scoped ref<'local> T selected) -> Unit
    with { requires CallbackReady(selected); restores CallbackClosed(selected); } callback)
    requires CallerReady(callback)
    ensures CallerClosed(callback);
alias Plain = Fn(byte) -> byte;
""", ("alias", "function_type", "generic_parameter", "modified_type", "contract")),
    Fixture("dependent-elimination-errors-remain-syntax", """module InvalidElimination;
public async Nat Bad(ref BorrowCell<byte> cell, tracked Permit permit) {
    let incompatible = match (cell.TryWrite()) as observed : Bytes<observed.Length> {
        Acquired(writer, debt) => (move permit, move permit),
        BorrowConflict() => 0,
    };
    let escaping = match (incompatible) as erased : Never<missing> {
        _ => (scoped ref byte loan) => { await Ready(); return loan; },
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
alias Higher = Fn(in Fn(Nat width) -> Vec<byte, width> build, Nat count) -> (Vec<byte, count>, Unit);
public void Use<grade q : NatExact>(in Fn(Nat count) -> Vec<byte, count> build) {
    let project = (Nat n @ q, byte value @ NatExact(1)) => (n, value);
    Apply((scoped ref byte selected @ NatExact(1)) => { selected = 0byte; });
}
""", ("alias", "function_type", "parameter", "lambda_parameter", "tuple_type", "tuple")),
    Fixture("product-types-values-and-patterns", """module Products;
alias Pair<T, U> = (T, U);
alias Group = (Nat);
alias Empty = Unit;
public (owned Buffer, (tracked Permit, Unit)) Package(owned Buffer buffer, tracked Permit permit) {
    return (move buffer, (move permit, ()));
}
public Unit Consume((owned Buffer, (tracked Permit, Unit)) package) {
    let (owner, (receipt, ())) = package;
    var (left, right) = (1, 2);
    match ((move owner, (move receipt, ()))) {
        case (live, (token, ())):
            Finish(move live, move token);
    }
    match (left) { case _: return (); }
}
""", ("tuple_type", "group_type", "type", "tuple", "unit", "tuple_pattern",
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
alias UnitBox = Box<Unit>;
alias Value = Indexed<((a, b))>;
public void Use() { Construct::<type (Nat, bool)>(value); }
""", ("tuple_type", "function_type", "group_type", "type", "tuple", "generic_application")),
    Fixture("structural-local-and-lambda-annotations", """module StructuralAnnotations;
public void Use(ref Span<byte> text) {
    ref<'this.text> (Span<byte>) local = ref text;
    (owned Packet, tracked Receipt) package = source;
    Unit empty = ();
    let pairIdentity = ((owned Packet, tracked Receipt) pair) => pair;
    let unitIdentity = (Unit value) => value;
    let groupedIdentity = ((Nat) number) => number;
}
""", ("typed_local", "modified_type", "group_type", "tuple_type", "type", "lambda")),
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
    restores result is Ok(slot) ==> workspace.bytes.Model == old(workspace.bytes.Model).Set(0, final(slot))
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
        case Packed(length, storage, evidence):
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
        case BorrowConflict(): return Err(Conflict);
        case CapacityExhausted(): return Err(Capacity);
    }
}
private Result WithWrite(ref BorrowCell<byte> cell,
    in Fn(scoped ref byte selected) -> Unit callback) {
    match (cell.TryWrite()) {
        case Acquired(writer, debt):
            callback(ref writer.Value);
            cell.ReleaseWrite(move writer, move debt);
            return Ok();
        case BorrowConflict(): return Err(Conflict);
    }
}
public void Replace(ref LocalCell<Buffer> cell, owned Buffer replacement) {
    let displaced = cell.Replace(move replacement);
    Dispose(move displaced);
}
""", ("function_type", "lambda", "type", "unit", "unit_pattern", "match", "call")),
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
    public void Push(ref this.Tail, T item)
        requires this.Length < capacity
        ensures this.Model == old(this.Model).Append(item);
}
""", ("record", "union", "struct", "view", "generic_parameter", "modified_type")),
    Fixture("function-types-grades-and-contracts", """module Maps;
public Result<ref<'table> Value, Error> Find<ghost Nat n, captures C, grade q : NatExact>(
    ref Table<Key, Value, n> table,
    in Fn(byte) -> byte captures C effects(Choose) transform @ q)
    where Duplicable(C)
    requires n > 0
    effects reads(C), writes(table)
    ensures result is Ok(slot) ==> slot == old(table.Model).Get(0)
    restores result is Ok(slot) ==> table.Model == old(table.Model).Set(0, final(slot));
public void Use(owned Packet packet, tracked Permit permit, scoped ref byte selected);
""", ("function_type", "generic_parameter", "parameter", "modified_type")),
    Fixture("control-loans-and-proof", """module Fill;
public void Fill(ref Span<byte> target) {
    var seen = 0usize;
    ref byte first = ref target[0usize];
    foreach (let i in 0usize..target.Length)
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
        case Ok(packet): Forward(in packet.Data);
        case Err(error): Report(error);
    }
    if (true) return;
    return;
}
""", ("foreach", "while", "match", "proof", "hole", "if", "return")),
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
    let result = (Read()?).Value;
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
            case Spawned(task): return Ok(await task);
            case Full(unstarted, verdict): return Err(move unstarted);
        }
    }
}
""", ("function", "scope", "match", "unary", "return")),
    Fixture("mathematical-definitions-and-proofs", """module Mathematics;
universe u;
public definition Nat Twice(Nat x) => x + x;
public definition Type<u> Identity<T>(T value) => T;
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
    Fixture("required-static-constants", """// café: declaration order and constant spans are original bytes.
module Constants;
public Nat Square(Nat value) => value * value;
public const Nat Limit = Square(value: 4);
public const bool Ready = Limit == 16;
public struct Bounds<T> {
    public const usize Capacity = 8usize;
    private const Nat Doubled = Limit + Limit;
    public void Use(Nat runtime) {
        const Nat Local = Limit + 1;
        const Nat Invalid = runtime;
        const ghost Nat Erased = runtime;
        Consume(Local);
    }
}
""", ("constant", "constant_local", "type", "argument", "modified_type")),
    Fixture("compositional-constant-callables", """// café: const has declaration and telescope roles.
module StaticCalls;
public const Nat Square(Nat value) => value * value;
public Nat Scale(const Nat factor, Nat value) {
    const Nat multiplier = Square(factor);
    return multiplier * value;
}
const internal Nat Hidden(Nat value) => Square(value);
alias StaticMap = Fn(const Nat dimension, Nat item) -> Nat;
definition StaticMap Build() => (const Nat coefficient, Nat element) => coefficient * element;
definition StaticMap Explicit() => Fn(const Nat axis, Nat entry) -> Nat => axis * entry;
interface StaticProvider {
    public const Nat Select(const Nat selector);
}
""", ("function", "parameter", "constant_local", "function_type", "lambda_parameter", "typed_lambda", "interface")),
    Fixture("canonical-readable-calls", """// café: labels and explicit modes have separate spans.
module Readable;
alias Outcome = Result<Unit, Error>;
public void Use(ref Span<byte> bytes) requires Valid(this) {
    Fill(target: ref bytes, value: 0byte);
    Forward(in bytes, count: bytes.Length);
    Transfer(input: in source, target: ref bytes, output: out nextSlot, owner: move packet);
    let exact = Fn(Nat n, Vec<byte, n> values) -> Vec<byte, n> => values;
    let selected = exact(n: 1, values: Singleton());
    foreach (let index in 0usize..bytes.Length)
        invariant Valid(this)
    {
        ref byte selected = ref bytes[index];
        if (index == 0usize) { continue; }
        if (index == 1usize) { break; }
        if (index == 2usize) { return; }
        selected = 0byte;
    }
}
""", ("argument", "function_type", "typed_lambda", "foreach", "type", "unary")),
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
    ("legacy-definition-body", b"module M; definition Nat F() = 0;", "syntax"),
    ("combined-definition-bodies", b"module M; definition Nat F() = => 0;", "syntax"),
    ("legacy-expression-arms", b"module M; Nat F() => match (x) { case _ => 0; };", "syntax"),
    ("expression-arm-semicolons", b"module M; Nat F() => match (x) { _ => 0; };", "syntax"),
    ("expression-arms-empty-comma", b"module M; Nat F() => match (x) { , };", "syntax"),
    ("expression-arms-double-comma", b"module M; Nat F() => match (x) { _ => 0,, };", "syntax"),
    ("selected-generic-call-incomplete", b"module M; Nat F() => f<T>(;", "syntax"),
    ("collection-missing-binder", b"module M; void F() { foreach (let in values) {} }", "syntax"),
    ("collection-missing-in", b"module M; void F() { foreach (let item values) {} }", "syntax"),
    ("collection-missing-source", b"module M; void F() { foreach (in item in) {} }", "syntax"),
    ("collection-out-binder", b"module M; void F() { foreach (out item in values) {} }", "syntax"),
    ("collection-move-binder", b"module M; void F() { foreach (move item in values) {} }", "syntax"),
    ("collection-var-binder", b"module M; void F() { foreach (var item in values) {} }", "syntax"),
    ("collection-incomplete-type", b"module M; void F() { foreach (ref Box<T item in values) {} }", "syntax"),
    ("collection-unbraced-body", b"module M; void F() { foreach (let item in values) Consume(item); }", "syntax"),
    ("repeated-const-function", b"module M; public const const Nat F() => 1;", "syntax"),
    ("repeated-const-parameter", b"module M; Nat F(const const Nat value) => value;", "syntax"),
    ("repeated-const-lambda-parameter", b"module M; Nat F() => (const const Nat value) => value;", "syntax"),
    ("const-parameter-missing-type", b"module M; Nat F(const) => 0;", "syntax"),
    ("const-general-type-qualifier", b"module M; alias X = const Nat;", "syntax"),
    ("const-non-callable-declaration", b"module M; const struct X {}", "syntax"),
    ("constant-missing-type", b"module M; public const Limit = 1;", "syntax"),
    ("constant-missing-initializer", b"module M; public const Nat Limit;", "syntax"),
    ("constant-missing-value", b"module M; public const Nat Limit = ;", "syntax"),
    ("constant-local-missing-type", b"module M; void F() { const Limit = 1; }", "syntax"),
    ("empty-parenthesized-type", b"module M; alias Empty = ();", "syntax"),
    ("noncanonical-range-loop", b"module M; void F() { for (let index in 0..count) {} }", "syntax"),
    ("missing-named-argument-value", b"module M; Nat F() => Call(value:);", "syntax"),
    ("missing-named-argument-label", b"module M; Nat F() => Call(: 1);", "syntax"),
    ("arrow-missing-expression", b"module M; Nat F() => ;", "syntax"),
    ("arrow-missing-semicolon", b"module M; Nat F() => 1", "syntax"),
    ("arrow-double-arrow", b"module M; Nat F() => => 1;", "syntax"),
    ("empty-parameter-trailing-comma", b"module M; Nat F(,) => 1;", "syntax"),
    ("double-parameter-comma", b"module M; Nat F(Nat value,,) => value;", "syntax"),
    ("empty-call-trailing-comma", b"module M; Nat F() => Call(,);", "syntax"),
    ("double-call-comma", b"module M; Nat F() => Call(1,,);", "syntax"),
    ("empty-generic-trailing-comma", b"module M; alias X<,> = Nat;", "syntax"),
    ("double-generic-comma", b"module M; alias X<T,,> = T;", "syntax"),
    ("empty-generic-arguments-comma", b"module M; alias X = Box<,>;", "syntax"),
    ("double-lambda-comma", b"module M; Nat F() => (left,,right) => left;", "syntax"),
    ("empty-lambda-comma", b"module M; Nat F() => (,) => 0;", "syntax"),
    ("empty-handler-comma", b"module M; Nat F() => handle (Run()) { , };", "syntax"),
    ("double-handler-comma", b"module M; Nat F() => handle (Run()) { return x => x,, };", "syntax"),
    ("grouped-singleton-not-product", b"module M; Nat F() => (value,);", "syntax"),
    ("typed-singleton-not-product", b"module M; alias X = (Nat,);", "syntax"),
    ("qualified-constructor-without-arguments", b"module M; void F() { match (x) { case Result.None: return; } }", "syntax"),
    ("redundant-pattern-let", b"module M; void F() { let (let left, let right) = pair; }", "syntax"),
    ("contract-let-needs-grouping", b"module M; Nat F() requires let x = 1 in x == 1 => 1;", "syntax"),
    ("contract-quantifier-needs-grouping", b"module M; Nat F() requires forall (Nat n) => n == n => 1;", "syntax"),
    ("lambda-probe-comment-depth", b"module M; Nat F() => (" + b"/*" * 257 + b"*/" * 257 + b"x) => x;", "limit"),
    ("lambda-probe-delimiter-depth", b"module M; Nat F() => (" + b"(" * 257 + b"x" + b")" * 257 + b") => x;", "limit"),
    ("ghost-generic-missing-name", b"module M; alias A<ghost Nat> = Nat;", "syntax"),
    ("region-generic-missing-lifetime", b"module M; alias A<region r> = Nat;", "syntax"),
    ("effect-generic-missing-name", b"module M; alias A<effect> = Nat;", "syntax"),
    ("captures-generic-missing-name", b"module M; alias A<captures> = Nat;", "syntax"),
    ("grade-generic-missing-colon", b"module M; alias A<grade q NatExact> = Nat;", "syntax"),
    ("grade-generic-missing-domain", b"module M; alias A<grade q :> = Nat;", "syntax"),
    ("null-literal", b"module M; void F() { let value = null; }", "syntax"),
    ("null-binder", b"module M; void F() { let null = value; }", "syntax"),
    ("nullable-type", b"module M; alias A = Nat?;", "syntax"),
    ("nullable-parameter", b"module M; void F(Nat? value) {}", "syntax"),
    ("nullable-local", b"module M; void F() { let Nat? value = None(); }", "syntax"),
    ("null-forgiving", b"module M; definition T F() => value!;", "syntax"),
    ("null-coalescing", b"module M; definition T F() => value??other;", "syntax"),
    ("null-conditional", b"module M; definition T F() => value?.Member;", "syntax"),
    ("pointer-declarator", b"module M; alias A = Nat*;", "syntax"),
    ("pointer-parameter-declarator", b"module M; void F(Nat* p) {}", "syntax"),
    ("pointer-member-arrow", b"module M; definition T F() => p->Member;", "syntax"),
    ("out-missing-type", b"module M; void F(out) {}", "syntax"),
    ("out-missing-argument", b"module M; void F() { Apply(out); }", "syntax"),
    ("out-incomplete-lifetime", b"module M; void F(out<'slot Nat value) {}", "syntax"),
    ("out-incomplete-local", b"module M; void F() { let out Nat = value; }", "syntax"),
    ("dereference-missing-operand", b"module M; definition T F() => *;", "syntax"),
    ("address-missing-operand", b"module M; definition T F() => &;", "syntax"),
    ("pointer-prefix-incomplete-group", b"module M; definition T F() => *(;", "syntax"),
    ("out-prefix-depth", b"module M; definition T F() => " + b"out " * 257 + b"value;", "limit"),
    ("pointer-prefix-depth", b"module M; definition T F() => " + b"*&" * 129 + b"value;", "limit"),
    ("expression-binding-missing-name", b"module M; definition T F() => let = value in value;", "syntax"),
    ("expression-binding-missing-initializer", b"module M; definition T F() => let value = in value;", "syntax"),
    ("expression-binding-missing-delimiter", b"module M; definition T F() => let value = source value;", "syntax"),
    ("expression-binding-missing-body", b"module M; definition T F() => let value = source in;", "syntax"),
    ("expression-binding-statement-terminator", b"module M; definition T F() => let value = source; in value;", "syntax"),
    ("expression-binding-mutable-keyword", b"module M; definition T F() => var value = source in value;", "syntax"),
    ("expression-binding-missing-annotation-name", b"module M; definition T F() => let ref T = source in value;", "syntax"),
    ("expression-binding-incomplete-grade", b"module M; definition T F() => let value @ = source in value;", "syntax"),
    ("expression-binding-incomplete-pattern", b"module M; definition T F() => let Some(let) = source in value;", "syntax"),
    ("expression-binding-pattern-grade", b"module M; definition T F() => let Some(x) @ q = source in x;", "syntax"),
    ("expression-binding-body-depth", b"module M; definition T F() => " + b"let value = source in " * 257 + b"value;", "limit"),
    ("expression-binding-initializer-depth", b"module M; definition T F() => " + b"let value = " * 257
     + b"source" + b" in value" * 257 + b";", "limit"),
    ("operator-value-missing-close", b"module M; definition T F() => (+;", "syntax"),
    ("operator-value-mixed-symbols", b"module M; definition T F() => (+*);", "syntax"),
    ("operator-value-plus-operand", b"module M; definition T F() => (+ 1);", "syntax"),
    ("operator-value-assignment", b"module M; definition T F() => (=);", "syntax"),
    ("operator-value-range", b"module M; definition T F() => (..);", "syntax"),
    ("operator-value-propagation", b"module M; definition T F() => (?);", "syntax"),
    ("operator-value-keyword", b"module M; definition T F() => (await);", "syntax"),
    ("operator-generic-missing-close", b"module M; definition T F() => Apply::<(+>();", "syntax"),
    ("operator-generic-doubled-comma", b"module M; definition T F() => Apply::<(+),,>();", "syntax"),
    ("operator-group-depth", b"module M; definition T F() => " + b"(" * 257
     + b"(+)" + b")" * 257 + b";", "limit"),
    ("local-constructor-incomplete-argument", b"module M; void F() { let Some(let) = value; }", "syntax"),
    ("local-constructor-doubled-comma", b"module M; void F() { var Some(x,,) = value; }", "syntax"),
    ("local-constructor-missing-initializer", b"module M; void F() { let Some(x) = ; }", "syntax"),
    ("local-constructor-grade", b"module M; void F() { let Some(x) @ q = value; }", "syntax"),
    ("local-qualified-constructor-missing-parentheses", b"module M; void F() { let Result.Empty = value; }", "syntax"),
    ("local-pattern-incomplete-group", b"module M; void F() { let (let x = value; }", "syntax"),
    ("local-pattern-group-trailing-comma", b"module M; void F() { let ((x),) = value; }", "syntax"),
    ("group-pattern-missing-close", b"module M; void F() { match (x) { case (Some(value): return; } }", "syntax"),
    ("local-constructor-pattern-depth", b"module M; void F() { let " + b"Some(" * 257
     + b"value" + b")" * 257 + b" = source; }", "limit"),
    ("local-group-pattern-depth", b"module M; void F() { let " + b"(" * 257
     + b"value" + b")" * 257 + b" = source; }", "limit"),
    ("local-pattern-syntax-depth", b"module M; void F() { let " + b"Some((" * 126
     + b"value" + b"))" * 126 + b" = source; }", "limit"),
    *((f"nonassociative-{name}", b"module M; definition T F() => 1 " + symbol
       + b" 2 " + symbol + b" 3;", "syntax")
      for name, symbol in (("equal", b"=="), ("unequal", b"!="), ("less", b"<"),
                           ("less-equal", b"<="), ("greater", b">"), ("greater-equal", b">="),
                           ("range", b".."))),
    ("computed-type-missing-value", b"module M; alias A = type[];", "syntax"),
    ("computed-type-missing-close", b"module M; alias A = type[Family();", "syntax"),
    ("computed-type-wrong-delimiter", b"module M; alias A = type(Family());", "syntax"),
    ("computed-type-generic-missing-value", b"module M; alias A = Box<type[]>;", "syntax"),
    ("computed-type-local-missing-binder", b"module M; void F() { type[Family()] = value; }", "syntax"),
    ("computed-type-lambda-missing-binder", b"module M; void F() { let f = (type[Family()]) => value; }", "syntax"),
    ("computed-type-lookahead-depth", b"module M; void F() { type[" + b"(" * 257
     + b"Family()" + b")" * 257 + b"] local = value; }", "limit"),
    ("alias-missing-law", b"module M; alias A<T> where = T;", "syntax"),
    ("alias-law-after-definition", b"module M; alias A = T where Law(T);", "syntax"),
    ("alias-missing-effect", b"module M; alias A effects = T;", "syntax"),
    ("effect-family-missing-law", b"module M; effect E<T> where { Nat Get(); }", "syntax"),
    ("effect-family-missing-invariant", b"module M; effect E invariant { Nat Get(); }", "syntax"),
    ("effect-family-law-semicolon", b"module M; effect E where Ready(); { Nat Get(); }", "syntax"),
    ("literal-pattern-missing-arrow", b'module M; Nat F() { return match (x) { "ready" 1, }; }', "syntax"),
    ("literal-pattern-unterminated-string", b'module M; Nat F() { return match (x) { "ready => 1, }; }', "syntax"),
    ("literal-pattern-empty-character", b"module M; void F() { match (x) { case '' : return; } }", "syntax"),
    ("empty-match-missing-group-close", b"module M; definition T F() => (match (x) {};", "syntax"),
    ("empty-match-missing-motive-name", b"module M; definition T F() => (match (x) as : T {});", "syntax"),
    ("empty-match-missing-motive-type", b"module M; definition T F() => (match (x) as p : {});", "syntax"),
    ("empty-match-missing-motive-colon", b"module M; definition T F() => (match (x) as p T {});", "syntax"),
    ("empty-match-ungrouped-operator", b"module M; definition Nat F() => match (x) {} + 1;", "syntax"),
    ("empty-match-ungrouped-postfix", b"module M; definition Nat F() => match (x) {}.Member();", "syntax"),
    ("local-inferred-missing-grade", b"module M; void F() { let value @ = Make(); }", "syntax"),
    ("local-var-missing-grade", b"module M; void F() { var Nat value @ = Make(); }", "syntax"),
    ("local-bare-missing-grade", b"module M; void F() { Nat value @ = Make(); }", "syntax"),
    ("local-grade-after-initializer", b"module M; void F() { let value = Make() @ q; }", "syntax"),
    ("local-grade-without-initializer", b"module M; void F() { let value @ q; }", "syntax"),
    ("local-pattern-grade", b"module M; void F() { let (x, y) @ q = Pair(); }", "syntax"),
    ("local-grade-lookahead-depth", b"module M; void F() { Nat value @ " + b"(" * 257
     + b"q" + b")" * 257 + b" = Make(); }", "limit"),
    ("domain-incomplete-telescope", b"module M; domain Product<A,,> {}", "syntax"),
    ("domain-incomplete-law", b"module M; domain Product<A> where {}", "syntax"),
    ("domain-missing-carrier-member", b"module M; alias A = D.;", "syntax"),
    ("domain-member-without-value", b"module M; void F() { D.add(); let value = D.; }", "syntax"),
    ("domain-role-remains-reserved", b"module M; definition Nat add() => 0;", "syntax"),
    ("domain-role-remains-reserved-value", b"module M; void F() { let value = zero; }", "syntax"),
    ("disposal-clause-missing-binder", b"module M; void F() { handle (Run()) { dispose => Cleanup(); }; }", "syntax"),
    ("disposal-clause-missing-arrow", b"module M; void F() { handle (Run()) { dispose reason Cleanup(reason), }; }", "syntax"),
    ("disposal-clause-missing-body", b"module M; void F() { handle (Run()) { dispose reason =>, }; }", "syntax"),
    ("disposal-clause-semicolon-separator", b"module M; void F() { handle (Run()) { dispose reason => Cleanup(reason); }; }", "syntax"),
    ("disposal-clause-body-depth", b"module M; void F() { handle (Run()) { dispose reason => "
     + b"{" * 257 + b"return ();" + b"}" * 257 + b", }; }", "limit"),
    ("generic-callable-missing-result", b"module M; void F() { Box<Fn() ->> value = source; }", "syntax"),
    ("generic-callable-broken-arrow", b"module M; void F() { Box<Fn() - > Nat> value = source; }", "syntax"),
    ("generic-callable-missing-contract-value", b"module M; void F() { Box<Fn() -> Nat with { restores; }> value = source; }", "syntax"),
    ("generic-callable-contract-lookahead-depth", b"module M; void F() { Box<Fn() -> Nat with "
     + b"{" * 257 + b"requires Ready();" + b"}" * 257 + b"> value = source; }", "limit"),
    ("ungrouped-callable-kind", b"module M; alias A<F : Fn() -> Nat> = F;", "syntax"),
    ("ungrouped-associated-callable-kind", b"module M; trait F { type A : Fn() -> Nat; }", "syntax"),
    ("ungrouped-callable-type-expression", b"module M; definition Type<u> F() => type Fn() -> Nat;", "syntax"),
    ("typed-callable-statement-missing-body", b"module M; void F() { Fn() -> Nat =>; }", "syntax"),
    ("typed-callable-argument-missing-body", b"module M; void F() { Apply(Fn() -> Nat =>); }", "syntax"),
    ("typed-callable-return-missing-body", b"module M; void F() { let f = Fn() -> (Fn() -> Nat) =>; }", "syntax"),
    ("type-binder-missing-kind", b"module M; alias Box<T :> = T;", "syntax"),
    ("type-binder-missing-name", b"module M; alias Box<: Type<u>> = T;", "syntax"),
    ("associated-missing-kind", b"module M; trait F { type Value :; }", "syntax"),
    ("associated-missing-law", b"module M; trait F { type Value : Type<u> where; }", "syntax"),
    ("associated-kind-after-law", b"module M; trait F { type Value where Stable(T) : Type<u>; }", "syntax"),
    ("type-expression-missing-type", b"module M; definition Type<u> F() => type;", "syntax"),
    ("type-expression-missing-component", b"module M; definition Type<u> F() => type (T,);", "syntax"),
    ("type-expression-incomplete-callable", b"module M; definition Type<u> F() => type Fn(T) ->;", "syntax"),
    ("typed-lambda-missing-result", b"module M; void F() { let f = Fn(T x) -> => x; }", "syntax"),
    ("typed-lambda-missing-arrow", b"module M; void F() { let f = Fn(T x) -> T x; }", "syntax"),
    ("typed-lambda-missing-body", b"module M; void F() { let f = FnOnce(T x) -> T =>; }", "syntax"),
    ("typed-lambda-missing-local-region", b"module M; void F() { let f = Fn<region>(T x) -> T => x; }", "syntax"),
    ("typed-lambda-incomplete-law", b"module M; void F() { let f = Fn(T x) -> T with { restores; } => x; }", "syntax"),
    ("typed-lambda-undelimited-law", b"module M; void F() { let f = Fn(T x) -> T requires Valid(x) => x; }", "syntax"),
    ("sum-missing-law", b"module M; union Result<T> where { Ok(T value); }", "syntax"),
    ("constructor-missing-law", b"module M; union Result { Ok() : Result ensures; }", "syntax"),
    ("constructor-result-after-law", b"module M; union Result { Ok() ensures Ready() : Result; }", "syntax"),
    ("definition-missing-law", b"module M; definition Nat F() requires => 0;", "syntax"),
    ("predicate-missing-law", b"module M; predicate P(Nat n) where = true;", "syntax"),
    ("literal-generic-missing-neighbor", b"module M; alias A = Indexed<true,,>;", "syntax"),
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
    ("missing-match-motive-binder", b"module M; public Nat F() { return match (x) as : Nat { _ => 0, }; }", "syntax"),
    ("missing-match-motive-colon", b"module M; public Nat F() { return match (x) as p Nat { _ => 0, }; }", "syntax"),
    ("missing-match-motive-type", b"module M; public Nat F() { return match (x) as p : { _ => 0, }; }", "syntax"),
    ("empty-expression-match-missing-body", b"module M; public Nat F() { return match (x); }", "syntax"),
    ("expression-match-colon-arm", b"module M; public Nat F() { return match (x) { case _ : 0; }; }", "syntax"),
    ("expression-match-mixed-arms", b"module M; public Nat F() { return match (x) { true => 0, case false : 1; }; }", "syntax"),
    ("expression-match-missing-value", b"module M; public Nat F() { return match (x) { _ => , }; }", "syntax"),
    ("expression-match-missing-comma", b"module M; public Nat F() { return match (x) { true => 0 false => 1 }; }", "syntax"),
    ("match-motive-depth", b"module M; public Nat F() { return match (x) as p : "
     + b"Box<" * 257 + b"Nat" + b">" * 257 + b" { _ => 0, }; }", "limit"),
    ("field-missing-grade", b"module M; struct Box { Nat Value @; }", "syntax"),
    ("field-grade-after-initializer", b"module M; struct Box { Nat Value = 0 @ q; }", "syntax"),
    ("impl-incomplete-telescope", b"module M; impl<T,,> Dup<T> {}", "syntax"),
    ("impl-incomplete-contract", b"module M; impl<T> Dup<T> where {}", "syntax"),
    ("impl-ungrouped-callable", b"module M; impl Fn() -> Nat effects(Read) where Reusable(Read) {}", "syntax"),
    ("callable-incomplete-telescope", b"module M; alias F = Fn<region>() -> Nat;", "syntax"),
    ("callable-incomplete-law-block", b"module M; alias F = Fn() -> Nat with { requires Ready() };", "syntax"),
    ("callable-law-without-delimiter", b"module M; alias F = Fn() -> Nat with requires Ready();", "syntax"),
    ("incomplete-callable-binder", b"module M; alias F = Fn(Nat n,, ) -> Nat;", "syntax"),
    ("incomplete-callable-grade", b"module M; alias F = Fn(Nat n @) -> Nat;", "syntax"),
    ("incomplete-lambda-grade", b"module M; public void F() { let f = (Nat n @) => n; }", "syntax"),
    ("incomplete-generic-alias", b"module M; alias F<T,,> = T;", "syntax"),
    ("singleton-product-type", b"module M; alias P = (Nat,);", "syntax"),
    ("singleton-product-value", b"module M; public void F() { let p = (1,); }", "syntax"),
    ("singleton-product-pattern", b"module M; public void F() { let (x,) = p; }", "syntax"),
    ("incomplete-product-binding", b"module M; public void F() { let (x, let) = p; }", "syntax"),
    ("missing-product-value", b"module M; public void F() { let (x, y) = ; }", "syntax"),
    ("product-type-depth", b"module M; alias P = " + b"(Nat," * 257
     + b"Nat" + b")" * 257 + b";", "limit"),
    ("product-pattern-depth", b"module M; public void F() { match (p) { case "
     + b"(x," * 257 + b"()" + b")" * 257 + b": return; } }", "limit"),
    ("graded-lambda-lookahead-depth", b"module M; public void F() { let f = (Nat n @ "
     + b"(" * 257 + b"q" + b")" * 257 + b") => n; }", "limit"),
    ("grade-callback-block-lookahead-depth", b"module M; public void F() { let f = (Nat x @ Grade.Of((Nat n) => "
     + b"{" * 257 + b"return n;" + b"}" * 257 + b")) => x; }", "limit"),
    ("grouped-type-lookahead-depth", b"module M; public void F() { "
     + b"(" * 257 + b"Nat" + b")" * 257 + b" local = value; }", "limit"),
    ("missing-generic-argument", b"module M; public Result<Packet,,> Parse();", "syntax"),
    ("incomplete-record", b"module M; public record Packet(Nat Count", "syntax"),
    ("incomplete-handler", b"module M; public Nat F() { return handle (G()) { return x =>", "syntax"),
    ("missing-effect-result", b"module M; public effect E { Choose() resumes(1); }", "syntax"),
    ("missing-match-colon", b"module M; public void F() { match (x) { case Ok(x) return; } }", "syntax"),
    ("incomplete-cancel", b"module M; public async Nat F() { return 0; } on cancel", "syntax"),
    ("unterminated-string", b'module M; public void F() { let text = "unterminated', "syntax"),
    ("unterminated-raw-string", b'module M; public void F() { let text = """unterminated ""; }', "syntax"),
    ("raw-string-excess-closing-quotes", b'module M; public void F() { let text = """raw""""; }', "syntax"),
    ("raw-string-opening-line-text", b'module M; public void F() { let text = """text\n"""; }', "syntax"),
    ("raw-string-closing-not-own-line", b'module M; public void F() { let text = """\n  text """; }', "syntax"),
    ("raw-string-underindented-content", b'module M; public void F() { let text = """\n  short\n    """; }', "syntax"),
    ("unterminated-interpolated-string", b'module M; public void F() { Format.Write(ref b, $"unterminated); }', "syntax"),
    ("interpolated-empty-hole", b'module M; public void F() { Format.Write(ref b, $"empty {}"); }', "syntax"),
    ("interpolated-whitespace-hole", b'module M; public void F() { Format.Write(ref b, $"empty {   }"); }', "syntax"),
    ("interpolated-empty-specifier", b'module M; public void F() { Format.Write(ref b, $"spec {x:}"); }', "syntax"),
    ("interpolated-whitespace-specifier", b'module M; public void F() { Format.Write(ref b, $"spec {x: x2}"); }', "syntax"),
    ("interpolated-unescaped-close-brace", b'module M; public void F() { Format.Write(ref b, $"bad }"); }', "syntax"),
    ("interpolated-unclosed-hole", b'module M; public void F() { Format.Write(ref b, $"bad {x"); }', "syntax"),
    ("interpolated-pattern-disallowed", b'module M; public void F() { match (x) { case $"bad {y}": return; } }', "syntax"),
    ("interpolated-hole-delimiter-limit", b'module M; public void F() { Format.Write(ref b, $"{'
     + b"(" * 256 + b"x" + b")" * 256 + b'}"); }', "limit"),
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
    # Payload-role oracles inspect expressions; _argument_roles independently
    # validates every located wrapper before these assertions run.
    if value.get("kind") == "argument":
        return _object(value.get("value"), description)
    return value


def _argument_roles(source: bytes, result: dict[str, Json]) -> None:
    """Independently bind each call's labels, payloads and delimiters to bytes."""
    for call in nodes(result.get("ast")):
        if call.get("kind") != "call":
            continue
        arguments = _sequence(call.get("arguments"), "located call arguments")
        raw_callee = call.get("callee")
        if not isinstance(raw_callee, dict):
            raise TypeError("surface call has no callee")
        callee_span = _sequence(raw_callee.get("span"), "callee span")
        call_span = _sequence(call.get("span"), "call span")
        cursor = trivia_end(source, cast("int", callee_span[1]), block_comments=True)
        if source[cursor:cursor + 1] != b"(":
            raise ValueError("surface call opening differs from source")
        cursor = trivia_end(source, cursor + 1, block_comments=True)
        for index, raw in enumerate(arguments):
            if not isinstance(raw, dict) or set(raw) != {"kind", "span", "label", "value"} or raw.get("kind") != "argument":
                raise ValueError("surface call argument lost its located label/value role")
            span = _sequence(raw.get("span"), "argument span")
            value = raw.get("value")
            if not isinstance(value, dict):
                raise TypeError("surface argument has no value")
            value_span = _sequence(value.get("span"), "argument value span")
            if span[0] != cursor or span[1] != value_span[1]:
                raise ValueError("surface call leaves argument bytes uncovered")
            label = raw.get("label")
            if label is None:
                if span != value_span:
                    raise ValueError("surface positional argument span differs")
            else:
                if not isinstance(label, dict) or set(label) != {"text", "span"}:
                    raise ValueError("surface argument label lost its name role")
                label_span = _sequence(label.get("span"), "argument label span")
                if (label_span[0] != span[0]
                        or source[cast("int", label_span[0]):cast("int", label_span[1])].decode() != label.get("text")):
                    raise ValueError("surface argument label differs from source")
                colon = trivia_end(source, cast("int", label_span[1]), block_comments=True)
                if (source[colon:colon + 1] != b":"
                        or trivia_end(source, colon + 1, block_comments=True) != value_span[0]):
                    raise ValueError("surface argument label delimiter differs")
            cursor = trivia_end(source, cast("int", span[1]), block_comments=True)
            if index < len(arguments) - 1:
                if source[cursor:cursor + 1] != b",":
                    raise ValueError("surface call argument separator differs")
                cursor = trivia_end(source, cursor + 1, block_comments=True)
        if arguments and source[cursor:cursor + 1] == b",":
            cursor = trivia_end(source, cursor + 1, block_comments=True)
        if source[cursor:cursor + 1] != b")" or cursor != cast("int", call_span[1]) - 1:
            raise ValueError("surface call closing differs or leaves uncovered arguments")


def _readable_call_roles(result: dict[str, Json]) -> None:
    calls = [node for node in nodes(result.get("ast")) if node.get("kind") == "call"]
    transfer = next(node for node in calls if _texts(node.get("callee")) == ["Transfer"])
    arguments = _sequence(transfer.get("arguments"), "explicit loan arguments")
    if len(arguments) != 4:
        raise ValueError("surface labeled transfer changed its arity")
    for raw, label, mode in zip(arguments, ("input", "target", "output", "owner"), ("in", "ref", "out", "move"), strict=True):
        if not isinstance(raw, dict) or _texts(raw.get("label")) != [label]:
            raise ValueError("surface argument label changed resolved-slot spelling")
        value = _object(raw.get("value"), "loan argument")
        if value.get("kind") != "unary" or _texts(value.get("operator")) != [mode]:
            raise ValueError("surface argument label removed its explicit loan/transfer mode")
    loops = [node for node in nodes(result.get("ast")) if node.get("kind") == "foreach"]
    if len(loops) != 1 or _texts(loops[0].get("name")) != ["index"]:
        raise ValueError("surface bounded foreach lost its immutable binder")
    exits = {node.get("kind") for node in nodes(loops[0])}
    if not {"break", "continue", "return", "contract", "assignment"} <= exits:
        raise ValueError("surface foreach lost a loan/contract exit role")


def _compositional_constant_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = _object(result.get("ast"), "constant callable root")
    for name, modifiers in (("Square", ["public", "const"]), ("Scale", ["public"]),
                            ("Hidden", ["const", "internal"]), ("Select", ["public", "const"])):
        function = _named(tree, "function", name)
        if function.get("modifiers") != modifiers or "const" in function:
            raise ValueError("constant function qualifier changed its declaration role")
    for owner_kind, owner_name, parameter_kind, name, spelling in (
            ("function", "Scale", "parameter", "factor", b"const Nat factor"),
            ("alias", "StaticMap", "parameter", "dimension", b"const Nat dimension"),
            ("definition", "Build", "lambda_parameter", "coefficient", b"const Nat coefficient"),
            ("definition", "Explicit", "parameter", "axis", b"const Nat axis"),
            ("function", "Select", "parameter", "selector", b"const Nat selector")):
        parameter = _named(_named(tree, owner_kind, owner_name), parameter_kind, name)
        if parameter.get("const") is not True or parameter.get("grade") is not None:
            raise ValueError("required-static parameter lost its Boolean qualifier or acquired a grade")
        _exact_span(source, parameter, spelling)
        annotation = _object(parameter.get("type"), "static parameter annotation")
        start = source.index(spelling) + len(b"const ")
        if annotation.get("span") != [start, start + len(b"Nat")]:
            raise ValueError("const entered the parameter type rather than qualifying the binder")
    for name in ("value", "item", "element", "entry"):
        for parameter in nodes(tree):
            if (parameter.get("kind") in {"parameter", "lambda_parameter"}
                    and _texts(parameter.get("name")) == [name] and "const" in parameter):
                raise ValueError("ordinary parameter acquired a required-static qualifier")
    local = _named(tree, "constant_local", "multiplier")
    if _object(local.get("value"), "static initializer").get("kind") != "call":
        raise ValueError("syntax parser evaluated a symbolic constant initializer")


def _required_static_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = _object(result.get("ast"), "constant declaration root")
    declarations = _sequence(tree.get("declarations"), "ordered declarations")
    if [_texts(_object(value, "declaration").get("name")) for value in declarations] != [["Square"], ["Limit"], ["Ready"], ["Bounds"]]:
        raise ValueError("surface constants changed authored declaration order")
    for name, kind, spelling, annotation in (
            ("Limit", "constant", b"public const Nat Limit = Square(value: 4);", "Nat"),
            ("Ready", "constant", b"public const bool Ready = Limit == 16;", "bool"),
            ("Capacity", "constant", b"public const usize Capacity = 8usize;", "usize"),
            ("Doubled", "constant", b"private const Nat Doubled = Limit + Limit;", "Nat"),
            ("Local", "constant_local", b"const Nat Local = Limit + 1;", "Nat")):
        declaration = _named(tree, kind, name)
        _exact_span(source, declaration, spelling)
        _type_head(declaration.get("type"), annotation, 0)
        expected = {"kind", "span", "name", "type", "value"}
        if kind == "constant":
            expected.add("modifiers")
            if declaration.get("modifiers") != ["private" if name == "Doubled" else "public"]:
                raise ValueError("surface constant lost its source visibility")
        if set(declaration) != expected:
            raise ValueError("surface constant acquired unexpected callable/grade fields")
    initializer = _object(_named(tree, "constant", "Limit").get("value"), "unreduced initializer")
    if initializer.get("kind") != "call" or _texts(initializer.get("callee")) != ["Square"]:
        raise ValueError("surface parser evaluated a required-static initializer")
    invalid = _named(tree, "constant_local", "Invalid")
    if _object(invalid.get("value"), "runtime initializer").get("kind") != "name":
        raise ValueError("surface parser hid a runtime constant dependency")
    erased = _object(_named(tree, "constant_local", "Erased").get("type"), "erased constant annotation")
    if erased.get("kind") != "modified_type" or erased.get("modifier") != "ghost":
        raise ValueError("surface constant erased its unsupported phase annotation")


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


def _explicit_shape(value: Json) -> Json:
    expression = _object(value, "explicit value expression")
    kind = expression.get("kind")
    if kind == "name":
        return _object(expression.get("name"), "value name").get("text")
    if kind == "nat":
        return ["nat", expression.get("value"), expression.get("suffix")]
    if kind in {"unary", "binary"}:
        symbol = _object(expression.get("operator"), "value operator").get("text")
        if kind == "unary":
            return ["unary", symbol, _explicit_shape(expression.get("value"))]
        return ["binary", symbol, _explicit_shape(expression.get("left")),
                _explicit_shape(expression.get("right"))]
    if kind in {"group", "propagate"}:
        return [kind, _explicit_shape(expression.get("value"))]
    if kind == "index":
        return ["index", _explicit_shape(expression.get("value")), _explicit_shape(expression.get("index"))]
    if kind == "member":
        return ["member", _explicit_shape(expression.get("value")),
                _object(expression.get("name"), "member name").get("text")]
    if kind == "call":
        return ["call", _explicit_shape(expression.get("callee")),
                [_explicit_shape(argument) for argument in _sequence(expression.get("arguments"), "arguments")]]
    if kind == "operator":
        return ["operator", _object(expression.get("name"), "operator name").get("text")]
    raise ValueError(f"unexpected explicit-value AST role: {kind}")


def _binder_initializer_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    family = _named(tree, "alias", "Family")
    generics = _sequence(family.get("generics"), "shared generic telescope")
    expected = (("type", "T", b"T : Type<u>", "Type", 1),
                ("type", "U", b"U", None, 0),
                ("ghost", "extent", b"ghost Nat extent", "Nat", 0),
                ("region", "'scope", b"region 'scope", None, 0),
                ("effect", "E", b"effect E", None, 0),
                ("captures", "C", b"captures C", None, 0),
                ("grade", "q", b"grade q : NatExact", "NatExact", 0))
    if len(generics) != len(expected):
        raise ValueError("surface generic modes lost a binder or fabricated a helper")
    for raw, (mode, name, spelling, head, arity) in zip(generics, expected, strict=True):
        binder = _object(raw, "shared generic binder")
        if (set(binder) != {"kind", "span", "mode", "name", "type"}
                or binder.get("kind") != "generic_parameter" or binder.get("mode") != mode
                or _texts(binder.get("name")) != [name]):
            raise ValueError("surface generic binder lost its mode/name/type roles")
        _exact_span(source, binder, spelling)
        first = source.index(spelling) + spelling.index(name.encode())
        if _object(binder.get("name"), "generic name").get("span") != [first, first + len(name)]:
            raise ValueError("surface generic name lost its original-byte span")
        if head is None:
            if binder.get("type") is not None:
                raise ValueError("surface untyped generic fabricated a type")
        else:
            _type_head(binder.get("type"), head, arity)
    callable_type = _object(family.get("type"), "shared callable type")
    nested = _sequence(callable_type.get("generics"), "callable generic telescope")
    if [(_object(value, "callable binder").get("mode"), _texts(value)) for value in nested] != [
            ("region", ["'call"]), ("grade", ["uses", "NatExact"])]:
        raise ValueError("surface nested callable changed its generic modes")
    for raw, spelling in zip(nested, (b"region 'call", b"grade uses : NatExact"), strict=True):
        _exact_span(source, _object(raw, "callable binder"), spelling)
    if _texts(callable_type.get("captures")) != ["C"] or _texts(callable_type.get("effects")) != ["E"]:
        raise ValueError("surface generic modes conflated captures and effects")
    _contract_roles(callable_type, ["requires"])
    function = _named(tree, "function", "Bind")
    for kind, name, spelling, initializer in (
            ("typed_local", "direct", b"Vec<T, n> direct @ NatExact(n) = input;", "input"),
            ("let", "immutable", b"let scoped in<'input> Vec<T, n> immutable @ allowance = input;", "input"),
            ("var", "mutable", b"var Vec<T, n> mutable @ allowance = direct;", "direct")):
        local = _named(function, kind, name)
        _exact_span(source, local, spelling)
        if _texts(local.get("value")) != [initializer]:
            raise ValueError("surface typed initializer changed its value")
        annotation = _object(local.get("type"), "typed initializer annotation")
        if name == "immutable":
            loan = _object(annotation.get("type"), "scoped initializer loan")
            if (annotation.get("modifier") != "scoped" or loan.get("modifier") != "in"
                    or _texts(loan.get("lifetime")) != ["'input"]):
                raise ValueError("surface typed initializer changed its loan ancestry")
            annotation = _object(loan.get("type"), "initializer base type")
        arguments = _type_head(annotation, "Vec", 2)
        if [_texts(value) for value in arguments] != [["T"], ["n"]]:
            raise ValueError("surface typed initializer changed its dependent indices")
        if name != "direct" and _texts(local.get("grade")) != ["allowance"]:
            raise ValueError("surface typed initializer changed its allowance")
    direct_grade = _object(_named(function, "typed_local", "direct").get("grade"), "direct allowance")
    _exact_span(source, direct_grade, b"NatExact(n)")
    for local_name, bound, spelling, graded in (
            ("computed", "chosen", b"let Vec<T, n> chosen @ allowance = direct", True),
            ("ungraded", "plain", b"let Vec<T, n> plain = direct", False)):
        expression = _object(_named(function, "let", local_name).get("value"), "initializer expression")
        binding = _object(expression.get("binding"), "expression-owned initializer")
        if (expression.get("kind") != "let_expression" or binding.get("kind") != "let"
                or _texts(binding.get("name")) != [bound] or _texts(expression.get("body")) != [bound]
                or _texts(binding.get("value")) != ["direct"]):
            raise ValueError("surface expression initializer lost its binding/body roles")
        _exact_span(source, binding, spelling)
        _exact_span(source, expression, spelling + b" in " + bound.encode())
        _type_head(binding.get("type"), "Vec", 2)
        grade = binding.get("grade")
        if (graded and _texts(grade) != ["allowance"]) or (not graded and grade is not None):
            raise ValueError("surface expression initializer fabricated or lost its grade")
    if _named(function, "let", "inferred").get("type") is not None:
        raise ValueError("surface inferred initializer acquired an annotation")
    pattern = next(node for node in nodes(function) if node.get("kind") == "let_pattern")
    if "grade" in pattern or "type" in pattern:
        raise ValueError("surface pattern initializer acquired whole-pattern type/grade fields")


def _binder_initializer_error_roles(result: dict[str, Json]) -> None:
    tree = result.get("ast")
    bad = _named(tree, "alias", "Bad")
    generics = [_object(value, "invalid generic") for value in _sequence(bad.get("generics"), "invalid telescope")]
    if ([_texts(value.get("name")) for value in generics[:2]] != [["duplicate"], ["duplicate"]]
            or [value.get("mode") for value in generics[:2]] != ["ghost", "effect"]):
        raise ValueError("surface syntax repaired duplicate names across generic modes")
    _type_head(generics[-1].get("type"), "UnknownDomain", 0)
    function = _named(tree, "function", "Invalid")
    for kind, name in (("typed_local", "shared"), ("let", "copied")):
        value = _object(_named(function, kind, name).get("value"), "duplicate owner initializer")
        if value.get("kind") != "unary" or _texts(value.get("operator")) != ["move"] or _texts(value.get("value")) != ["owner"]:
            raise ValueError("surface syntax repaired repeated owner consumption")
    repeated = _named(function, "var", "repeated")
    if _object(repeated.get("type"), "repeated callable type").get("mode") != "FnOnce":
        raise ValueError("surface syntax repaired an invalid repeated callable allowance")
    runtime = _named(function, "let", "runtime")
    if (_object(runtime.get("type"), "erased runtime type").get("modifier") != "ghost"
            or _texts(_object(runtime.get("value"), "effectful erased initializer").get("callee")) != ["Read"]):
        raise ValueError("surface syntax erased an effectful initializer or repaired its phase")


def _explicit_value_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    function = _named(tree, "function", "Modes")
    parameters = _sequence(function.get("parameters"), "explicit-mode parameters")
    expected = (("value", None, "Nat"), ("read", "in", "Nat"),
                ("write", "ref", "Nat"), ("output", "out", "Nat"), ("packet", "owned", "Packet"))
    if len(parameters) != len(expected):
        raise ValueError("surface explicit parameter modes lost their arity")
    for raw, (name, mode, head) in zip(parameters, expected, strict=True):
        parameter = _object(raw, "explicit-mode parameter")
        annotation = _object(parameter.get("type"), "explicit-mode type")
        if _texts(parameter.get("name")) != [name]:
            raise ValueError("surface explicit parameter names changed")
        if mode is not None:
            if annotation.get("kind") != "modified_type" or annotation.get("modifier") != mode:
                raise ValueError("surface parameter mode was inferred, lost or changed")
            if mode == "out":
                if _texts(annotation.get("lifetime")) != ["'slot"]:
                    raise ValueError("surface out parameter lost its named lifetime")
                start = source.index(b"out<'slot> Nat output")
                if annotation.get("span") != [start, start + len(b"out<'slot> Nat")]:
                    raise ValueError("surface out parameter original-byte span differs")
            annotation = _object(annotation.get("type"), "underlying parameter type")
        _type_head(annotation, head, 0)
    for kind, name, spelling in (("let", "frozen", b"let frozen = value;"),
                                 ("typed_local", "defaultFrozen", b"Nat defaultFrozen = value;"),
                                 ("var", "mutable", b"var mutable = value;")):
        binding = _named(tree, kind, name)
        _exact_span(source, binding, spelling)
        if _explicit_shape(binding.get("value")) != "value":
            raise ValueError("surface default mutability changed its initializer")
    annotated = _object(_named(tree, "let", "annotatedOutput").get("type"), "out local annotation")
    start = source.index(b"out<'slot> Nat annotatedOutput")
    if annotated.get("span") != [start, start + len(b"out<'slot> Nat")]:
        raise ValueError("surface out local original-byte span differs")
    if annotated.get("modifier") != "out" or _texts(annotated.get("lifetime")) != ["'slot"]:
        raise ValueError("surface local out modifier/lifetime differs from parameter syntax")
    callback = _object(_named(tree, "let", "callback").get("value"), "out callback")
    parameter = _object(_sequence(callback.get("parameters"), "out callback parameters")[0], "out callback parameter")
    callback_type = _object(parameter.get("type"), "out callback type")
    if callback_type.get("modifier") != "out" or _texts(parameter.get("name")) != ["destination"]:
        raise ValueError("surface callback lost explicit out mode")
    initializer = _object(_named(tree, "alias", "Initializer").get("type"), "initializer callable")
    argument = _object(_sequence(initializer.get("parameters"), "initializer parameters")[0], "initializer parameter")
    if _object(argument.get("type"), "initializer out type").get("modifier") != "out":
        raise ValueError("surface callable type lost out mode")
    calls = [node for node in nodes(function) if node.get("kind") == "call"
             and _texts(node.get("callee")) == ["Apply"]]
    expected_call: Json = ["call", "Apply", ["value", ["unary", "in", "read"],
        ["unary", "ref", "write"], ["unary", "out", "output"], ["unary", "move", "packet"]]]
    if len(calls) != 1 or _explicit_shape(calls[0]) != expected_call:
        raise ValueError("surface call-site modes were lost or inserted")
    for symbol, spelling in (("in", b"in read"), ("ref", b"ref write"),
                             ("out", b"out output"), ("move", b"move packet")):
        unary = next(node for node in nodes(calls[0]) if node.get("kind") == "unary"
                     and _texts(node.get("operator")) == [symbol])
        _exact_span(source, unary, spelling)
        start = source.index(spelling)
        if _object(unary.get("operator"), "call-site keyword span").get("span") != [start, start + len(symbol)]:
            raise ValueError("surface call-site keyword original-byte span differs")
    consume = _named(tree, "definition", "Consume")
    parameter = _object(_sequence(consume.get("parameters"), "option parameters")[0], "option parameter")
    _type_head(_type_head(_type_head(parameter.get("type"), "Option", 1)[0], "Option", 1)[0], "Nat", 0)
    match = _object(consume.get("value"), "option match")
    cases = _sequence(match.get("cases"), "option cases")
    patterns: list[Json] = [
        ["constructor", "Some", [["constructor", "Some", [["bind", "n"]]]]],
        ["constructor", "Some", [["constructor", "None", []]]], ["constructor", "None", []],
    ]
    if match.get("kind") != "match_expression" or len(cases) != len(patterns):
        raise ValueError("surface option elimination lost a tagged branch")
    for raw, expected_pattern, spelling in zip(cases, patterns,
            (b"Some(Some(n))", b"Some(None())", b"None()"), strict=True):
        pattern = _object(_object(raw, "option case").get("pattern"), "option pattern")
        if _recursive_pattern_shape(pattern) != expected_pattern:
            raise ValueError("surface nested option cases were flattened or changed")
        start = source.index(spelling + b" =>")
        if pattern.get("span") != [start, start + len(spelling)]:
            raise ValueError("surface nested option pattern original-byte span differs")
    for name, shape in (("present", ["call", "Some", [["call", "Some", ["value"]]]]),
                        ("absent", ["call", "None", []]),
                        ("propagated", ["propagate", ["call", "ReadOption", []]])):
        if _explicit_shape(_named(tree, "let", name).get("value")) != shape:
            raise ValueError("surface option construction/propagation acquired an implicit operation")
    hole = _object(_named(tree, "let", "hole").get("value"), "named proof hole")
    _exact_span(source, hole, b"?proof")
    if hole.get("kind") != "hole":
        raise ValueError("surface named hole became optional syntax")


def _explicit_error_roles(result: dict[str, Json]) -> None:
    tree = result.get("ast")
    for name, shape in (("narrow", ["nat", "300", "u64"]),
                        ("mixed", ["binary", "+", ["nat", "1", "u8"], ["nat", "2", "u64"]]),
                        ("truthy", ["nat", "1", ""]), ("lifted", ["nat", "1", ""]),
                        ("extracted", ["call", "Some", [["nat", "1", ""]]]),
                        ("invalidAddress", ["unary", "&", ["nat", "1", ""]]),
                        ("invalidRead", ["unary", "*", ["nat", "1", ""]])):
        if _explicit_shape(_named(tree, "let", name).get("value")) != shape:
            raise ValueError("surface semantic-error fixture acquired a conversion or permission repair")
    calls = [node for node in nodes(tree) if node.get("kind") == "call"
             and _texts(node.get("callee")) == ["Apply"]]
    expected: list[Json] = [
        ["call", "Apply", ["shared", "exclusive", "output", "packet"]],
        ["call", "Apply", [["unary", "ref", "shared"], ["unary", "in", "exclusive"],
            ["unary", "ref", "output"], ["unary", "move", "packet"]]],
    ]
    if [_explicit_shape(call) for call in calls] != expected:
        raise ValueError("surface missing/mismatched call modes were repaired or rejected")
    partial = _object(_named(tree, "definition", "Partial").get("value"), "partial option elimination")
    cases = _sequence(partial.get("cases"), "partial option cases")
    if len(cases) != 1 or _recursive_pattern_shape(_object(cases[0], "partial case").get("pattern")) != [
            "constructor", "Some", [["bind", "value"]]]:
        raise ValueError("surface partial option match was completed or changed")
    assignments = [node for node in nodes(tree) if node.get("kind") == "assignment"]
    if [_explicit_shape(node.get("target")) for node in assignments] != ["frozen", "alsoFrozen", "shared"]:
        raise ValueError("surface immutable/shared assignments lost their source obligations")


def _propagation_member_role(result: dict[str, Json]) -> None:
    value = _named(result.get("ast"), "let", "result").get("value")
    if _explicit_shape(value) != ["member", ["group", ["propagate", ["call", "Read", []]]], "Value"]:
        raise ValueError("surface explicit propagation/member grouping differs")


def _pointer_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    indexed: Json = ["index", "p", "i"]
    dereferenced: Json = ["unary", "*", "p"]
    expected: tuple[tuple[str, Json, bytes], ...] = (
        ("address", ["unary", "&", indexed], b"&p[i]"),
        ("read", ["unary", "*", indexed], b"*p[i]"),
        ("nested", ["unary", "*", ["unary", "&", indexed]], b"*&p[i]"),
        ("offset", ["unary", "*", ["group", ["binary", "+", "p", "n"]]], b"*(p + n)"),
        ("advance", ["binary", "+", "p", ["binary", "*", "n", ["nat", "2", ""]]], b"p + n * 2"),
        ("difference", ["binary", "-", "p", "other"], b"p - other"),
        ("arithmetic", ["binary", "&", ["binary", "*", dereferenced, "n"], "mask"], b"*p * n & mask"),
        ("bitwise", ["binary", "&", "flags", dereferenced], b"flags & *p"),
        ("field", ["member", ["group", dereferenced], "Value"], b"(*p).Value"),
        ("multiply", ["operator", "*"], b"(*)"),
        ("conjunction", ["operator", "&"], b"(&)"),
        ("apply", ["call", ["operator", "*"], [["nat", "2", ""], ["nat", "3", ""]]], b"(*)(2, 3)"),
        ("derived", ["call", ["operator", "&"], ["p"]], b"(&)(p)"),
    )
    for name, shape, spelling in expected:
        expression = _object(_named(tree, "let", name).get("value"), "pointer expression")
        if _explicit_shape(expression) != shape:
            raise ValueError(f"surface pointer/operator precedence differs for {name}")
        _exact_span(source, expression, spelling)
    for name, symbol in (("multiply", "*"), ("conjunction", "&")):
        _operator_value(source, _named(tree, "let", name).get("value"), symbol)
    for unary in (node for node in nodes(tree) if node.get("kind") == "unary"):
        symbol = _object(unary.get("operator"), "pointer prefix")
        span = _sequence(unary.get("span"), "pointer prefix expression span")
        if (len(span) != 2 or type(span[0]) is not int
                or symbol.get("span") != [span[0], span[0] + 1]
                or source[span[0]:span[0] + 1] != str(symbol.get("text")).encode()):
            raise ValueError("surface pointer prefix original-byte span differs")
    assignments = [node for node in nodes(tree) if node.get("kind") == "assignment"]
    if len(assignments) != 2 or [_texts(node.get("operator")) for node in assignments] != [["="], ["+="]]:
        raise ValueError("surface dereference assignments lost their operation")
    for assignment in assignments:
        if _explicit_shape(assignment.get("target")) != dereferenced:
            raise ValueError("surface pointer assignment target lost its dereference")


def _callable_list_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    for local, names, spelling in (
            ("noParameters", [], b"() => Zero()"),
            ("oneParameter", ["single"], b"(single) => single"),
            ("manyParameters", ["left", "right"], b"(left, right) => Pair(left, right)"),
            ("trailingParameter", ["last"], b"(last,) => last")):
        value = _object(_named(tree, "let", local).get("value"), "list-boundary lambda")
        parameters = [_object(raw, "list-boundary parameter")
                      for raw in _sequence(value.get("parameters"), "list-boundary parameters")]
        if value.get("kind") != "lambda" or [_texts(item.get("name")) for item in parameters] != [[name] for name in names]:
            raise ValueError("surface lambda list changed its parameter count or order")
        _exact_span(source, value, spelling)
        for parameter, name in zip(parameters, names, strict=True):
            _exact_span(source, parameter, name.encode())
            if (parameter.get("span") != _object(parameter.get("name"), "lambda name").get("span")
                    or parameter.get("type") is not None or parameter.get("grade") is not None):
                raise ValueError("surface inferred parameter includes absent annotations or delimiters")
    for local, kind, shallow, clause_kinds, spelling in (
            ("noClauses", "handle", False, [], b"handle (Empty()) {}"),
            ("oneClause", "handle", False, ["return_clause"], b"handle (Single()) { return item => item }"),
            ("manyClauses", "handle", False, ["operation_clause", "return_clause"],
             b"handle (Multiple()) {\n        Choose(chosen) with k => resume k(chosen), return answer => answer\n    }"),
            ("trailingClause", "rehandle", True, ["return_clause"],
             b"rehandle shallow (Trailing()) { return final => final, }")):
        value = _object(_named(tree, "let", local).get("value"), "list-boundary handler")
        clauses = [_object(raw, "list-boundary clause")
                   for raw in _sequence(value.get("clauses"), "list-boundary clauses")]
        if (value.get("kind") != kind or value.get("shallow") is not shallow
                or [clause.get("kind") for clause in clauses] != clause_kinds):
            raise ValueError("surface handler list changed mode, clause count or order")
        _exact_span(source, value, spelling)
    call = _object(_named(tree, "let", "arguments").get("value"), "nested labeled call")
    arguments = _sequence(call.get("arguments"), "outer call arguments")
    if len(arguments) != 2:
        raise ValueError("surface argument list changed its arity")
    positional, labeled = arguments
    if not isinstance(positional, dict) or not isinstance(labeled, dict):
        raise TypeError("surface fixture lacks outer argument wrappers")
    if positional.get("label") is not None or _texts(labeled.get("label")) != ["label"]:
        raise ValueError("surface argument list changed its positional and labeled roles")
    _exact_span(source, positional, b"Input()")
    _exact_span(source, labeled, b"label: Nested(inner: value,)")
    nested = _object(labeled.get("value"), "nested labeled argument value")
    nested_arguments = _sequence(nested.get("arguments"), "nested arguments")
    if nested.get("kind") != "call" or len(nested_arguments) != 1:
        raise ValueError("surface nested trailing comma changed its arity")
    inner = nested_arguments[0]
    if not isinstance(inner, dict) or _texts(inner.get("label")) != ["inner"]:
        raise ValueError("surface nested trailing comma changed its labeled argument")
    _exact_span(source, inner, b"inner: value")


def _concise_authoring_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    increment = _named(tree, "function", "Increment")
    body = _object(increment.get("body"), "concise function body")
    if set(body) != {"kind", "span", "value"} or body.get("kind") != "expression_body":
        raise ValueError("surface expression body fabricated a block or lost its value")
    _exact_span(source, body, b"=> value + 1;")
    if _explicit_shape(body.get("value")) != ["binary", "+", "value", ["nat", "1", ""]]:
        raise ValueError("surface expression body changed its arithmetic or evaluation")
    checked = _named(tree, "function", "Checked")
    clauses = [_object(item, "checked contract") for item in _sequence(checked.get("contracts"), "checked contracts")]
    if [item.get("role", item.get("kind")) for item in clauses] != ["requires", "ensures", "effects"]:
        raise ValueError("surface concise function lost its contract ownership")
    effect = _object(_sequence(clauses[-1].get("values"), "effect values")[0], "effect call")
    callback = _object(_sequence(effect.get("arguments"), "effect arguments")[0], "effect callback")
    if callback.get("kind") != "lambda" or _texts(callback.get("body")) != ["item"]:
        raise ValueError("surface body arrow swallowed the nested effect-expression lambda")
    _exact_span(source, _object(checked.get("body"), "checked body"), b"=> Increment(value,);")
    grouped = _named(tree, "function", "Grouped")
    for clause, expected in zip(_contract_roles(grouped, ["requires", "ensures"]),
                                ("let_expression", "quantifier"), strict=True):
        group = _object(clause.get("value"), "full-form contract grouping")
        if group.get("kind") != "group" or _object(group.get("value"), "full-form contract").get("kind") != expected:
            raise ValueError("surface contract root lost its explicit full-expression grouping")
    built = _named(tree, "function", "Build")
    condition = _contract_roles(built, ["requires"])[0]
    if _object(condition.get("value"), "grouped name contract").get("kind") != "group":
        raise ValueError("surface grouped predicate became a lambda telescope")
    if _object(_object(built.get("body"), "returned lambda body").get("value"), "returned lambda").get("kind") != "lambda":
        raise ValueError("surface returned lambda consumed its enclosing function arrow")
    function = _named(tree, "function", "Use")
    for local, names in (("identity", ["item"]), ("grouped", ["value"]),
                          ("combine", ["left", "right"])):
        value = _object(_named(function, "let", local).get("value"), "inferred callable")
        parameters = _sequence(value.get("parameters"), "inferred telescope")
        if value.get("kind") != "lambda" or [_texts(_object(item, "inferred parameter").get("name")) for item in parameters] != [[name] for name in names]:
            raise ValueError("surface concise lambda lost parameter identities or list boundaries")
        for parameter in parameters:
            item = _object(parameter, "inferred parameter")
            if set(item) != {"kind", "span", "type", "name", "grade"} or item.get("type") is not None or item.get("grade") is not None:
                raise ValueError("surface omitted lambda annotation fabricated a type or grade")
            name = _object(item.get("name"), "inferred parameter name")
            if item.get("span") != name.get("span"):
                raise ValueError("surface inferred lambda binder span covers absent syntax")
    typed = _object(_named(function, "let", "typed").get("value"), "typed callback")
    _type_head(_object(_sequence(typed.get("parameters"), "typed telescope")[0], "typed parameter").get("type"), "Nat", 0)
    graded = _object(_named(function, "let", "graded").get("value"), "graded callback")
    slot = _object(_sequence(graded.get("parameters"), "graded telescope")[0], "graded slot")
    if not _texts(slot.get("grade")) or _object(slot.get("type"), "scoped callback type").get("modifier") != "scoped":
        raise ValueError("surface concise syntax removed explicit callback resource annotations")
    instance = _object(_named(function, "let", "instance").get("value"), "trailing-comma call")
    applied = _object(instance.get("callee"), "trailing-comma generic application")
    if len(_sequence(instance.get("arguments"), "call arguments")) != 1 or len(_sequence(applied.get("arguments"), "generic arguments")) != 1:
        raise ValueError("surface trailing comma fabricated a call or generic argument")
    bindings = [node for node in nodes(function) if node.get("kind") == "binding_pattern"]
    if sorted(_texts(node.get("name"))[0] for node in bindings) != ["fallback", "nested", "owner", "payload", "receipt"]:
        raise ValueError("surface bare pattern names became constructors or lost binding roles")
    for binding in bindings:
        if binding.get("span") != _object(binding.get("name"), "bare pattern binder").get("span"):
            raise ValueError("surface bare pattern binder span includes an absent keyword")
    constructors = [node for node in nodes(function) if node.get("kind") == "constructor_pattern"]
    if sorted(_texts(node.get("name"))[0] for node in constructors) != ["None", "Some", "Some"]:
        raise ValueError("surface explicit constructors became bare pattern binders")
    nullary = next(node for node in constructors if _texts(node.get("name")) == ["None"])
    nullary_start = source.index(b"case None()") + len(b"case ")
    if nullary.get("span") != [nullary_start, nullary_start + len(b"None()")]:
        raise ValueError("surface nullary constructor span differs from its match arm")
    if _sequence(nullary.get("arguments"), "nullary constructor"):
        raise ValueError("surface nullary constructor fabricated an argument")
    operator_contract = _contract_roles(_named(tree, "function", "OperatorContract"), ["requires"])[0]
    operator = _object(operator_contract.get("value"), "operator-valued contract")
    if operator.get("kind") != "operator" or _texts(operator.get("name")) != ["+"]:
        raise ValueError("surface body arrow changed its preceding operator value")
    _exact_span(source, operator, b"(+)")
    resumed = _object(_contract_roles(_named(tree, "function", "ResumeContract"), ["requires"])[0].get("value"), "resumption contract")
    if resumed.get("kind") != "resume" or _texts(resumed.get("continuation")) != ["k"] or _texts(resumed.get("value")) != ["value"]:
        raise ValueError("surface body arrow changed its preceding resumption expression")
    _exact_span(source, resumed, b"resume k(value)")
    structural = _named(tree, "function", "StructuralPatterns")
    eliminated = _object(_named(structural, "let", "eliminated").get("value"), "structural expression match")
    patterns = [_object(_object(arm, "structural match arm").get("pattern"), "structural arm pattern")
                for arm in _sequence(eliminated.get("cases"), "structural match arms")]
    expected_patterns: list[Json] = [
        "unit_pattern", ["tuple", [["bind", "left"], ["bind", "right"]]],
        ["group", ["constructor", "Some", [["bind", "item"]]]],
    ]
    if [_recursive_pattern_shape(pattern) for pattern in patterns] != expected_patterns:
        raise ValueError("surface expression-arm arrows changed structural pattern roles")
    for pattern, spelling in zip(patterns, (b"()", b"(left, right)", b"(Some(item))"), strict=True):
        start = source.index(spelling + b" =>", source.index(b"let eliminated ="))
        if pattern.get("span") != [start, start + len(spelling)]:
            raise ValueError("surface expression-arm structural pattern span differs")
    score = _named(structural, "typed_local", "score")
    signature = _object(score.get("type"), "effectful callable local")
    if signature.get("kind") != "function_type" or _texts(signature.get("effects")) != ["Choose"]:
        raise ValueError("surface effect telescope lost annotation-adjacent parentheses")


def _expression_binding_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    for expression in nodes(tree):
        if expression.get("kind") != "let_expression":
            continue
        binding = _object(expression.get("binding"), "expression-local binding")
        body = _object(expression.get("body"), "expression-local body")
        value = _object(binding.get("value"), "expression-local initializer")
        if binding.get("kind") not in {"let", "let_pattern"}:
            raise ValueError("surface expression binding changed the ordinary local-node role")
        expression_span = _sequence(expression.get("span"), "expression-local span")
        binding_span = _sequence(binding.get("span"), "expression-local binding span")
        body_span = _sequence(body.get("span"), "expression-local body span")
        value_span = _sequence(value.get("span"), "expression-local initializer span")
        if (binding_span[0] != expression_span[0] or binding_span[1] != value_span[1]
                or body_span[1] != expression_span[1]):
            raise ValueError("surface expression binding merged its initializer and body spans")
        first, last = binding_span[1], body_span[0]
        if type(first) is not int or type(last) is not int or source[first:last].strip() != b"in":
            raise ValueError("surface expression binding lost its original-byte delimiter")

    family = _object(_named(tree, "definition", "Family").get("value"), "type-family binding")
    family_binding = _object(family.get("binding"), "type-family local")
    family_body = _object(family.get("body"), "type-family body")
    if (_texts(family_binding.get("name")) != ["chosen"]
            or family_body.get("kind") != "name" or _texts(family_body.get("name")) != ["chosen"]):
        raise ValueError("surface expression binding lost its dependent type computation")
    _exact_span(source, family, b"let chosen = Select::<T>(pair) in chosen")
    _exact_span(source, family_binding, b"let chosen = Select::<T>(pair)")
    shared = _object(_named(tree, "alias", "Shared").get("type"), "computed shared type")
    if shared.get("kind") != "computed_type" or _object(shared.get("value"), "type-local expression").get("kind") != "let_expression":
        raise ValueError("surface computed type lost its local expression")
    injected = _object(_named(tree, "definition", "Inject").get("value"), "injected local expression")
    injection = _object(injected.get("body"), "type reinjection")
    if (injection.get("kind") != "type_expression"
            or _object(injection.get("type"), "reinjected computed type").get("kind") != "computed_type"):
        raise ValueError("surface type-valued local changed its expression/type roles")

    function = _named(tree, "function", "Read")
    for clause in _contract_roles(function, ["requires", "ensures"]):
        group = _object(clause.get("value"), "grouped contract-local expression")
        if group.get("kind") != "group" or _object(group.get("value"), "contract-local expression").get("kind") != "let_expression":
            raise ValueError("surface declaration contract cannot retain a local expression")
    borrowed = _object(_named(function, "let", "result").get("value"), "borrow-local expression")
    borrowed_value = _object(_object(borrowed.get("binding"), "borrow-local binding").get("value"), "borrow initializer")
    if borrowed_value.get("kind") != "unary" or _texts(borrowed_value.get("operator")) != ["in"]:
        raise ValueError("surface binding delimiter consumed the shared-loan prefix")

    annotated = _object(_named(function, "let", "annotated").get("value"), "annotated expression")
    annotated_binding = _object(annotated.get("binding"), "annotated expression binding")
    _type_head(annotated_binding.get("type"), "Nat", 0)
    grade = _object(annotated_binding.get("grade"), "expression binding grade")
    if (grade.get("kind") != "group"
            or _object(grade.get("value"), "grade-local expression").get("kind") != "let_expression"
            or _object(annotated_binding.get("value"), "annotated initializer").get("value") != "7"):
        raise ValueError("surface expression binding displaced its grade or initializer")
    _exact_span(source, annotated_binding, b"let Nat value @ (let demand = 1 in demand) = 7")
    inferred = _object(_named(function, "let", "inferredGraded").get("value"), "inferred graded expression")
    inferred_binding = _object(inferred.get("binding"), "inferred graded binding")
    if inferred_binding.get("type") is not None or _texts(inferred_binding.get("grade")) != ["q"]:
        raise ValueError("surface inferred expression binding lost its grade or acquired a type")

    deconstructed = _object(_named(function, "let", "deconstructed").get("value"), "pattern expression")
    pattern_binding = _object(deconstructed.get("binding"), "pattern expression binding")
    pattern = _object(pattern_binding.get("pattern"), "expression-local constructor pattern")
    components = _sequence(pattern.get("arguments"), "expression-local constructor arguments")
    if (pattern_binding.get("kind") != "let_pattern" or _texts(pattern.get("name")) != ["Ready"]
            or len(components) != 1 or _object(components[0], "constructor product").get("kind") != "tuple_pattern"):
        raise ValueError("surface expression binding lost its recursive constructor/product pattern")
    _exact_span(source, pattern_binding, b"let Ready((owner, receipt)) = Prepare()")
    product = _object(_named(function, "let", "product").get("value"), "product expression")
    product_binding = _object(product.get("binding"), "product expression binding")
    product_pattern = _object(product_binding.get("pattern"), "product expression pattern")
    if (product_binding.get("kind") != "let_pattern" or product_pattern.get("kind") != "tuple_pattern"
            or _texts(product_pattern.get("patterns")) != ["left", "right"]):
        raise ValueError("surface product expression binding changed its pattern role")
    for local_name, role, child in (("grouped", "binary", "left"), ("applied", "call", "callee"),
                                    ("projected", "member", "value")):
        composed = _object(_named(function, "let", local_name).get("value"), "composed local expression")
        group = _object(composed.get(child), "grouped local expression")
        if (composed.get("kind") != role or group.get("kind") != "group"
                or _object(group.get("value"), "grouped binding").get("kind") != "let_expression"):
            raise ValueError("surface local expression lost its operator/postfix grouping")

    callback = _object(_named(function, "let", "callback").get("value"), "binding callback")
    if _object(callback.get("body"), "callback binding body").get("kind") != "let_expression":
        raise ValueError("surface inferred callback lost its local expression")
    returned = next(node for node in nodes(function) if node.get("kind") == "return")
    outer = _object(returned.get("value"), "outer expression binding")
    inner = _object(outer.get("body"), "inner expression binding")
    if (_texts(_object(outer.get("binding"), "outer local").get("name")) != ["outer"]
            or inner.get("kind") != "let_expression"
            or _texts(_object(inner.get("binding"), "inner local").get("name")) != ["inner"]
            or _texts(inner.get("body")) != ["inner"]):
        raise ValueError("surface expression bindings no longer associate to the right")

    shadow = _object(_named(tree, "definition", "Shadow").get("value"), "shadowing expression")
    local = _object(shadow.get("binding"), "shadowing binding")
    binder = _object(local.get("name"), "shadowing binder")
    initializer = _object(_object(local.get("value"), "shadowing initializer").get("name"), "initializer name")
    if (_texts(binder) != ["value"] or _texts(initializer) != ["value"]
            or binder.get("span") == initializer.get("span")):
        raise ValueError("surface shadowing initializer lost its distinct name occurrence")
    typed_callback = _object(_named(tree, "definition", "Callback").get("value"), "typed callback")
    signature = _object(typed_callback.get("signature"), "typed callback signature")
    callback_contract = _contract_roles(signature, ["requires"])[0]
    contract_group = _object(callback_contract.get("value"), "grouped callable contract binding")
    if (contract_group.get("kind") != "group"
            or _object(contract_group.get("value"), "callable contract binding").get("kind") != "let_expression"
            or _object(typed_callback.get("body"), "typed callback binding").get("kind") != "let_expression"):
        raise ValueError("surface callable contract/body lost a local expression")


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
    if _texts(loan.get("type")) != ["this.Tail"]:
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


def _computed_type(source: bytes, value: Json, spelling: bytes, callee: str) -> dict[str, Json]:
    annotation = _object(value, "computed type")
    computation = _object(annotation.get("value"), "computed type's expression")
    if (annotation.get("kind") != "computed_type" or computation.get("kind") != "call"
            or _texts(computation.get("callee")) != [callee]):
        raise ValueError("surface computed type lost its expression or type role")
    _exact_span(source, annotation, spelling)
    _exact_span(source, computation, spelling[len(b"type["):-1])
    return computation


def _computed_type_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    _computed_type(source, _named(tree, "alias", "Selected").get("type"),
                   b"type[ChooseType(choose)]", "ChooseType")
    argument = _type_head(_named(tree, "alias", "Wrapped").get("type"), "Box", 1)[0]
    _computed_type(source, argument, b"type[PayloadType(true)]", "PayloadType")
    reinjected = _object(_named(tree, "definition", "Reinject").get("value"), "type reinjection")
    if reinjected.get("kind") != "type_expression":
        raise ValueError("surface type reinjection conflated expression and type roles")
    _computed_type(source, reinjected.get("type"), b"type[ReifiedType()]", "ReifiedType")
    structural = _object(_named(tree, "alias", "Structural").get("type"), "computed product")
    components = _sequence(structural.get("types"), "computed product components")
    if structural.get("kind") != "tuple_type" or len(components) != 2:
        raise ValueError("surface computed product changed its structural type")
    for value, modifier, callee in zip(components, ("owned", "tracked"), ("OwnerType", "ReceiptType"), strict=True):
        component = _object(value, "modified computed component")
        if component.get("modifier") != modifier:
            raise ValueError("surface computed type displaced its ownership modifier")
        _computed_type(source, component.get("type"), f"type[{callee}()]".encode(), callee)
    conditional = _object(_named(tree, "alias", "Conditional").get("type"), "type-valued match")
    match = _object(conditional.get("value"), "computed match")
    if conditional.get("kind") != "computed_type" or match.get("kind") != "match_expression":
        raise ValueError("surface computed type cannot retain a dependent expression")
    branches = _sequence(match.get("cases"), "computed type branches")
    if len(branches) != 2 or any(_object(_object(value, "computed branch").get("value"),
                                      "computed branch value").get("kind") != "type_expression" for value in branches):
        raise ValueError("surface computed type confused type injection with type application")
    family = _named(tree, "trait", "Family")
    generic = _object(_sequence(family.get("generics"), "computed kind telescope")[0], "computed kind binder")
    _computed_type(source, generic.get("type"), b"type[KindOf()]", "KindOf")
    item = _named(family, "associated_type", "Item")
    _computed_type(source, item.get("kind_annotation"), b"type[UniverseOf(T)]", "UniverseOf")
    _computed_type(source, item.get("definition"), b"type[MemberType(T)]", "MemberType")
    field = _named(_named(tree, "record", "Packed"), "parameter", "Value")
    _computed_type(source, field.get("type"), b"type[FieldType(Enabled)]", "FieldType")
    function = _named(tree, "function", "Select")
    _computed_type(source, function.get("result"), b"type[ResultType(value)]", "ResultType")
    parameter = _named(function.get("parameters"), "parameter", "value")
    _computed_type(source, parameter.get("type"), b"type[InputType()]", "InputType")
    local = _named(function, "typed_local", "local")
    _computed_type(source, local.get("type"), b"type[LocalType(value)]", "LocalType")
    if (_texts(_object(local.get("grade"), "computed local grade").get("callee")) != ["NatExact"]
            or _texts(local.get("value")) != ["value"]):
        raise ValueError("surface computed local merged allowance and initializer")
    mutable = _named(function, "var", "changed")
    _computed_type(source, mutable.get("type"), b"type[MutableType(value)]", "MutableType")
    loan = _named(function, "lambda_parameter", "loan")
    scoped = _object(loan.get("type"), "computed scoped loan")
    exclusive = _object(scoped.get("type"), "computed exclusive loan")
    if (scoped.get("modifier") != "scoped" or exclusive.get("modifier") != "ref"
            or _texts(exclusive.get("lifetime")) != ["'value"] or _texts(loan.get("grade")) != ["q"]):
        raise ValueError("surface computed callback lost its loan and grade roles")
    _computed_type(source, exclusive.get("type"), b"type[LoanType(value)]", "LoanType")
    typed = _object(_named(function, "let", "typed").get("value"), "computed callable value")
    signature = _object(typed.get("signature"), "computed callable signature")
    if typed.get("kind") != "typed_lambda" or _texts(typed.get("body")) != ["selected"]:
        raise ValueError("surface computed callback displaced its body")
    selected = _named(signature.get("parameters"), "parameter", "selected")
    _computed_type(source, selected.get("type"), b"type[CallbackInput()]", "CallbackInput")
    _computed_type(source, signature.get("result"), b"type[OutputType(selected)]", "OutputType")
    _contract_roles(signature, ["restores"])
    boxed = _named(function, "typed_local", "boxed")
    _computed_type(source, _type_head(boxed.get("type"), "Box", 1)[0],
                   b"type[GenericType(value)]", "GenericType")
    choice = _named(function, "typed_local", "choiceBox")
    callback = _object(_named(function, "let", "nestedCallback").get("value"), "nested computed callback")
    parameter = _named(callback.get("parameters"), "lambda_parameter", "item")
    for owner, scrutinee in ((choice, "flag"), (parameter, "callbackFlag")):
        computed = _object(_type_head(owner.get("type"), "Box", 1)[0], "nested computed annotation")
        match = _object(computed.get("value"), "nested annotation match")
        if computed.get("kind") != "computed_type" or match.get("kind") != "match_expression":
            raise ValueError("surface nested computed annotation lost its match")
        _exact_span(source, computed,
                    ("type[match (" + scrutinee + ') { true => type Nat, false => type bool, }]').encode())
    application = next(node for node in nodes(function) if node.get("kind") == "generic_application")
    argument = _sequence(application.get("arguments"), "computed generic application arguments")[0]
    _computed_type(source, argument, b"type[CallType(value)]", "CallType")


def _family_contract_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    borrowed = _named(tree, "alias", "Borrowed")
    clauses = _contract_roles(borrowed, ["where", "requires"])
    for clause, spelling in zip(clauses, (b"where Stable(T)", b"requires Available(T)"), strict=True):
        _exact_span(source, clause, spelling)
    loan = _object(borrowed.get("type"), "constrained alias loan")
    if loan.get("modifier") != "ref" or _texts(loan.get("lifetime")) != ["'r"]:
        raise ValueError("surface alias law displaced its loan lifetime")
    reusable = _named(tree, "alias", "Reusable")
    clauses = [_object(value, "alias contract") for value in _sequence(reusable.get("contracts"), "alias contracts")]
    if [clause.get("role", clause.get("kind")) for clause in clauses] != ["where", "effects"]:
        raise ValueError("surface alias lost its generic law or declaration effect")
    _exact_span(source, clauses[1], b"effects reads(T)")
    callable_type = _object(reusable.get("type"), "constrained callable alias")
    if callable_type.get("kind") != "function_type" or _texts(callable_type.get("effects")) != ["Read"]:
        raise ValueError("surface alias absorbed its callable's effect bound")
    _contract_roles(callable_type, ["requires", "restores"])
    _exact_span(source, _object(_sequence(callable_type.get("contracts"), "callable laws")[1], "callable restoration"),
                b"restores Closed(value)")
    if _named(tree, "alias", "Plain").get("contracts") != []:
        raise ValueError("surface unconstrained alias fabricated laws")
    effect = _named(tree, "effect", "Exchange")
    clauses = [_object(value, "effect family contract")
               for value in _sequence(effect.get("contracts"), "effect family contracts")]
    if [clause.get("role", clause.get("kind")) for clause in clauses] != ["where", "invariant", "effects"]:
        raise ValueError("surface effect family laws leaked into operation contracts")
    for clause, spelling in zip(clauses, (b"where ExchangeLaw(T, q)", b"invariant Closed(this)", b"effects calls(Storage)"), strict=True):
        _exact_span(source, clause, spelling)
    replacement = _named(effect, "effect_operation", "Replace")
    _contract_roles(replacement, ["requires", "ensures", "restores"])
    parameter = _named(replacement.get("parameters"), "parameter", "replacement")
    if _texts(parameter.get("grade")) != ["q"]:
        raise ValueError("surface effect family laws displaced an operation's parameter grade")
    bound = _object(replacement.get("resumes"), "constrained effect resumption allowance")
    _exact_span(source, bound, b"0..1")
    _contract_roles(_named(effect, "effect_operation", "Borrow"), ["requires"])
    plain = _named(tree, "effect", "PlainEffect")
    if plain.get("contracts") != [] or _named(plain, "effect_operation", "Read").get("contracts") != []:
        raise ValueError("surface plain effect family or operation fabricated contracts")


def _literal_pattern_roles(source: bytes, result: dict[str, Json]) -> None:
    patterns = [node for node in nodes(result.get("ast"))
                if node.get("kind") in {"character_pattern", "string_pattern"}]
    expected = (("character_pattern", b"'x'"), ("character_pattern", b"'\\n'"),
                ("string_pattern", b'"ready"'), ("string_pattern", b'"// {\\\"}"'),
                ("string_pattern", b'""'), ("character_pattern", b"'\\\\'"),
                ("character_pattern", b"'('"), ("string_pattern", b'"closed"'))
    if len(patterns) != len(expected):
        raise ValueError("surface literal pattern roles are missing or conflated with expressions")
    for pattern, (kind, spelling) in zip(patterns, expected, strict=True):
        if pattern.get("kind") != kind or pattern.get("value") != spelling.decode("utf-8"):
            raise ValueError("surface literal pattern lost its raw spelling or literal kind")
        _exact_span(source, pattern, spelling)
    classify = _named(result.get("ast"), "definition", "Classify")
    motive = _object(_object(classify.get("value"), "literal match").get("motive"), "literal match motive")
    if _texts(motive.get("name")) != ["token"]:
        raise ValueError("surface literal patterns displaced the dependent motive binder")
    _exact_span(source, motive, b"as token : Nat")
    statement = _named(result.get("ast"), "function", "Inspect")
    cases = _sequence(next(node for node in nodes(statement) if node.get("kind") == "match").get("cases"), "literal statement cases")
    constructor = _object(_object(cases[2], "nested literal case").get("pattern"), "nested constructor pattern")
    nested = _object(_sequence(constructor.get("arguments"), "constructor patterns")[0], "nested product pattern")
    if constructor.get("kind") != "constructor_pattern" or nested.get("kind") != "tuple_pattern":
        raise ValueError("surface literal pattern composition lost its constructor/product roles")


def _empty_elimination_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    if _named(tree, "inductive", "Never").get("constructors") != []:
        raise ValueError("surface empty type fabricated a constructor")
    absurd = _object(_named(tree, "definition", "Absurd").get("value"), "empty value elimination")
    if absurd.get("kind") != "match_expression" or absurd.get("cases") != []:
        raise ValueError("surface empty dependent eliminator became a statement")
    _exact_span(source, absurd, b"match (impossible) as whole : T {}")
    motive = _object(absurd.get("motive"), "empty eliminator motive")
    if _texts(motive.get("name")) != ["whole"] or _texts(motive.get("type")) != ["T"]:
        raise ValueError("surface empty eliminator lost its motive binder or result type")
    family = _object(_named(tree, "alias", "EmptyFamily").get("type"), "computed empty family")
    inner = _object(family.get("value"), "empty type computation")
    if family.get("kind") != "computed_type" or inner.get("kind") != "match_expression" or inner.get("cases") != []:
        raise ValueError("surface computed type lost its empty eliminator")
    _exact_span(source, inner, b"match (empty) as witness : Type<u> {}")
    returned = next(node for node in nodes(_named(tree, "function", "Eliminate")) if node.get("kind") == "return")
    returned_match = _object(returned.get("value"), "returned empty eliminator")
    if returned_match.get("kind") != "match_expression" or returned_match.get("motive") is not None:
        raise ValueError("surface unannotated empty value match acquired a motive")
    _exact_span(source, returned_match, b"match (absent) {}")
    use = _named(tree, "function", "Use")
    nested = _object(_named(use, "let", "nested").get("value"), "empty elimination call")
    grouped = _object(_sequence(nested.get("arguments"), "empty elimination arguments")[0], "grouped empty elimination")
    empty = _object(grouped.get("value"), "nested empty eliminator")
    if grouped.get("kind") != "group" or empty.get("kind") != "match_expression" or empty.get("cases") != []:
        raise ValueError("surface empty value match lost explicit grouping in a call")
    _exact_span(source, grouped, b"(match (missing) {})")
    statement = next(node for node in nodes(use) if node.get("kind") == "match")
    if statement.get("cases") != [] or statement.get("motive") is not None:
        raise ValueError("surface empty statement match changed its role")
    callback = _object(_named(use, "let", "callback").get("value"), "empty elimination callback")
    callback_body = _object(callback.get("body"), "grouped callback elimination")
    _exact_span(source, callback_body, b"(match (denied) as dead : Unit {})")
    body = _object(use.get("body"), "empty elimination statement body")
    statements = [_object(value, "empty elimination statement")
                  for value in _sequence(body.get("statements"), "empty elimination statements")]
    if [value.get("kind") for value in statements] != [
            "let", "let", "match", "expression_statement", "match", "expression_statement",
            "match", "expression_statement", "match", "block", "let"]:
        raise ValueError("surface empty match consumed a following statement")
    for statement, kind in ((statements[3], "match_expression"), (statements[5], "group"), (statements[7], "unary")):
        if _object(statement.get("value"), "empty match statement boundary").get("kind") != kind:
            raise ValueError("surface empty match confused statement and expression continuations")
    combined = _object(_named(use, "let", "combined").get("value"), "grouped empty match arithmetic")
    if combined.get("kind") != "binary" or _object(combined.get("operator"), "empty match operator").get("text") != "+":
        raise ValueError("surface grouped empty match lost its arithmetic")
    call = _object(combined.get("left"), "grouped empty match call")
    member = _object(call.get("callee"), "grouped empty match member")
    group = _object(member.get("value"), "grouped empty match receiver")
    if call.get("kind") != "call" or member.get("kind") != "member" or group.get("kind") != "group":
        raise ValueError("surface grouped empty match lost postfix composition")
    _exact_span(source, group, b"(match (last) {})")


def _local_grade_roles(source: bytes, result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Bind")
    inferred = _named(function, "let", "inferred")
    if inferred.get("type") is not None or _texts(inferred.get("grade")) != ["q"]:
        raise ValueError("surface inferred local lost its separate allowance")
    _exact_span(source, inferred, b"let inferred @ q = Input.Read();")
    grade_start = source.index(b"inferred @ q") + len(b"inferred @ ")
    if _object(inferred.get("grade"), "local grade").get("span") != [grade_start, grade_start + 1]:
        raise ValueError("surface local allowance lost its original-byte span")
    if _texts(_object(inferred.get("value"), "effectful initializer").get("callee")) != ["Input", "Read"]:
        raise ValueError("surface local allowance absorbed its initializer")
    mutable = _named(function, "var", "mutable")
    _exact_span(source, _object(mutable.get("grade"), "mutable allowance"), b"NatExact(2)")
    annotated = _named(function, "let", "annotated")
    _type_head(annotated.get("type"), "byte", 0)
    if _texts(annotated.get("grade")) != ["q"]:
        raise ValueError("surface typed let lost its allowance")
    for kind, name in (("var", "loan"), ("typed_local", "direct")):
        local = _named(function, kind, name)
        scoped = _object(local.get("type"), "scoped local type")
        loan = _object(scoped.get("type"), "exclusive local loan")
        if (scoped.get("modifier") != "scoped" or loan.get("modifier") != "ref"
                or _texts(loan.get("lifetime")) != ["'source"]):
            raise ValueError("surface local grade displaced scoped loan ancestry")
        _type_head(loan.get("type"), "byte", 0)
        if _object(local.get("value"), "borrow initializer").get("kind") != "unary":
            raise ValueError("surface graded loan lost its borrow initializer")
    callback = _named(function, "let", "callback")
    grade = _object(callback.get("grade"), "callback-computed local allowance")
    argument = _object(_sequence(grade.get("arguments"), "allowance arguments")[0], "grade callback")
    initializer = _object(callback.get("value"), "callable initializer")
    if grade.get("kind") != "call" or argument.get("kind") != "typed_lambda" or initializer.get("kind") != "typed_lambda":
        raise ValueError("surface local allowance conflated its callback with the initializer")
    _exact_span(source, grade, b"Grade.Of(Fn(Nat probe) -> Nat => probe)")
    dormant = _named(function, "typed_local", "dormant")
    dormant_grade = _object(dormant.get("grade"), "zero-use allowance")
    zero = _object(_sequence(dormant_grade.get("arguments"), "zero allowance arguments")[0], "zero allowance")
    if zero.get("value") != "0" or _texts(_object(dormant.get("value"), "retained initializer").get("callee")) != ["Effects", "Read"]:
        raise ValueError("surface zero-use local erased or replaced its effectful initializer")
    generic_grade = _object(_named(function, "typed_local", "genericGrade").get("grade"), "generic local allowance")
    if _object(generic_grade.get("callee"), "generic allowance operation").get("kind") != "generic_application":
        raise ValueError("surface local allowance ended at a generic argument comma")
    _exact_span(source, generic_grade, b"Grade.Of::<T, U>()")
    type_grade = _object(_named(function, "typed_local", "typeGrade").get("grade"), "type-valued allowance")
    if type_grade.get("kind") != "type_expression":
        raise ValueError("surface syntax removed a semantically invalid type-valued allowance")
    arguments = _type_head(type_grade.get("type"), "Box", 2)
    _contract_roles(_object(arguments[0], "type-valued allowance callback"), ["requires"])
    _exact_span(source, type_grade, b"type Box<Fn() -> Nat with { requires Ready(); }, U>")
    plain = _named(function, "let", "plain")
    if "grade" not in plain or plain.get("grade") is not None:
        raise ValueError("surface ungraded local fabricated an allowance")
    pattern = next(node for node in nodes(function) if node.get("kind") == "let_pattern")
    if "grade" in pattern:
        raise ValueError("surface product elimination acquired a component allowance")


def _local_grade_error_roles(result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Invalid")
    duplicate = _named(function, "let", "duplicated")
    if _object(duplicate.get("grade"), "invalid exact allowance").get("kind") != "call":
        raise ValueError("surface invalid local lost its explicit allowance")
    moves = [node for node in nodes(function) if node.get("kind") == "unary"
             and _texts(node.get("operator")) == ["move"] and _texts(node.get("value")) == ["duplicated"]]
    if len(moves) != 2:
        raise ValueError("surface syntax repaired duplicated ownership use")
    erased = _named(function, "let", "erased")
    if _texts(_object(erased.get("value"), "zero-use effectful initializer").get("callee")) != ["Effectful"]:
        raise ValueError("surface invalid zero-use binding lost its evaluated computation")
    escaping = _object(_named(function, "let", "escaping").get("value"), "escaping callback")
    if not any(node.get("kind") == "unary" and _texts(node.get("operator")) == ["await"] for node in nodes(escaping)):
        raise ValueError("surface syntax repaired borrowing across a suspension")


def _domain_dictionary_roles(source: bytes, result: dict[str, Json]) -> None:
    product = _named(result.get("ast"), "domain", "Product")
    generics = [_object(value, "domain generic") for value in _sequence(product.get("generics"), "domain telescope")]
    if [_texts(value.get("name")) for value in generics] != [["A"], ["B"]]:
        raise ValueError("surface product domain lost its ordinary telescope")
    for generic in generics:
        _type_head(generic.get("type"), "GradeDomain", 0)
    contracts = [_object(value, "domain contract") for value in _sequence(product.get("contracts"), "domain contracts")]
    if [value.get("kind") for value in contracts] != ["contract", "effects"] or contracts[0].get("role") != "where":
        raise ValueError("surface domain law/effect ownership differs")
    _exact_span(source, contracts[0], b"where Compatible(A, B)")
    _exact_span(source, contracts[1], b"effects calls(A.interpret, B.interpret)")
    entries: dict[str, dict[str, Json]] = {}
    for value in _sequence(product.get("entries"), "domain entries"):
        entry = _object(value, "domain entry")
        role = entry.get("role")
        if not isinstance(role, str):
            raise TypeError("surface domain entry lacks its role")
        entries[role] = entry
    carrier = _object(entries["carrier"].get("value"), "product carrier")
    components = [_object(value, "carrier component") for value in _sequence(carrier.get("types"), "carrier components")]
    if carrier.get("kind") != "tuple_type" or [_texts(value.get("name")) for value in components] != [["A.carrier"], ["B.carrier"]]:
        raise ValueError("surface domain carrier stopped using ordinary product types")
    _exact_span(source, carrier, b"(A.carrier, B.carrier)")
    zero = _object(entries["zero"].get("value"), "product zero")
    if zero.get("kind") != "tuple" or _texts(zero) != ["A", "zero", "B", "zero"]:
        raise ValueError("surface product domain zero lost contextual member projections")
    addition = _object(entries["add"].get("value"), "domain addition callback")
    signature = _object(addition.get("signature"), "addition signature")
    if addition.get("kind") != "typed_lambda" or signature.get("effects") != []:
        raise ValueError("surface domain effects leaked into addition's callable signature")
    _contract_roles(signature, ["requires"])
    interpretation = _object(entries["interpret"].get("value"), "domain interpretation callback")
    interpretation_signature = _object(interpretation.get("signature"), "interpretation signature")
    if _texts(interpretation_signature.get("effects")) != ["Read"] or interpretation_signature.get("contracts") != []:
        raise ValueError("surface interpretation effects changed declaration ownership")
    laws = _object(entries["laws"].get("value"), "product laws")
    if _texts(laws) != ["ProductLaws", "A", "laws", "B", "laws"]:
        raise ValueError("surface product laws lost dictionary member names")
    legacy = _named(result.get("ast"), "domain", "Legacy")
    if legacy.get("generics") != [] or legacy.get("contracts") != []:
        raise ValueError("surface legacy domain fabricated a telescope or contract")
    associated = _object(_named(result.get("ast"), "alias", "Associated").get("type"), "qualified carrier")
    _exact_span(source, _object(associated.get("name"), "qualified carrier path"), b"Library.NatExact.carrier")
    add_zero = _named(result.get("ast"), "definition", "AddZero")
    _type_head(add_zero.get("result"), "NatExact.carrier", 0)
    addition_call = _object(add_zero.get("value"), "dictionary addition")
    _exact_span(source, _object(addition_call.get("callee"), "addition member"), b"NatExact.add")
    selected = _named(result.get("ast"), "typed_local", "selected")
    _type_head(selected.get("type"), "NatExact.carrier", 0)
    _exact_span(source, selected, b"NatExact.carrier selected @ q = NatExact.one;")
    identity = _object(_named(result.get("ast"), "let", "identity").get("value"), "carrier callback")
    parameter = _object(_sequence(identity.get("parameters"), "carrier callback parameters")[0], "carrier callback binder")
    _type_head(parameter.get("type"), "NatExact.carrier", 0)
    _exact_span(source, parameter, b"NatExact.carrier operand")
    for local_name, role in (("multiply", "mul"), ("permitted", "admits"), ("interpreted", "interpret")):
        value = _object(_named(result.get("ast"), "let", local_name).get("value"), "dictionary operation")
        member = _object(value.get("callee"), "dictionary operation member")
        if member.get("kind") != "member" or _texts(member.get("name")) != [role]:
            raise ValueError("surface domain role was not retained as an ordinary member")


def _disposal_clause_roles(source: bytes, result: dict[str, Json]) -> None:
    deep = _object(_named(result.get("ast"), "let", "deep").get("value"), "deep handler")
    clauses = [_object(value, "deep handler clause") for value in _sequence(deep.get("clauses"), "deep handler clauses")]
    if deep.get("shallow") is not False or _texts(deep.get("capability")) != ["active"]:
        raise ValueError("surface disposal changed its enclosing handler capability")
    if [value.get("kind") for value in clauses] != ["operation_clause", "return_clause", "disposal_clause"]:
        raise ValueError("surface disposal absorbed operation or return clauses")
    disposal = clauses[2]
    _exact_span(source, _object(disposal.get("name"), "disposal reason binder"), b"cancelled")
    _exact_span(source, _object(disposal.get("body"), "disposal block"), b"{ Cleanup(cancelled); return (); }")
    shallow = _object(_named(result.get("ast"), "let", "outerHandler").get("value"), "shallow handler")
    outer_clauses = [_object(value, "shallow clause") for value in _sequence(shallow.get("clauses"), "shallow clauses")]
    rehandler = _object(outer_clauses[0].get("body"), "nested rehandler")
    if (shallow.get("shallow") is not True or rehandler.get("kind") != "rehandle"
            or rehandler.get("shallow") is not True or _texts(rehandler.get("capability")) != ["forwarded"]):
        raise ValueError("surface disposal lost shallow rehandler association")
    inner = _named(rehandler, "disposal_clause", "innerReason")
    if _object(inner.get("body"), "expression disposal body").get("kind") != "call":
        raise ValueError("surface expression disposal body acquired a block")
    _exact_span(source, inner, b"dispose innerReason => Cleanup(innerReason)")
    outer = outer_clauses[1]
    if outer.get("kind") != "disposal_clause" or _texts(outer.get("name")) != ["shallowReason"]:
        raise ValueError("surface inner disposal escaped into the outer handler")
    unary = next(node for node in nodes(outer) if node.get("kind") == "dispose")
    if _texts(unary.get("value")) != ["continuation"]:
        raise ValueError("surface disposal clause replaced the existing dispose computation")


def _disposal_error_roles(result: dict[str, Json]) -> None:
    handler = _object(_named(result.get("ast"), "let", "duplicate").get("value"), "invalid disposal handler")
    clauses = [_object(value, "invalid disposal clause") for value in _sequence(handler.get("clauses"), "invalid disposal clauses")]
    if [value.get("kind") for value in clauses] != ["disposal_clause", "disposal_clause", "return_clause"]:
        raise ValueError("surface syntax silently repaired duplicate disposal clauses")
    if _texts(_object(clauses[0].get("body"), "invalid capability use").get("callee")) != ["forbidden", "Choose"]:
        raise ValueError("surface syntax removed forbidden handler-capability use")
    if not any(node.get("kind") == "resume" for node in nodes(clauses[1])):
        raise ValueError("surface syntax removed invalid disposal resumption")


def _generic_callable_annotation_roles(source: bytes, result: dict[str, Json]) -> None:
    direct = _named(result.get("ast"), "typed_local", "direct")
    signature = _object(_type_head(direct.get("type"), "Box", 1)[0], "generic callable")
    if signature.get("kind") != "function_type" or _texts(direct.get("grade")) != ["q"]:
        raise ValueError("surface generic callable arrow displaced the local allowance")
    _exact_span(source, signature, b"Fn(Nat n) -> Vec<T, n>")
    result_arguments = _type_head(signature.get("result"), "Vec", 2)
    if [_texts(value) for value in result_arguments] != [["T"], ["n"]]:
        raise ValueError("surface generic callable lost dependent result indices")
    nested = _named(result.get("ast"), "typed_local", "nested")
    owned = _object(_type_head(nested.get("type"), "Result", 2)[0], "owned callable box")
    nested_signature = _object(_type_head(owned.get("type"), "Box", 1)[0], "nested callable signature")
    if owned.get("modifier") != "owned" or nested_signature.get("mode") != "FnOnce":
        raise ValueError("surface generic callable lost ownership or call mode")
    if _texts(nested_signature.get("captures")) != ["Environment"] or _texts(nested_signature.get("effects")) != ["Read"]:
        raise ValueError("surface generic callable displaced capture/effect annotations")
    contracts = _contract_roles(nested_signature, ["requires", "restores"])
    _exact_span(source, contracts[0], b"requires Valid(item)")
    parameter = _object(_sequence(nested_signature.get("parameters"), "nested callable parameters")[0], "scoped callable parameter")
    scoped = _object(parameter.get("type"), "scoped callable loan")
    loan = _object(scoped.get("type"), "exclusive callable loan")
    if (scoped.get("modifier") != "scoped" or loan.get("modifier") != "ref"
            or _texts(loan.get("lifetime")) != ["'r"] or _texts(parameter.get("grade")) != ["q"]):
        raise ValueError("surface generic annotation displaced its parameter loan/grade")
    callback_local = _named(result.get("ast"), "let", "callback")
    callback = _object(callback_local.get("value"), "inferred generic callback")
    box_parameter = _object(_sequence(callback.get("parameters"), "inferred callback telescope")[0], "generic box parameter")
    box_signature = _object(_type_head(box_parameter.get("type"), "Box", 1)[0], "boxed mutable callable")
    if (callback.get("kind") != "lambda" or callback_local.get("grade") is not None
            or _texts(box_parameter.get("grade")) != ["q"] or box_signature.get("mode") != "FnMut"):
        raise ValueError("surface generic callback conflated local and parameter allowances")
    _contract_roles(box_signature, ["restores"])
    if _texts(box_signature.get("effects")) != ["Write"]:
        raise ValueError("surface boxed callback lost its effect annotation")
    higher = _named(result.get("ast"), "typed_local", "higher")
    higher_signature = _object(_type_head(higher.get("type"), "Box", 1)[0], "higher-order callable")
    grouped_result = _object(higher_signature.get("result"), "higher-order result")
    if grouped_result.get("kind") != "group_type" or _object(grouped_result.get("type"), "returned callable").get("kind") != "function_type":
        raise ValueError("surface generic annotation lost its returned callable")
    computed = _type_head(_named(result.get("ast"), "typed_local", "computed").get("type"), "Index", 2)
    callback_argument = _object(_object(computed[0], "callback value argument").get("value"), "computed generic callback")
    equivalence = _object(_object(computed[1], "equivalence argument").get("value"), "generic equivalence")
    if callback_argument.get("kind") != "typed_lambda" or _texts(equivalence.get("operator")) != ["<==>"]:
        raise ValueError("surface generic lookahead confused callback/equivalence arrows")
    literal = _type_head(_named(result.get("ast"), "typed_local", "literal").get("type"), "Index", 1)
    string = _object(_object(literal[0], "literal argument").get("value"), "arrow-like string")
    if string.get("kind") != "string" or string.get("value") != '"-> >"':
        raise ValueError("surface generic lookahead interpreted a literal arrow")


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
                                 ("UnitType", "type", b"type Unit"),
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
    expression_group = _object(precondition.get("value"), "grouped type-valued precondition")
    if expression_group.get("kind") != "group":
        raise ValueError("surface type-valued contract lost its explicit grouping")
    expression = _object(expression_group.get("value"), "type-valued precondition")
    if (precondition.get("role") != "requires" or expression.get("kind") != "type_expression"
            or effects.get("kind") != "effects" or _texts(effects) != ["writes", "Storage"]):
        raise ValueError("surface type expression confused callable and declaration effects")
    _exact_span(source, precondition, b"requires (type (Fn() -> bool effects(Read)))")
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
                b"invariant Closed(this)")
    if _texts(_named(cell, "field", "Value").get("grade")) != ["q"]:
        raise ValueError("surface container contract displaced a field grade")
    closed = _named(cell, "function", "Close")
    if _texts(closed.get("contracts")) != ["Opened", "this", "Closed", "this"]:
        raise ValueError("surface container invariant swallowed its member's contracts")
    storage = _named(result.get("ast"), "interface", "Storage")
    read = _named(storage, "operation", "Read")
    if _texts(read.get("contracts")) != ["Readable", "this", "Stable", "result"]:
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
    _exact_span(source, _object(arm.get("pattern"), "dependent arm pattern"), b"Packed(count, bytes)")
    if _texts(arm.get("value")) != ["bytes"] or "statements" in arm:
        raise ValueError("surface expression arm value became a statement body")
    value_start = source.index(b"=> bytes,") + len(b"=> ")
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
    if unit.get("kind") != "type":
        raise ValueError("surface unit type conflated with value syntax")
    _exact_span(source, unit, b"Unit")
    package = _named(result.get("ast"), "function", "Package")
    returned = _object(package.get("result"), "resource product result")
    outer = _sequence(returned.get("types"), "resource product types")
    if returned.get("kind") != "tuple_type" or len(outer) != 2:
        raise ValueError("surface returned resource product shape differs")
    first, second = [_object(value, "resource component") for value in outer]
    inner = _sequence(second.get("types"), "nested resource types")
    if (first.get("modifier") != "owned" or second.get("kind") != "tuple_type"
            or len(inner) != 2 or _object(inner[0], "receipt type").get("modifier") != "tracked"
            or _object(inner[1], "empty type").get("kind") != "type"):
        raise ValueError("surface product erased resource modifiers or nesting")
    destructures = [node for node in nodes(result.get("ast")) if node.get("kind") == "let_pattern"]
    if len(destructures) != 1:
        raise ValueError("surface local product elimination lost its statement role")
    destructure = destructures[0]
    _exact_span(source, destructure, b"let (owner, (receipt, ())) = package;")
    pattern = _object(destructure.get("pattern"), "local product pattern")
    _exact_span(source, pattern, b"(owner, (receipt, ()))")
    fields = _sequence(pattern.get("patterns"), "product pattern fields")
    if pattern.get("kind") != "tuple_pattern" or len(fields) != 2:
        raise ValueError("surface local product pattern shape differs")
    binding = _object(fields[0], "owner binding")
    if binding.get("kind") != "binding_pattern" or _texts(binding.get("name")) != ["owner"]:
        raise ValueError("surface product owner field is not a binding pattern")
    _exact_span(source, binding, b"owner")
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
    if annotation.get("modifier") != "ref" or _texts(annotation.get("lifetime")) != ["'this.text"]:
        raise ValueError("surface structural local annotation lost its place-named loan")
    group = _object(annotation.get("type"), "grouped view type")
    if group.get("kind") != "group_type":
        raise ValueError("surface structural local grouping lost its type role")
    _type_head(group.get("type"), "Span", 1)
    _exact_span(source, annotation, b"ref<'this.text> (Span<byte>)")
    for name, kind, spelling in (("pair", "tuple_type", b"(owned Packet, tracked Receipt) pair"),
                                 ("value", "type", b"Unit value"),
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


def _operator_value(source: bytes, value: Json, symbol: str) -> dict[str, Json]:
    operator = _object(value, "operator value")
    located = _object(operator.get("name"), "operator symbol")
    span = operator.get("span")
    if (operator.get("kind") != "operator" or located.get("text") != symbol
            or not isinstance(span, list) or len(span) != 2):
        raise ValueError("surface operator value lost its syntax or symbol role")
    start, end = span
    if (type(start) is not int or type(end) is not int
            or source[start:end] != f"({symbol})".encode()
            or located.get("span") != [start + 1, end - 1]):
        raise ValueError("surface operator value or symbol original-byte span differs")
    return operator


def _shared_primitive_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    product = _named(tree, "alias", "Product").get("type")
    generic = _named(tree, "alias", "Generic").get("type")
    argument = _object(_type_head(generic, "Box", 1)[0], "structural generic argument")
    local = _named(tree, "typed_local", "local").get("type")
    callback = _object(_named(tree, "let", "callback").get("value"), "structural callback")
    parameters = _sequence(callback.get("parameters"), "structural callback parameters")
    if len(parameters) != 1:
        raise ValueError("surface shared callback lost its parameter")
    parameter = _object(parameters[0], "structural callback parameter")
    if (argument.get("kind") != "type_argument" or callback.get("kind") != "lambda"
            or parameter.get("kind") != "lambda_parameter"
            or _texts(parameter.get("name")) != ["input"]):
        raise ValueError("surface shared type syntax lost its generic or callback role")
    for value in (product, argument.get("type"), local, parameter.get("type")):
        annotation = _object(value, "shared product type")
        components = _sequence(annotation.get("types"), "shared product components")
        if annotation.get("kind") != "tuple_type" or len(components) != 2:
            raise ValueError("surface shared product type lost its arity or type role")
        unit, group = [_object(component, "shared product component") for component in components]
        if unit.get("kind") != "type" or group.get("kind") != "group_type":
            raise ValueError("surface unit/group type became a value or pattern")
        _type_head(group.get("type"), "Core.Value", 0)
        for node, spelling in ((annotation, b"(Unit, (Core.Value))"), (unit, b"Unit"),
                               (group, b"(Core.Value)")):
            span = _sequence(node.get("span"), "shared type byte span")
            if len(span) != 2 or type(span[0]) is not int or type(span[1]) is not int:
                raise ValueError("surface shared type has no original-byte span")
            if source[span[0]:span[1]] != spelling:
                raise ValueError("surface shared type byte span differs")
    empty = _object(_named(tree, "let", "empty").get("value"), "empty callback")
    if (empty.get("kind") != "lambda" or empty.get("parameters") != []
            or _object(empty.get("body"), "empty callback body").get("kind") != "unit"):
        raise ValueError("surface empty callback changed its parameter/body boundary")
    values = _object(_named(tree, "let", "values").get("value"), "literal tuple")
    literals = _sequence(values.get("values"), "literal tuple values")
    patterns = [node for node in nodes(tree)
                if node.get("kind") in {"nat_pattern", "string_pattern", "character_pattern", "bool_pattern"}]
    expected: tuple[tuple[str, Json, str | None, bytes], ...] = (
        ("nat", "0007", "", b"0007"), ("nat", "0xAf", "u8", b"0xAfu8"),
        ("string", '"café"', None, '"café"'.encode()),
        ("character", "'\\n'", None, b"'\\n'"),
        ("bool", True, None, b"true"), ("bool", False, None, b"false"),
    )
    if values.get("kind") != "tuple" or len(literals) != len(expected) or len(patterns) != len(expected):
        raise ValueError("surface shared literal syntax lost an expression or pattern")
    for expression, pattern, (kind, payload, suffix, spelling) in zip(literals, patterns, expected, strict=True):
        for value, role in ((expression, kind), (pattern, kind + "_pattern")):
            literal = _object(value, "shared literal")
            if (literal.get("kind") != role or literal.get("value") != payload
                    or literal.get("suffix") != suffix):
                raise ValueError("surface shared literal changed its role, payload or representation")
            span = _sequence(literal.get("span"), "shared literal byte span")
            if (len(span) != 2 or type(span[0]) is not int or type(span[1]) is not int
                    or source[span[0]:span[1]] != spelling):
                raise ValueError("surface shared literal original-byte span differs")
    outer = _object(_named(tree, "definition", "Nested").get("value"), "outer quantifier")
    inner = _object(outer.get("value"), "inner quantifier")
    for quantifier, role, binder in ((outer, "forall", "outer"), (inner, "exists", "inner")):
        parameters = _sequence(quantifier.get("parameters"), "quantifier parameters")
        if (quantifier.get("kind") != "quantifier" or quantifier.get("quantifier") != role
                or len(parameters) != 1 or _texts(_object(parameters[0], "quantifier parameter").get("name")) != [binder]):
            raise ValueError("surface shared quantifier changed its keyword or binder scope")
    equality = _object(inner.get("value"), "quantified equality")
    if (equality.get("kind") != "binary" or _texts(equality.get("operator")) != ["=="]
            or _texts(equality.get("left")) != ["outer"] or _texts(equality.get("right")) != ["inner"]):
        raise ValueError("surface nested quantifier body changed its operand roles")


def _shared_operator_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    returned = _object(_named(tree, "definition", "Addition").get("value"), "returned operator")
    _operator_value(source, returned, "+")
    function = _named(tree, "function", "Use")
    contract = _object(_sequence(function.get("contracts"), "operator contract")[0], "operator contract")
    law = _object(contract.get("value"), "operator law call")
    _operator_value(source, _sequence(law.get("arguments"), "operator law arguments")[0], "+")
    all_values = _object(_named(function, "let", "all").get("value"), "operator tuple")
    symbols = ("+", "-", "*", "/", "%", "<", "<=", ">", ">=", "==", "!=",
               "&&", "||", "&", "|", "^", "==>", "<==>", "!", "~")
    values = _sequence(all_values.get("values"), "operator tuple values")
    if all_values.get("kind") != "tuple" or len(values) != len(symbols):
        raise ValueError("surface operator tuple omitted or regrouped a symbolic operation")
    for value, symbol in zip(values, symbols, strict=True):
        _operator_value(source, value, symbol)
    direct = _object(_named(function, "let", "direct").get("value"), "direct operator call")
    if direct.get("kind") != "call" or _texts(direct.get("arguments")) != ["left", "right"]:
        raise ValueError("surface operator call displaced its arguments")
    _operator_value(source, direct.get("callee"), "+")
    projected = _object(_named(function, "let", "projected").get("value"), "projected operator call")
    member = _object(projected.get("callee"), "operator member")
    if member.get("kind") != "member" or _texts(member.get("name")) != ["Apply"]:
        raise ValueError("surface operator value cannot compose with ordinary member syntax")
    _operator_value(source, member.get("value"), "*")
    specialised = _object(_named(function, "let", "specialised").get("value"), "specialised operator call")
    application = _object(specialised.get("callee"), "specialised operator")
    if application.get("kind") != "generic_application":
        raise ValueError("surface operator generic application lost its postfix role")
    _operator_value(source, application.get("value"), "%")
    _type_head(_sequence(application.get("arguments"), "operator type arguments")[0], "Nat", 0)
    higher = _object(_named(function, "let", "higher").get("value"), "higher-order call")
    _operator_value(source, _sequence(higher.get("arguments"), "fold arguments")[0], "+")
    callback = _object(_named(function, "let", "callback").get("value"), "operator callback")
    callback_body = _object(callback.get("body"), "operator callback body")
    if callback.get("kind") != "lambda" or callback_body.get("kind") != "call":
        raise ValueError("surface operator callback lost its lambda/body boundary")
    _operator_value(source, callback_body.get("callee"), "-")
    for binding, grouped in (("directGeneric", False), ("groupedGeneric", True)):
        called = _object(_named(function, "let", binding).get("value"), "generic operator call")
        generic = _object(called.get("callee"), "generic operator application")
        argument = _object(_sequence(generic.get("arguments"), "generic operator arguments")[0], "generic operator argument")
        if called.get("kind") != "call" or generic.get("kind") != "generic_application":
            raise ValueError("surface generic operator argument changed its enclosing application")
        if grouped:
            if argument.get("kind") != "group":
                raise ValueError("surface explicitly grouped generic operator lost its group")
            start = source.index(b"Apply::<((+))>") + len(b"Apply::<")
            if argument.get("span") != [start, start + len(b"((+))")]:
                raise ValueError("surface grouped generic operator span differs from its application")
            argument = _object(argument.get("value"), "grouped operator")
        _operator_value(source, argument, "+")
    computed = _object(_named(tree, "alias", "Computed").get("type"), "operator computed type")
    family = _object(computed.get("value"), "operator type-family call")
    if computed.get("kind") != "computed_type" or family.get("kind") != "call":
        raise ValueError("surface operator value changed computed-type expression roles")
    _operator_value(source, _sequence(family.get("arguments"), "operator family arguments")[0], "+")
    domain = _named(tree, "domain", "Arithmetic")
    entries = {_object(value, "domain entry").get("role"): _object(value, "domain entry")
               for value in _sequence(domain.get("entries"), "domain entries")}
    for role, symbol in (("add", "+"), ("mul", "*"), ("admits", "<=")):
        _operator_value(source, entries[role].get("value"), symbol)


def _operator_expression_shape(value: Json) -> Json:
    expression = _object(value, "operator precedence expression")
    kind = expression.get("kind")
    if kind == "nat":
        return ["nat", expression.get("value"), expression.get("suffix")]
    if kind == "binary":
        operator = _object(expression.get("operator"), "precedence symbol")
        return [operator.get("text"), _operator_expression_shape(expression.get("left")),
                _operator_expression_shape(expression.get("right"))]
    if kind == "range":
        return ["range", _operator_expression_shape(expression.get("start")),
                _operator_expression_shape(expression.get("end"))]
    if kind == "unary":
        return ["unary", _object(expression.get("operator"), "prefix symbol").get("text"),
                _operator_expression_shape(expression.get("value"))]
    if kind == "group":
        return ["group", _operator_expression_shape(expression.get("value"))]
    raise ValueError(f"unexpected operator-precedence AST role: {kind}")


def _shared_precedence_roles(result: dict[str, Json]) -> None:
    def n(value: int) -> Json:
        return ["nat", str(value), ""]

    arithmetic: Json = ["+", n(10), ["*", n(11), n(12)]]
    bitwise: Json = ["|", n(7), ["^", n(8), ["&", n(9), arithmetic]]]
    comparison: Json = ["==", n(5), ["range", n(6), bitwise]]
    logical: Json = ["||", n(3), ["&&", n(4), comparison]]
    expected: dict[str, Json] = {
        "Ladder": ["==>", n(1), ["<==>", n(2), logical]],
        "Additive": ["+", ["-", n(20), n(6)], n(2)],
        "Multiplicative": ["*", ["%", ["/", n(24), n(4)], n(3)], n(2)],
        "Prefixes": ["unary", "!", ["unary", "~", ["unary", "-", n(1)]]],
        "Grouping": ["+", ["group", ["unary", "-", n(1)]], ["group", ["+", n(2), n(3)]]],
    }
    for name, symbol in (("Disjunction", "||"), ("Conjunction", "&&"),
                         ("BitOr", "|"), ("BitXor", "^"), ("BitAnd", "&")):
        expected[name] = [symbol, [symbol, n(1), n(2)], n(3)]
    for name, symbol in (("Implication", "==>"), ("Equivalence", "<==>")):
        expected[name] = [symbol, n(1), [symbol, n(2), n(3)]]
    for name, shape in expected.items():
        actual = _named(result.get("ast"), "definition", name).get("value")
        if _operator_expression_shape(actual) != shape:
            raise ValueError(f"surface operator precedence/associativity differs for {name}")


def _recursive_pattern_shape(value: Json) -> Json:
    pattern = _object(value, "recursive pattern")
    kind = pattern.get("kind")
    if kind == "binding_pattern":
        return ["bind", *_texts(pattern.get("name"))]
    if kind == "constructor_pattern":
        return ["constructor", *_texts(pattern.get("name")),
                [_recursive_pattern_shape(child) for child in _sequence(pattern.get("arguments"), "constructor arguments")]]
    if kind == "group_pattern":
        return ["group", _recursive_pattern_shape(pattern.get("pattern"))]
    if kind == "tuple_pattern":
        return ["tuple", [_recursive_pattern_shape(child) for child in _sequence(pattern.get("patterns"), "product patterns")]]
    if kind in {"unit_pattern", "wildcard_pattern"}:
        return kind
    raise ValueError(f"unexpected recursive pattern role: {kind}")


def _recursive_local_roles(source: bytes, result: dict[str, Json]) -> None:
    function = _named(result.get("ast"), "function", "Eliminate")
    statements = _sequence(_object(function.get("body"), "elimination block").get("statements"), "elimination statements")
    expected: list[tuple[str, bytes, Json]] = [
        ("let_pattern", b"Some(value)", ["constructor", "Some", [["bind", "value"]]]),
        ("var_pattern", b"Ready((owner, receipt))", ["constructor", "Ready", [["tuple", [["bind", "owner"], ["bind", "receipt"]]]]]),
        ("let_pattern", b"Result.Empty()", ["constructor", "Result.Empty", []]),
        ("let_pattern", b"(Some((nested)))", ["group", ["constructor", "Some", [["group", ["bind", "nested"]]]]]),
        ("let_pattern", b"Outer(Inner(deep), (item, ()))", ["constructor", "Outer", [
            ["constructor", "Inner", [["bind", "deep"]]], ["tuple", [["bind", "item"], "unit_pattern"]]]]),
        ("let_pattern", b"((grouped))", ["group", ["group", ["bind", "grouped"]]]),
    ]
    for statement, (kind, spelling, shape) in zip(statements[:6], expected, strict=True):
        local = _object(statement, "local pattern binding")
        pattern = _object(local.get("pattern"), "local elimination pattern")
        if local.get("kind") != kind or _recursive_pattern_shape(pattern) != shape:
            raise ValueError("surface local constructor/group/product elimination roles differ")
        _exact_span(source, pattern, spelling)
        if "grade" in local or "name" in local:
            raise ValueError("surface pattern elimination fabricated a name or component allowance")
    for node in nodes(function):
        if node.get("kind") in {"binding_pattern", "constructor_pattern", "group_pattern", "tuple_pattern", "unit_pattern"}:
            span = node.get("span")
            if not isinstance(span, list) or len(span) != 2:
                raise ValueError("surface recursive pattern lacks its own byte span")
            start, end = span
            if type(start) is not int or type(end) is not int:
                raise ValueError("surface recursive pattern span is not an offset pair")
            if node.get("kind") == "binding_pattern":
                name = _object(node.get("name"), "nested pattern binder")
                text = name.get("text")
                if not isinstance(text, str) or source[start:end] != text.encode():
                    raise ValueError("surface nested binding span differs from original bytes")
                if name.get("span") != [start, end]:
                    raise ValueError("surface nested binding name span differs from its binder")
    inferred = _named(function, "let", "inferred")
    mutable = _named(function, "var", "mutable")
    if (inferred.get("type") is not None or inferred.get("grade") is not None
            or "pattern" in inferred or _texts(inferred.get("value")) != ["optional"]
            or _texts(mutable.get("grade")) != ["q"] or "pattern" in mutable):
        raise ValueError("surface bare local names changed into constructor patterns")
    for binding, outer in (("sharedLoan", "in"), ("exclusiveLoan", "ref")):
        group = _object(_named(function, "let", binding).get("value"), "grouped loan computation")
        first = _object(group.get("value"), "outer loan computation")
        second = _object(first.get("value"), "inner loan computation")
        if (group.get("kind") != "group" or first.get("kind") != "unary" or second.get("kind") != "unary"
                or _texts(first.get("operator")) != [outer] or _texts(second.get("operator")) != ["ref"]
                or _texts(second.get("value")) != ["value"]):
            raise ValueError("surface grouped loan computations became type annotations")
        _exact_span(source, group, f"({outer} ref value)".encode())
    for kind, binding in (("let", "annotated"), ("typed_local", "bareAnnotated"),
                          ("var", "mutableAnnotated")):
        local = _named(function, kind, binding)
        _type_head(_type_head(local.get("type"), "Core.Box", 1)[0], "Nat", 0)
        if "pattern" in local or _texts(local.get("value")) != ["source"]:
            raise ValueError("surface qualified typed local changed into constructor elimination")
    loan_annotation = _object(_named(function, "let", "loanAnnotated").get("type"), "qualified loan local")
    if loan_annotation.get("modifier") != "ref" or _texts(loan_annotation.get("lifetime")) != ["'source"]:
        raise ValueError("surface qualified local annotation lost its loan lifetime")
    _type_head(_type_head(loan_annotation.get("type"), "Core.Box", 1)[0], "Nat", 0)
    qualified = [node for node in nodes(function) if node.get("kind") == "constructor_pattern"
                 and _texts(node.get("name")) == ["Core.Result.Ready"]]
    if len(qualified) != 1 or _recursive_pattern_shape(qualified[0]) != ["constructor", "Core.Result.Ready", [["bind", "qualified"]]]:
        raise ValueError("surface qualified constructor elimination became a local type annotation")
    _exact_span(source, qualified[0], b"Core.Result.Ready(qualified)")
    cases = [node for node in nodes(function) if node.get("kind") == "case"]
    tests = [node for node in nodes(function) if node.get("kind") == "is"]
    if len(cases) != 1 or len(tests) != 1:
        raise ValueError("surface grouped pattern lost its match/test owner")
    for owner, binder in ((cases[0], "matched"), (tests[0], "testedValue")):
        expected_pattern: Json = ["group", ["constructor", "Some", [["group", ["bind", binder]]]]]
        if _recursive_pattern_shape(owner.get("pattern")) != expected_pattern:
            raise ValueError("surface match/test grouping differs from local pattern grouping")
    invalid = _named(result.get("ast"), "function", "InvalidMeaning")
    if len([node for node in nodes(invalid) if node.get("kind") in {"let_pattern", "var_pattern"}]) != 3:
        raise ValueError("surface resource or constructor mistakes were resolved during parsing")


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


def _numeric_separator_roles(source: bytes, result: dict[str, Json]) -> None:
    def span_start(node: dict[str, Json]) -> int:
        span = node.get("span")
        if not isinstance(span, list) or len(span) != 2:
            raise ValueError("numeric separator literal has no original-byte span")
        first, last = span
        if type(first) is not int or type(last) is not int:
            raise ValueError("numeric separator span endpoints must be integers")
        return first

    literals = sorted((node for node in nodes(result.get("ast"))
                       if node.get("kind") in {"nat", "nat_pattern"}),
                      key=span_start)
    expected = (("1_024", "usize"), ("1_000", ""), ("1_024", ""),
                ("0b1010_0011", "byte"), ("0xA_3", "u8"), ("0xFF_FF", "u16"), ("1_0", ""))
    if len(literals) != len(expected):
        raise ValueError("numeric separators changed literal or pattern boundaries")
    cursor = 0
    for literal, (digits, suffix) in zip(literals, expected, strict=True):
        if literal.get("value") != digits or literal.get("suffix") != suffix:
            raise ValueError("numeric separator spelling or representation suffix differs")
        spelling = (digits + suffix).encode()
        start = source.index(spelling, cursor)
        cursor = start + len(spelling)
        if literal.get("span") != [start, cursor]:
            raise ValueError("numeric separator original-byte span differs")


def _numeric_separator_limits(parse: Callable[[bytes], dict[str, Json]]) -> None:
    prefix = b"module M; public Nat F() => "
    for base, digit in ((b"", b"9"), (b"0x", b"f"), (b"0b", b"1")):
        parse(prefix + base + b"_".join([digit] * 256) + b";")
        try:
            parse(prefix + base + b"_".join([digit] * 257) + b";")
        except VelaError as error:
            if error.kind != "limit":
                raise ValueError("separated literal has the wrong digit-bound refusal") from error
        else:
            raise ValueError("separated literal bypassed its actual-digit bound")
    for spelling in (b"1_", b"1__0", b"1_usize", b"0x_FF", b"0xFF_u64",
                     b"0xF__F", b"0b_10", b"0b10_", b"0b1__0", b"0b1_2"):
        try:
            parse(prefix + spelling + b";")
        except VelaError as error:
            if error.kind != "syntax":
                raise ValueError("malformed separator has the wrong syntax refusal") from error
        else:
            raise ValueError(f"malformed numeric separator parsed: {spelling!r}")


def _familiar_call_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")

    def local(name: str) -> dict[str, Json]:
        return _object(_named(tree, "let", name).get("value"), "familiar local value")

    one = local("genericSingle")
    arguments = _sequence(one.get("arguments"), "outer generic-call arguments")
    if len(arguments) != 1:
        raise ValueError("ordinary generic call became comma-separated comparison arguments")
    inner = _object(arguments[0], "inner call")
    generic = _object(inner.get("callee"), "ordinary generic application")
    if inner.get("kind") != "call" or generic.get("kind") != "generic_application":
        raise ValueError("ordinary generic call lost its application and call roles")
    if [_texts(argument.get("name")) for argument in
            (_object(value, "generic type") for value in _sequence(generic.get("arguments"), "type arguments"))] != [["A"], ["B"]]:
        raise ValueError("ordinary generic call changed its type arguments")
    comparisons = _sequence(local("comparisons").get("arguments"), "comparison arguments")
    operators = [_texts(_object(value, "comparison").get("operator"))
                 for value in comparisons]
    if operators != [["<"], [">"]]:
        raise ValueError("unsuccessful generic probe changed ordinary comparisons")
    if (local("ambiguous").get("kind") != "call" or local("groupedComparison").get("kind") != "binary"
            or local("computedCall").get("kind") != "call"):
        raise ValueError("generic classification depends on whitespace, resolution or callee spelling")
    for name, spelling in (("ambiguous", b"f /* comment */ < n >"), ("explicitCall", b"Identity::<Nat>")):
        application = _object(local(name).get("callee"), "source-bound application")
        binding_start = _sequence(_named(tree, "let", name).get("span"), "generic local span")[0]
        if type(binding_start) is not int:
            raise ValueError("generic local has no byte offset")
        start = source.index(spelling, binding_start)
        if application.get("kind") != "generic_application" or application.get("span") != [start, start + len(spelling)]:
            raise ValueError("ordinary/explicit generic application lost original UTF-8 spans")
    match = next(node for node in nodes(tree) if node.get("kind") == "match_expression")
    cases = _sequence(match.get("cases"), "familiar expression arms")
    if len(cases) != 2 or any(_object(value, "expression arm").get("kind") != "expression_case" for value in cases):
        raise ValueError("comma expression match changed arm roles")
    nested = _object(local("nestedValue").get("callee"), "nested generic value application")
    grouped = _object(_sequence(nested.get("arguments"), "nested generic value arguments")[0], "grouped generic value")
    called = _object(grouped.get("value"), "nested ordinary call")
    if (grouped.get("kind") != "group" or called.get("kind") != "call"
            or _object(called.get("callee"), "nested call callee").get("kind") != "generic_application"):
        raise ValueError("nested ordinary generic call became type syntax or comparisons")
    for annotation in (_named(tree, "let", "annotated").get("type"),
                       _sequence(local("callback").get("parameters"), "typed callback parameters")[0]):
        if not any(node.get("kind") == "computed_type" for node in nodes(annotation)):
            raise ValueError("annotation lookahead lost the computed type's ordinary generic call")


def _collection_iteration_roles(source: bytes, result: dict[str, Json]) -> None:
    visit = _named(result.get("ast"), "function", "Visit")
    contracts = _contract_roles(visit, ["where", "requires", "requires", "ensures"])
    bounds = {text for node in nodes(contracts[0]) if node.get("kind") == "call" for text in _texts(node.get("callee"))}
    if bounds != {"ISequenceModel", "IBoundedIterable"}:
        raise ValueError("sequence .Model contract lost its ISequenceModel/IBoundedIterable bounds")
    all_call = _object(contracts[1].get("value"), "sequence All contract")
    all_member = _object(all_call.get("callee"), "sequence All member")
    all_lambda = _object(_sequence(all_call.get("arguments"), "sequence All arguments")[0], "sequence All predicate")
    if (all_call.get("kind") != "call" or all_member.get("kind") != "member"
            or _texts(all_member.get("name")) != ["All"] or all_lambda.get("kind") != "lambda"):
        raise ValueError("sequence .Model.All contract lost its member call or lambda predicate role")
    members = {text for clause in contracts[1:] for node in nodes(clause)
               if node.get("kind") == "member" for text in _texts(node.get("name"))}
    if not {"Model", "All", "Any", "Contains", "Take", "Skip", "Slice", "Count"} <= members:
        raise ValueError("sequence .Model contract vocabulary lost a predicate or slice projection")
    loops = [node for node in nodes(result.get("ast")) if node.get("kind") in {"foreach", "foreach_collection"}]
    expected = {
        "copied": ("value", False), "typed": ("value", True), "borrowed": ("in", False),
        "shared": ("in", True), "selected": ("ref", False), "exclusive": ("ref", True),
        "inner": ("value", False), "explicitRange": ("value", True), "loanRange": ("ref", False),
        "invalidCopy": ("value", False), "invalidLoan": ("ref", False),
    }
    if len(loops) != len(expected) + 2:
        raise ValueError("collection iteration lost a nested loop or a syntax-valid invalid neighbor")
    for loop in loops:
        name = _texts(loop.get("name"))
        if len(name) != 1:
            raise ValueError("collection loop lost its located immutable binder")
        binder = name[0]
        if binder in {"index", "grouped"}:
            if loop.get("kind") != "foreach" or set(loop) != {"kind", "span", "name", "range", "contracts", "body"}:
                raise ValueError("unannotated range/grouped range changed its existing AST fields")
            continue
        mode, typed = expected[binder]
        if (loop.get("kind") != "foreach_collection" or loop.get("mode") != mode
                or (loop.get("type") is not None) != typed
                or set(loop) != {"kind", "span", "name", "type", "mode", "collection", "contracts", "body"}):
            raise ValueError("collection iteration changed element mode, type or AST ownership")
        located = _object(loop.get("name"), "collection binder")
        start, end = _sequence(located.get("span"), "collection binder span")
        if type(start) is not int or type(end) is not int or source[start:end] != binder.encode():
            raise ValueError("collection binder has no exact original-byte source span")
        if binder == "exclusive" and len(_sequence(loop.get("contracts"), "exclusive loop contracts")) != 2:
            raise ValueError("collection contracts became body statements or type annotations")


def _raw_string_and_format_roles(source: bytes, result: dict[str, Json]) -> None:
    tree = result.get("ast")
    single = _object(_named(tree, "constant", "SingleRaw").get("value"), "single-line raw string")
    multi = _object(_named(tree, "constant", "MultiRaw").get("value"), "multi-line raw string")
    single_spelling = b'"""exact "quoted" \\raw caf\xc3\xa9"""'
    multi_spelling = b'"""\n    VERSION 1\n    MODE "STRICT" \\raw\n    """'
    for node, spelling in ((single, single_spelling), (multi, multi_spelling)):
        if node.get("kind") != "string" or node.get("value") != spelling.decode("utf-8"):
            raise ValueError("raw string literal changed its AST kind or raw spelling")
        _exact_span(source, node, spelling)
    pattern = next(node for node in nodes(tree) if node.get("kind") == "string_pattern")
    pattern_spelling = b'""""matched """ \\raw""""'
    if pattern.get("value") != pattern_spelling.decode("utf-8"):
        raise ValueError("raw string pattern lost its raw spelling")
    _exact_span(source, pattern, pattern_spelling)
    header = _named(tree, "function", "WriteHeader")
    clauses = [_object(value, "formatting contract")
               for value in _sequence(header.get("contracts"), "formatting contracts")]
    if [clause.get("role", clause.get("kind")) for clause in clauses] != ["where", "effects"]:
        raise ValueError("checked formatting contract or effects roles differ")
    if [_texts(node.get("callee")) for node in nodes(clauses[0]) if node.get("kind") == "call"] != [["Format"], ["Format"]]:
        raise ValueError("checked formatting lost its static Format<T> trait bounds")
    interpolated = [node for node in nodes(header) if node.get("kind") == "interpolated_string"]
    expected = (
        b'$"packet[{id}]={{tag:{tag:x2}}}"',
        b'$"id={Identity::<usize>(id)}"',
        b'$"allocated {id}"',
        b'$"len={builder.Length}"',
    )
    if len(interpolated) != len(expected):
        raise ValueError("interpolated format templates were omitted or conflated with ordinary strings")
    for node, spelling in zip(interpolated, expected, strict=True):
        if node.get("value") != spelling.decode("utf-8") or set(node) != {"kind", "span", "value"}:
            raise ValueError("interpolated format template changed its AST fields or spelling")
        _exact_span(source, node, spelling)
    for binding_name, target_name in (("first", "builder"), ("second", "scratch")):
        propagated = _object(_named(header, "let", binding_name).get("value"), "propagated Format.Write")
        call = _object(propagated.get("value"), "Format.Write call")
        arguments = _sequence(call.get("arguments"), "Format.Write arguments")
        if (propagated.get("kind") != "propagate" or call.get("kind") != "call"
                or _texts(call.get("callee")) != ["Format", "Write"] or len(arguments) != 2):
            raise ValueError("Format.Write call lost its propagation or receiver/template arity")
        target = _object(arguments[0], "Format.Write target loan")
        template = _object(arguments[1], "Format.Write template")
        if (target.get("kind") != "unary" or _texts(target.get("operator")) != ["ref"]
                or _texts(target.get("value")) != [target_name]
                or template.get("kind") != "interpolated_string"):
            raise ValueError("Format.Write lost its explicit ref target loan or interpolated template role")


def _generic_probe_limits(parse: Callable[[bytes], dict[str, Json]]) -> None:
    # A depth-n nested call inspects (7*n*n-n)/2 tokens: each enclosing
    # prefix adds seven tokens. Distinct source positions have distinct probes.
    nested = b"F<T>()"
    for _ in range(79):
        nested = b"F<(" + nested + b")>()"
    # F<A<B>>() includes a three-token unsuccessful nested probe (nine total).
    # Outer comparisons add a five-token unsuccessful probe across comments.
    base = (nested + b";") * 8 + b"F<A<B>>();Outer(F /* comment */ <\n T, A > value);"
    base_count = 8 * (7 * 80 * 80 - 80) // 2 + 9 + 5
    for count in (199_999, 200_000, 200_001):
        remainder = count - base_count
        pairs = remainder % 3
        singles = (remainder - 13 * pairs) // 3
        source = b"module M; void Main() {" + base + b"F<(F<T>())>();" * pairs + b"F<T>();" * singles + b"}"
        if len(source) > MAX_SOURCE_BYTES:
            raise ValueError("generic probe boundary fixture exceeds the independent source limit")
        try:
            parse(source)
        except VelaError as error:
            if count <= 200_000 or error.kind != "limit" or "200000 inspected tokens" not in error.message:
                raise ValueError("generic probe inspection boundary has the wrong refusal") from error
        else:
            if count > 200_000:
                raise ValueError("generic probe inspection exhaustion reinterpreted source or published syntax")


def qualify(parse: Callable[[bytes], dict[str, Json]]) -> list[str]:
    """Exercise independent syntax cases; a failed oracle never passes a case."""
    _precedence_and_spans(parse)
    _literal_and_comment_boundaries(parse)
    _numeric_separator_limits(parse)
    passed = ["surface:independent-precedence-and-spans", "surface:literal-and-comment-boundaries",
              "surface:numeric-separator-suffixes-and-digit-limits"]
    for fixture in POSITIVE:
        try:
            result = parse(fixture.source.encode("utf-8"))
        except VelaError as error:
            raise ValueError(f"surface fixture {fixture.name} failed at {error.line}:{error.column}: {error}") from error
        _argument_roles(fixture.source.encode("utf-8"), result)
        found = {node.get("kind") for node in nodes(result.get("ast"))}
        missing = set(fixture.kinds) - found
        if missing:
            raise ValueError(f"surface fixture {fixture.name} lacks AST roles: {sorted(missing)}")
        if fixture.name == "familiar-generic-calls-and-expression-arms":
            _familiar_call_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "bounded-collection-iteration":
            _collection_iteration_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "raw-strings-and-checked-formatting":
            _raw_string_and_format_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "numeric-separator-values-patterns-and-indices":
            _numeric_separator_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "callable-list-boundaries":
            _callable_list_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "required-static-constants":
            _required_static_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "compositional-constant-callables":
            _compositional_constant_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "canonical-readable-calls":
            _readable_call_roles(result)
        elif fixture.name == "concise-authoring-syntax":
            _concise_authoring_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "generic-binders-and-typed-initializers":
            _binder_initializer_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "binder-initializer-errors-remain-syntax":
            _binder_initializer_error_roles(result)
        elif fixture.name == "explicit-values-loans-and-options":
            _explicit_value_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "explicit-pointer-operators":
            _pointer_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "explicit-values-errors-remain-syntax":
            _explicit_error_roles(result)
        elif fixture.name == "expressions-and-closures":
            _propagation_member_role(result)
        elif fixture.name == "expression-local-bindings":
            _expression_binding_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "shared-syntax-primitives":
            _shared_primitive_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "shared-operator-values":
            _shared_operator_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "shared-operator-precedence":
            _shared_precedence_roles(result)
        elif fixture.name == "recursive-local-patterns":
            _recursive_local_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "computed-types-and-family-application":
            _computed_type_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "alias-and-effect-family-contracts":
            _family_contract_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "literal-patterns-and-dependent-branches":
            _literal_pattern_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "empty-dependent-elimination":
            _empty_elimination_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "local-grades-and-evaluation":
            _local_grade_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "local-grade-errors-remain-syntax":
            _local_grade_error_roles(result)
        elif fixture.name == "domain-dictionaries-and-product-laws":
            _domain_dictionary_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "disposal-clause-lifecycles":
            _disposal_clause_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "disposal-errors-remain-syntax":
            _disposal_error_roles(result)
        elif fixture.name == "generic-callable-annotation-composition":
            _generic_callable_annotation_roles(fixture.source.encode("utf-8"), result)
        elif fixture.name == "function-types-grades-and-contracts":
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
    _generic_probe_limits(parse)
    passed.append("surface:generic-probe-inspection-boundaries")
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
