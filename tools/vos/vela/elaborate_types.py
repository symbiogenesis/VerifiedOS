# SPDX-License-Identifier: Apache-2.0
"""Core terms, fixed-width integer specifications, bindings, and Gallina prelude for Vela elaboration."""

from dataclasses import dataclass, field

from vos.vela.ast import MAX_LITERAL_DIGITS

MAX_DEPTH = 128
MAX_WORK = 200_000
MAX_REDUCTIONS = 20_000
MAX_OUTPUT_BYTES = 4_194_304
MAX_UNIVERSE = 8
MAX_NAT_BITS = 4096
MAX_CONSTANT_NAT = 10 ** MAX_LITERAL_DIGITS - 1
MAX_PATTERN_NAT = 64
MAX_STRING_BYTES = 256


@dataclass(frozen=True)
class Elaboration:
    module: str
    gallina: str


type Node = dict[str, object]



@dataclass(frozen=True)
class _Term:
    kind: str
    value: str | int = ""
    args: tuple[_Term, ...] = ()


def _term(kind: str, *args: _Term, value: str | int = "") -> _Term:
    return _Term(kind, value, tuple(args))


def _app(function: _Term, argument: _Term) -> _Term:
    return _term("app", function, argument)


def _apps(function: _Term, *arguments: _Term) -> _Term:
    for argument in arguments:
        function = _app(function, argument)
    return function


def _constant(name: str) -> _Term:
    return _term("const", value=name)


_NAT = _constant("Nat")
_BOOL = _constant("bool")
_CHAR = _constant("char")
_UNIT = _constant("Unit")
_SORT = _term("sort", value=0)
_PROP = _term("sort", value=-1)


@dataclass(frozen=True)
class _IntSpec:
    name: str
    tag: int
    bits: int
    signed: bool
    min_val: int
    max_val: int
    const: _Term


_INT_SPECS: dict[str, _IntSpec] = {
    "u8": _IntSpec("u8", 0, 8, False, 0, (1 << 8) - 1, _constant("u8")),
    "u16": _IntSpec("u16", 1, 16, False, 0, (1 << 16) - 1, _constant("u16")),
    "u32": _IntSpec("u32", 2, 32, False, 0, (1 << 32) - 1, _constant("u32")),
    "u64": _IntSpec("u64", 3, 64, False, 0, (1 << 64) - 1, _constant("u64")),
    "usize": _IntSpec("usize", 4, 64, False, 0, (1 << 64) - 1, _constant("usize")),
    "i8": _IntSpec("i8", 5, 8, True, -(1 << 7), (1 << 7) - 1, _constant("i8")),
    "i16": _IntSpec("i16", 6, 16, True, -(1 << 15), (1 << 15) - 1, _constant("i16")),
    "i32": _IntSpec("i32", 7, 32, True, -(1 << 31), (1 << 31) - 1, _constant("i32")),
    "i64": _IntSpec("i64", 8, 64, True, -(1 << 63), (1 << 63) - 1, _constant("i64")),
}
_U8 = _INT_SPECS["u8"].const
_USIZE = _INT_SPECS["usize"].const
_NUMERICS_ALIASES: dict[str, str] = {
    "int": "i32",
    "uint": "u32",
    "long": "i64",
    "ulong": "u64",
}
_INT_INTRINSICS = {
    "ShiftLeft",
    "ShiftRight",
    "WrappingAdd",
    "WrappingSub",
    "WrappingMul",
    "WrappingNeg",
    "WrappingShiftLeft",
    "SaturatingAdd",
    "SaturatingSub",
    "SaturatingMul",
    "SaturatingNeg",
    "CheckedAdd",
    "CheckedSub",
    "CheckedMul",
    "CheckedNeg",
    "CheckedDiv",
    "CheckedRem",
    "CheckedShiftLeft",
    "CheckedShiftRight",
}


def _parse_numeric_magnitude(value: str) -> int:
    cleaned = value.replace("_", "")
    if cleaned.startswith(("0x", "0X")):
        return int(cleaned, 16)
    if cleaned.startswith(("0b", "0B")):
        return int(cleaned, 2)
    return int(cleaned, 10)


def _allows_from_conversion(src: _IntSpec, dst: _IntSpec) -> bool:
    if src.name == dst.name:
        return True
    if src.name == "usize" or dst.name == "usize":
        return dst.name == "usize" and src.name in {"u8", "u16", "u32"}
    return src.min_val >= dst.min_val and src.max_val <= dst.max_val


def _wrap_int(spec: _IntSpec, val: int) -> int:
    u = val & ((1 << spec.bits) - 1)
    if spec.signed and (u & (1 << (spec.bits - 1))):
        return u - (1 << spec.bits)
    return u


def _clamp_int(spec: _IntSpec, val: int) -> int:
    return min(spec.max_val, max(spec.min_val, val))


def _trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _trunc_rem(a: int, b: int) -> int:
    return a - _trunc_div(a, b) * b


def _int_term(spec: _IntSpec, value: int) -> _Term:
    return _term("int", spec.const, value=value)


@dataclass
class _Meta:
    type: _Term
    scope: frozenset[int]
    solution: _Term | None = None


@dataclass(frozen=True)
class _Binding:
    term: _Term
    type: _Term
    generics: int = 0
    constant: bool = False


@dataclass(frozen=True)
class _Pat:
    kind: str
    node: Node
    names: tuple[str, ...] = ()
    value: bool | str | int = False
    args: tuple[_Pat, ...] = ()


@dataclass(frozen=True)
class _Row:
    patterns: tuple[_Pat, ...]
    bindings: tuple[tuple[str, _Binding], ...]
    arm: Node
    arm_index: int = 0


@dataclass(frozen=True)
class _RecordField:
    name: str
    var: _Term
    type: _Term
    proj_const: str


@dataclass(frozen=True)
class _RecordProperty:
    name: str
    self_var: _Term
    type: _Term
    prop_const: str


@dataclass(frozen=True)
class _RecordInvariant:
    name: str
    self_var: _Term
    term: _Term
    type: _Term
    node: Node


@dataclass(frozen=True)
class _RecordMethod:
    name: str
    method_const: str
    binding: _Binding
    method_generics: int
    param_labels: tuple[str | None, ...]
    nullary: bool = False


@dataclass
class _RecordInfo:
    name: str
    type_const: str
    ctor_const: str
    type_binding: _Binding
    ctor_binding: _Binding
    generic_vars: tuple[_Term, ...]
    fields: tuple[_RecordField, ...]
    properties: dict[str, _RecordProperty]
    is_dependent: bool = False
    tail_sig_types: tuple[_Term, ...] = ()
    invariants: tuple[_RecordInvariant, ...] = ()
    methods: dict[str, _RecordMethod] = field(default_factory=dict)


@dataclass(frozen=True)
class _UnionCtor:
    name: str
    ctor_const: str
    ctor_binding: _Binding
    fields: tuple[_RecordField, ...]
    payload_type: _Term
    index: int
    is_dependent: bool = False
    tail_sig_types: tuple[_Term, ...] = ()


@dataclass(frozen=True)
class _UnionInfo:
    name: str
    type_const: str
    type_binding: _Binding
    generic_vars: tuple[_Term, ...]
    constructors: tuple[_UnionCtor, ...]
    suffix_types: tuple[_Term, ...]


@dataclass(frozen=True)
class _InterfaceMethodSpec:
    name: str
    method_generics: int
    generic_vars: tuple[_Term, ...]
    param_vars: tuple[_Term, ...]
    param_labels: tuple[str | None, ...]
    param_modifiers: tuple[str | None, ...]
    return_type: _Term
    signature: _Term
    self_var: _Term
    nullary: bool
    preconditions: tuple[tuple[tuple[int, ...], _Term], ...]
    ensures_clauses: tuple[Node, ...]
    ensures_props: tuple[_Term, ...]


@dataclass(frozen=True)
class _InterfaceLawSpec:
    name: str
    kind: str
    param_vars: tuple[_Term, ...]
    requires_clauses: tuple[Node, ...]
    ensures_clauses: tuple[Node, ...]
    req_props: tuple[_Term, ...]
    ensures_props: tuple[_Term, ...]


@dataclass(frozen=True)
class _InterfaceInfo:
    name: str
    generic_vars: tuple[_Term, ...]
    methods: dict[str, _InterfaceMethodSpec]
    laws: dict[str, _InterfaceLawSpec]


@dataclass(frozen=True)
class _ImplInstance:
    interface_name: str
    generic_vars: tuple[_Term, ...]
    target_types: tuple[_Term, ...]
    where_constraints: tuple[tuple[str, tuple[_Term, ...]], ...]
    methods: dict[str, _Binding]





_GALLINA = {
    "Nat": "Corelib.Init.Datatypes.nat", "bool": "Corelib.Init.Datatypes.bool",
    "char": "vela_char",
    "Unit": "Corelib.Init.Datatypes.unit", "Prop": "Prop",
    "char_eq": "vela_char_eq", "char_ne": "vela_char_ne",
    "char_lt": "vela_char_lt", "char_le": "vela_char_le",
    "char_gt": "vela_char_gt", "char_ge": "vela_char_ge",
    "char_to_nat": "vela_char_to_nat", "char_to_u32": "vela_char_to_u32",
    "char_from_u8": "vela_char_from_u8",
    "char_try_from_u32": "vela_char_try_from_u32",
    "char_try_from_Nat": "vela_char_try_from_Nat",
    "eq_unit": "vela_eq_unit", "ne_unit": "vela_ne_unit",
    "u8": "(vela_int (0 : Corelib.Init.Datatypes.nat))",
    "u16": "(vela_int (1 : Corelib.Init.Datatypes.nat))",
    "u32": "(vela_int (2 : Corelib.Init.Datatypes.nat))",
    "u64": "(vela_int (3 : Corelib.Init.Datatypes.nat))",
    "usize": "(vela_int (4 : Corelib.Init.Datatypes.nat))",
    "i8": "(vela_int (5 : Corelib.Init.Datatypes.nat))",
    "i16": "(vela_int (6 : Corelib.Init.Datatypes.nat))",
    "i32": "(vela_int (7 : Corelib.Init.Datatypes.nat))",
    "i64": "(vela_int (8 : Corelib.Init.Datatypes.nat))",
    "vela_ArithmeticError": "vela_ArithmeticError",
    "vela_ArithmeticError_Overflow": "vela_ArithmeticError_Overflow",
    "vela_ArithmeticError_ZeroDivisor": "vela_ArithmeticError_ZeroDivisor",
    "vela_ArithmeticError_InvalidShift": "vela_ArithmeticError_InvalidShift",
    "vela_ConversionError": "vela_ConversionError",
    "vela_ConversionError_OutOfRange": "vela_ConversionError_OutOfRange",
    "vela_Result": "vela_Result",
    "vela_Result_Ok": "vela_Result_Ok",
    "vela_Result_Err": "vela_Result_Err",
    "Succ": "Corelib.Init.Datatypes.S", "Eq": "Corelib.Init.Logic.eq",
    "Refl": "Corelib.Init.Logic.eq_refl", "Symm": "Corelib.Init.Logic.eq_sym",
    "Trans": "Corelib.Init.Logic.eq_trans", "Congr": "vela_Congr",
    "Fst": "Corelib.Init.Datatypes.fst", "Snd": "Corelib.Init.Datatypes.snd",
    "Vec": "vela_Vec", "VNil": "vela_VNil", "VCons": "vela_VCons", "ByteLength": "vela_ByteLength",
    "Vec_At_Nat": "vela_Vec_At_Nat", "Vec_Update": "vela_Vec_Update",
    "TextBuilder": "vela_TextBuilder", "TextBuilderVal": "vela_text_builder",
    "EmptyBuilder": "vela_EmptyBuilder", "FormatStep": "vela_FormatStep",
    "Fits": "vela_Fits", "Written": "vela_Written",
    "Fin": "vela_Fin", "FZero": "vela_FZero", "FSucc": "vela_FSucc", "At": "vela_At",
    "Span": "vela_Span",
    "Span_Base": "vela_Span_Base",
    "Span_Length": "vela_Span_Length",
    "Span_Tag": "vela_Span_Tag",
    "Span_PermRead": "vela_Span_PermRead",
    "Span_PermWrite": "vela_Span_PermWrite",
    "Span_CanRead": "vela_Span_CanRead",
    "Span_CanWrite": "vela_Span_CanWrite",
    "Span_AllocZeroed": "vela_Span_AllocZeroed",
    "Span_ReadOnly": "vela_Span_ReadOnly",
    "Span_Invalidate": "vela_Span_Invalidate",
    "Span_Disjoint": "vela_Span_Disjoint",
    "Span_Read": "vela_Span_Read",
    "Span_Write": "vela_Span_Write",
    "Span_Fill": "vela_Span_Fill",
    "Span_Slice": "vela_Span_Slice",
    "Span_CopyPrefix": "vela_Span_CopyPrefix",
    "Span_Restore": "vela_Span_Restore",
    "nat_to_usize": "vela_nat_to_usize",
    "Seq": "vela_Seq",
    "Seq_Empty": "vela_Seq_Empty",
    "Seq_Cons": "vela_Seq_Cons",
    "Seq_Singleton": "vela_Seq_Singleton",
    "Seq_Count": "vela_Seq_Count",
    "Seq_At": "vela_Seq_At",
    "Seq_Update": "vela_Seq_Update",
    "Seq_Append": "vela_Seq_Append",
    "Seq_Take": "vela_Seq_Take",
    "Seq_Skip": "vela_Seq_Skip",
    "Seq_Slice": "vela_Seq_Slice",
    "Seq_Contains": "vela_Seq_Contains",
    "Seq_All": "vela_Seq_All",
    "Seq_Any": "vela_Seq_Any",
    "Seq_Eq": "vela_Seq_Eq",
    "Vec_Model": "vela_Vec_Model",
    "Span_Model": "vela_Span_Model",
    "Slots": "vela_Slots",
    "Slots_Mk": "vela_Slots_Mk",
    "Slots_Base": "vela_Slots_Base",
    "Slots_LiveCount": "vela_Slots_LiveCount",
    "Slots_Tag": "vela_Slots_Tag",
    "Slots_PermRead": "vela_Slots_PermRead",
    "Slots_PermWrite": "vela_Slots_PermWrite",
    "Slots_CanRead": "vela_Slots_CanRead",
    "Slots_CanWrite": "vela_Slots_CanWrite",
    "Slots_RepModel": "vela_Slots_RepModel",
    "Slots_Model": "vela_Slots_Model",
    "Slots_AllocVacant": "vela_Slots_AllocVacant",
    "Slots_Write": "vela_Slots_Write",
    "Slots_Read": "vela_Slots_Read",
    "Slots_LivePrefix": "vela_Slots_LivePrefix",
    "Slots_VacantRange": "vela_Slots_VacantRange",
    "Slots_Disjoint": "vela_Slots_Disjoint",
    "Slots_RepEqual": "vela_Slots_RepEqual",
    "Slots_CopyRepresentation": "vela_Slots_CopyRepresentation",
    "Slots_TransferSource": "vela_Slots_TransferSource",
    "Slots_TransferDest": "vela_Slots_TransferDest",
    "Slots_TransferType": "vela_Slots_TransferType",
    "PrefixModel": "vela_PrefixModel",
    "LoopState": "vela_LoopState",
    "+": "Corelib.Init.Nat.add", "*": "Corelib.Init.Nat.mul", "-": "Corelib.Init.Nat.sub",
    "/": "Corelib.Init.Nat.div", "%": "Corelib.Init.Nat.modulo",
    "<=": "Corelib.Init.Nat.leb", "<": "Corelib.Init.Nat.ltb", ">=": "vela_ge", ">": "vela_gt",
    "eq_nat": "Corelib.Init.Nat.eqb", "ne_nat": "vela_ne_nat",
    "eq_bool": "vela_eq_bool", "ne_bool": "vela_ne_bool",
    "&&": "vela_and", "||": "vela_or", "!": "vela_not", "==>": "vela_implies", "<==>": "vela_eq_bool",
    **{
        f"int_{op}_{spec.name}": f"(vela_int_{op} ({spec.tag} : Corelib.Init.Datatypes.nat))"
        for spec in _INT_SPECS.values()
        for op in (
            "add", "sub", "mul", "div", "rem", "neg",
            "and", "or", "xor", "not",
            "shl", "shr", "eq", "ne", "lt", "le", "gt", "ge",
            "wrap_add", "wrap_sub", "wrap_mul", "wrap_neg", "wrap_shl",
            "sat_add", "sat_sub", "sat_mul", "sat_neg",
            "chk_add", "chk_sub", "chk_mul", "chk_div",
            "chk_rem", "chk_neg", "chk_shl", "chk_shr",
            "to_nat", "try_from_Nat",
        )
    },
    **{
        f"int_from_{src.name}_{dst.name}": (
            f"(vela_int_from ({src.tag} : Corelib.Init.Datatypes.nat) ({dst.tag} : Corelib.Init.Datatypes.nat))"
        )
        for src in _INT_SPECS.values()
        for dst in _INT_SPECS.values()
    },
    **{
        f"int_try_from_{src.name}_{dst.name}": (
            f"(vela_int_try_from ({src.tag} : Corelib.Init.Datatypes.nat) ({dst.tag} : Corelib.Init.Datatypes.nat))"
        )
        for src in _INT_SPECS.values()
        for dst in _INT_SPECS.values()
    },
}

_PRELUDE = """From Corelib Require Import Init.Datatypes Init.Nat Init.Logic Init.Specif.

Universe vela_u0 vela_u1 vela_u2 vela_u3 vela_u4 vela_u5 vela_u6 vela_u7 vela_u8 vela_u9.
Constraint vela_u0 < vela_u1.
Constraint vela_u1 < vela_u2.
Constraint vela_u2 < vela_u3.
Constraint vela_u3 < vela_u4.
Constraint vela_u4 < vela_u5.
Constraint vela_u5 < vela_u6.
Constraint vela_u6 < vela_u7.
Constraint vela_u7 < vela_u8.
Constraint vela_u8 < vela_u9.

Definition vela_not (a : bool) : bool := if a then false else true.
Definition vela_and (a b : bool) : bool := if a then b else false.
Definition vela_or (a b : bool) : bool := if a then true else b.
Definition vela_implies (a b : bool) : bool := if a then b else true.
Definition vela_eq_bool (a b : bool) : bool := if a then b else vela_not b.
Definition vela_ne_bool (a b : bool) : bool := vela_not (vela_eq_bool a b).
Definition vela_eq_unit (_ _ : unit) : bool := true.
Definition vela_ne_unit (_ _ : unit) : bool := false.
Definition vela_ne_nat (a b : nat) : bool := vela_not (Corelib.Init.Nat.eqb a b).
Definition vela_ge (a b : nat) : bool := Corelib.Init.Nat.leb b a.
Definition vela_gt (a b : nat) : bool := Corelib.Init.Nat.ltb b a.

Inductive vela_bits : Type@{vela_u0} :=
| vela_bnil : vela_bits
| vela_bcons : bool -> vela_bits -> vela_bits.

Abbreviation vela_0 x := (vela_bcons Corelib.Init.Datatypes.false x) (only parsing).
Abbreviation vela_1 x := (vela_bcons Corelib.Init.Datatypes.true x) (only parsing).
Abbreviation vela_x0 x := (vela_0 (vela_0 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_x1 x := (vela_0 (vela_0 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_x2 x := (vela_0 (vela_0 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_x3 x := (vela_0 (vela_0 (vela_1 (vela_1 x)))) (only parsing).
Abbreviation vela_x4 x := (vela_0 (vela_1 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_x5 x := (vela_0 (vela_1 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_x6 x := (vela_0 (vela_1 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_x7 x := (vela_0 (vela_1 (vela_1 (vela_1 x)))) (only parsing).
Abbreviation vela_x8 x := (vela_1 (vela_0 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_x9 x := (vela_1 (vela_0 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_xa x := (vela_1 (vela_0 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_xb x := (vela_1 (vela_0 (vela_1 (vela_1 x)))) (only parsing).
Abbreviation vela_xc x := (vela_1 (vela_1 (vela_0 (vela_0 x)))) (only parsing).
Abbreviation vela_xd x := (vela_1 (vela_1 (vela_0 (vela_1 x)))) (only parsing).
Abbreviation vela_xe x := (vela_1 (vela_1 (vela_1 (vela_0 x)))) (only parsing).
Abbreviation vela_xf x := (vela_1 (vela_1 (vela_1 (vela_1 x)))) (only parsing).

Inductive vela_int (tag : nat) : Type@{vela_u0} :=
| vela_mk_int : vela_bits -> vela_int tag.

Fixpoint vela_bits_eqb (a b : vela_bits) : bool :=
  match a, b with
  | vela_bnil, vela_bnil => true
  | vela_bcons x xs, vela_bcons y ys => vela_and (vela_eq_bool x y) (vela_bits_eqb xs ys)
  | _, _ => false
  end.

Definition vela_int_bits (tag : nat) (x : vela_int tag) : vela_bits :=
  match x with
  | vela_mk_int _ bs => bs
  end.

Definition vela_xorb (a b : bool) : bool := if a then vela_not b else b.

Fixpoint vela_bits_xor (a b : vela_bits) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys => vela_bcons (vela_xorb x y) (vela_bits_xor xs ys)
  | _, _ => vela_bnil
  end.

Fixpoint vela_bits_and (a b : vela_bits) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys => vela_bcons (vela_and x y) (vela_bits_and xs ys)
  | _, _ => vela_bnil
  end.

Fixpoint vela_bits_or (a b : vela_bits) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys => vela_bcons (vela_or x y) (vela_bits_or xs ys)
  | _, _ => vela_bnil
  end.

Fixpoint vela_bits_not (a : vela_bits) : vela_bits :=
  match a with
  | vela_bcons x xs => vela_bcons (vela_not x) (vela_bits_not xs)
  | vela_bnil => vela_bnil
  end.

Fixpoint vela_bits_ult (a b : vela_bits) : bool :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      if vela_eq_bool x y then vela_bits_ult xs ys else y
  | _, _ => false
  end.

Fixpoint vela_bits_ule (a b : vela_bits) : bool :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      if vela_eq_bool x y then vela_bits_ule xs ys else y
  | _, _ => true
  end.

Fixpoint vela_bits_rev_acc (a acc : vela_bits) : vela_bits :=
  match a with
  | vela_bnil => acc
  | vela_bcons x xs => vela_bits_rev_acc xs (vela_bcons x acc)
  end.

Definition vela_bits_rev (a : vela_bits) : vela_bits :=
  vela_bits_rev_acc a vela_bnil.

Fixpoint vela_bits_add_lsb (a b : vela_bits) (carry : bool) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      let sum := vela_xorb (vela_xorb x y) carry in
      let next_carry := vela_or (vela_and x y) (vela_and (vela_xorb x y) carry) in
      vela_bcons sum (vela_bits_add_lsb xs ys next_carry)
  | _, _ => vela_bnil
  end.

Definition vela_bits_add (a b : vela_bits) : vela_bits :=
  vela_bits_rev (vela_bits_add_lsb (vela_bits_rev a) (vela_bits_rev b) false).

Fixpoint vela_bits_sub_lsb (a b : vela_bits) (borrow : bool) : vela_bits :=
  match a, b with
  | vela_bcons x xs, vela_bcons y ys =>
      let diff := vela_xorb (vela_xorb x y) borrow in
      let next_borrow := vela_or (vela_and (vela_not x) y) (vela_and (vela_not (vela_xorb x y)) borrow) in
      vela_bcons diff (vela_bits_sub_lsb xs ys next_borrow)
  | _, _ => vela_bnil
  end.

Definition vela_bits_sub (a b : vela_bits) : vela_bits :=
  vela_bits_rev (vela_bits_sub_lsb (vela_bits_rev a) (vela_bits_rev b) false).

Definition vela_tag_bits (tag : nat) : nat :=
  match tag with
  | O => 8
  | S O => 16
  | S (S O) => 32
  | S (S (S O)) => 64
  | S (S (S (S O))) => 64
  | S (S (S (S (S O)))) => 8
  | S (S (S (S (S (S O))))) => 16
  | S (S (S (S (S (S (S O)))))) => 32
  | _ => 64
  end.

Definition vela_tag_signed (tag : nat) : bool :=
  Corelib.Init.Nat.leb 5 tag.

Fixpoint vela_bits_len (a : vela_bits) : nat :=
  match a with
  | vela_bnil => O
  | vela_bcons _ xs => S (vela_bits_len xs)
  end.

Fixpoint vela_bits_pad (n : nat) (fill : bool) (a : vela_bits) : vela_bits :=
  match n with
  | O => a
  | S k => vela_bcons fill (vela_bits_pad k fill a)
  end.

Definition vela_bits_head (a : vela_bits) : bool :=
  match a with
  | vela_bcons x _ => x
  | vela_bnil => false
  end.

Definition vela_bits_tail (a : vela_bits) : vela_bits :=
  match a with
  | vela_bcons _ xs => xs
  | vela_bnil => vela_bnil
  end.

Fixpoint vela_bits_snoc (a : vela_bits) (x : bool) : vela_bits :=
  match a with
  | vela_bnil => vela_bcons x vela_bnil
  | vela_bcons y ys => vela_bcons y (vela_bits_snoc ys x)
  end.

Fixpoint vela_bits_init (a : vela_bits) : vela_bits :=
  match a with
  | vela_bnil => vela_bnil
  | vela_bcons x xs =>
      match xs with
      | vela_bnil => vela_bnil
      | vela_bcons _ _ => vela_bcons x (vela_bits_init xs)
      end
  end.

Fixpoint vela_bits_fill (a : vela_bits) (b : bool) : vela_bits :=
  match a with
  | vela_bnil => vela_bnil
  | vela_bcons _ xs => vela_bcons b (vela_bits_fill xs b)
  end.

Definition vela_bits_zero_like (a : vela_bits) : vela_bits :=
  vela_bits_fill a false.

Definition vela_bits_is_zero (a : vela_bits) : bool :=
  vela_bits_eqb a (vela_bits_zero_like a).

Definition vela_bits_neg (a : vela_bits) : vela_bits :=
  vela_bits_sub (vela_bits_zero_like a) a.

Definition vela_bits_shl1 (a : vela_bits) : vela_bits :=
  match a with
  | vela_bnil => vela_bnil
  | vela_bcons _ xs => vela_bits_snoc xs false
  end.

Definition vela_bits_shr1 (fill : bool) (a : vela_bits) : vela_bits :=
  match a with
  | vela_bnil => vela_bnil
  | vela_bcons _ _ => vela_bcons fill (vela_bits_init a)
  end.

Fixpoint vela_bits_shl_n (k : nat) (a : vela_bits) : vela_bits :=
  match k with
  | O => a
  | S j => vela_bits_shl_n j (vela_bits_shl1 a)
  end.

Fixpoint vela_bits_shr_n (k : nat) (fill : bool) (a : vela_bits) : vela_bits :=
  match k with
  | O => a
  | S j => vela_bits_shr_n j fill (vela_bits_shr1 fill a)
  end.

Fixpoint vela_bits_mul_acc (b a acc : vela_bits) : vela_bits :=
  match b with
  | vela_bnil => acc
  | vela_bcons x xs =>
      let shifted := vela_bits_shl1 acc in
      vela_bits_mul_acc xs a (if x then vela_bits_add shifted a else shifted)
  end.

Definition vela_bits_mul (a b : vela_bits) : vela_bits :=
  vela_bits_mul_acc b a (vela_bits_zero_like a).

Fixpoint vela_bits_divmod_acc (n d r qrev : vela_bits) : @prod vela_bits vela_bits :=
  match n with
  | vela_bnil => @pair vela_bits vela_bits (vela_bits_rev qrev) r
  | vela_bcons x xs =>
      let shifted := vela_bits_snoc (vela_bits_tail r) x in
      if vela_bits_ule d shifted
      then vela_bits_divmod_acc xs d (vela_bits_sub shifted d) (vela_bcons true qrev)
      else vela_bits_divmod_acc xs d shifted (vela_bcons false qrev)
  end.

Definition vela_bits_udivmod (n d : vela_bits) : @prod vela_bits vela_bits :=
  let result :=
    vela_bits_divmod_acc n (vela_bcons false d) (vela_bcons false (vela_bits_zero_like n)) vela_bnil
  in
  @pair vela_bits vela_bits
    (@fst vela_bits vela_bits result) (vela_bits_tail (@snd vela_bits vela_bits result)).

Definition vela_bits_extend (signed : bool) (a : vela_bits) : vela_bits :=
  vela_bits_pad (vela_bits_len a) (vela_and signed (vela_bits_head a)) a.

Fixpoint vela_bits_take_lsb (n : nat) (fill : bool) (a : vela_bits) : vela_bits :=
  match n with
  | O => vela_bnil
  | S k =>
      match a with
      | vela_bnil => vela_bcons fill (vela_bits_take_lsb k fill vela_bnil)
      | vela_bcons x xs => vela_bcons x (vela_bits_take_lsb k fill xs)
      end
  end.

Definition vela_bits_resize (n : nat) (fill : bool) (a : vela_bits) : vela_bits :=
  vela_bits_rev (vela_bits_take_lsb n fill (vela_bits_rev a)).

Definition vela_bits_max (signed : bool) (a : vela_bits) : vela_bits :=
  if signed then vela_bcons false (vela_bits_fill (vela_bits_tail a) true) else vela_bits_fill a true.

Definition vela_bits_min (signed : bool) (a : vela_bits) : vela_bits :=
  if signed then vela_bcons true (vela_bits_zero_like (vela_bits_tail a)) else vela_bits_zero_like a.

Definition vela_bits_add_overflows (signed : bool) (a b sum : vela_bits) : bool :=
  if signed
  then vela_and (vela_eq_bool (vela_bits_head a) (vela_bits_head b))
                (vela_ne_bool (vela_bits_head sum) (vela_bits_head a))
  else vela_bits_ult sum a.

Definition vela_bits_sub_overflows (signed : bool) (a b diff : vela_bits) : bool :=
  if signed
  then vela_and (vela_ne_bool (vela_bits_head a) (vela_bits_head b))
                (vela_ne_bool (vela_bits_head diff) (vela_bits_head a))
  else vela_bits_ult a b.

Definition vela_bits_mul_overflows (signed : bool) (a b : vela_bits) : bool :=
  vela_not
    (vela_bits_eqb
      (vela_bits_extend signed (vela_bits_mul a b))
      (vela_bits_mul (vela_bits_extend signed a) (vela_bits_extend signed b))).

Fixpoint vela_bits_to_nat_acc (bs : vela_bits) (acc : nat) : nat :=
  match bs with
  | vela_bnil => acc
  | vela_bcons b rest =>
      vela_bits_to_nat_acc rest (Corelib.Init.Nat.add (Corelib.Init.Nat.mul 2 acc) (if b then 1 else 0))
  end.

Fixpoint vela_nat_to_bits_lsb (w n : nat) : vela_bits :=
  match w with
  | O => vela_bnil
  | S k => vela_bcons (Corelib.Init.Nat.odd n) (vela_nat_to_bits_lsb k (Corelib.Init.Nat.div2 n))
  end.

Definition vela_nat_to_bits (w n : nat) : vela_bits :=
  vela_bits_rev (vela_nat_to_bits_lsb w n).

Fixpoint vela_nat_shr_n (k n : nat) : nat :=
  match k with
  | O => n
  | S j => vela_nat_shr_n j (Corelib.Init.Nat.div2 n)
  end.

Definition vela_nat_fits (w n : nat) : bool :=
  Corelib.Init.Nat.eqb (vela_nat_shr_n w n) O.

Definition vela_ArithmeticError : Type@{vela_u0} :=
  @sum unit (@sum unit unit).
Definition vela_ArithmeticError_Overflow (_ : unit) : vela_ArithmeticError :=
  @inl unit (@sum unit unit) tt.
Definition vela_ArithmeticError_ZeroDivisor (_ : unit) : vela_ArithmeticError :=
  @inr unit (@sum unit unit) (@inl unit unit tt).
Definition vela_ArithmeticError_InvalidShift (_ : unit) : vela_ArithmeticError :=
  @inr unit (@sum unit unit) (@inr unit unit tt).

Definition vela_ConversionError : Type@{vela_u0} := unit.
Definition vela_ConversionError_OutOfRange (_ : unit) : vela_ConversionError := tt.

Definition vela_Result (TValue TError : Type@{vela_u0}) : Type@{vela_u0} :=
  @sum TError TValue.
Definition vela_Result_Err (TValue TError : Type@{vela_u0}) (e : TError) : vela_Result TValue TError :=
  @inl TError TValue e.
Definition vela_Result_Ok (TValue TError : Type@{vela_u0}) (v : TValue) : vela_Result TValue TError :=
  @inr TError TValue v.

Definition vela_int_add (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_add (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_sub (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_sub (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_negative (tag : nat) (bs : vela_bits) : bool :=
  vela_and (vela_tag_signed tag) (vela_bits_head bs).
Definition vela_int_magnitude (tag : nat) (bs : vela_bits) : vela_bits :=
  if vela_int_negative tag bs then vela_bits_neg bs else bs.
Definition vela_int_mul (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_mul (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_div (tag : nat) (a b : vela_int tag) : vela_int tag :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  if vela_bits_is_zero y then vela_mk_int tag (vela_bits_zero_like x) else
  let q := @fst vela_bits vela_bits
    (vela_bits_udivmod (vela_int_magnitude tag x) (vela_int_magnitude tag y)) in
  vela_mk_int tag
    (if vela_xorb (vela_int_negative tag x) (vela_int_negative tag y) then vela_bits_neg q else q).
Definition vela_int_rem (tag : nat) (a b : vela_int tag) : vela_int tag :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  if vela_bits_is_zero y then a else
  let r := @snd vela_bits vela_bits
    (vela_bits_udivmod (vela_int_magnitude tag x) (vela_int_magnitude tag y)) in
  vela_mk_int tag (if vela_int_negative tag x then vela_bits_neg r else r).
Definition vela_int_neg (tag : nat) (a : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_neg (vela_int_bits tag a)).
Definition vela_int_and (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_and (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_or (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_or (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_xor (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_xor (vela_int_bits tag a) (vela_int_bits tag b)).
Definition vela_int_not (tag : nat) (a : vela_int tag) : vela_int tag :=
  vela_mk_int tag (vela_bits_not (vela_int_bits tag a)).
Definition vela_shift_amount (tag : nat) (count : vela_int (4 : nat)) : option nat :=
  let c := vela_int_bits (4 : nat) count in
  if vela_bits_ult c (vela_nat_to_bits (vela_bits_len c) (vela_tag_bits tag))
  then Some (vela_bits_to_nat_acc c O)
  else None.
Definition vela_int_shl (tag : nat) (a : vela_int tag) (count : vela_int (4 : nat)) : vela_int tag :=
  let x := vela_int_bits tag a in
  match vela_shift_amount tag count with
  | Some k => vela_mk_int tag (vela_bits_shl_n k x)
  | None => vela_mk_int tag (vela_bits_zero_like x)
  end.
Definition vela_int_shr (tag : nat) (a : vela_int tag) (count : vela_int (4 : nat)) : vela_int tag :=
  let x := vela_int_bits tag a in
  let fill := vela_int_negative tag x in
  match vela_shift_amount tag count with
  | Some k => vela_mk_int tag (vela_bits_shr_n k fill x)
  | None => vela_mk_int tag (vela_bits_fill x fill)
  end.
Definition vela_int_eq (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_eqb (vela_int_bits tag a) (vela_int_bits tag b).
Definition vela_int_ne (tag : nat) (a b : vela_int tag) : bool :=
  vela_not (vela_int_eq tag a b).
Definition vela_int_key (tag : nat) (a : vela_int tag) : vela_bits :=
  let bs := vela_int_bits tag a in
  if vela_tag_signed tag
  then match bs with
       | vela_bcons msb rest => vela_bcons (vela_not msb) rest
       | vela_bnil => vela_bnil
       end
  else bs.
Definition vela_int_lt (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ult (vela_int_key tag a) (vela_int_key tag b).
Definition vela_int_le (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ule (vela_int_key tag a) (vela_int_key tag b).
Definition vela_int_gt (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ult (vela_int_key tag b) (vela_int_key tag a).
Definition vela_int_ge (tag : nat) (a b : vela_int tag) : bool :=
  vela_bits_ule (vela_int_key tag b) (vela_int_key tag a).
Definition vela_int_wrap_add (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_int_add tag a b.
Definition vela_int_wrap_sub (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_int_sub tag a b.
Definition vela_int_wrap_mul (tag : nat) (a b : vela_int tag) : vela_int tag :=
  vela_int_mul tag a b.
Definition vela_int_wrap_neg (tag : nat) (a : vela_int tag) : vela_int tag :=
  vela_int_neg tag a.
Definition vela_int_wrap_shl (tag : nat) (a : vela_int tag) (count : vela_int (4 : nat)) : vela_int tag :=
  vela_int_shl tag a count.
Definition vela_int_sat_add (tag : nat) (a b : vela_int tag) : vela_int tag :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  let s := vela_tag_signed tag in
  let r := vela_bits_add x y in
  vela_mk_int tag
    (if vela_bits_add_overflows s x y r
     then (if vela_int_negative tag x then vela_bits_min s x else vela_bits_max s x)
     else r).
Definition vela_int_sat_sub (tag : nat) (a b : vela_int tag) : vela_int tag :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  let s := vela_tag_signed tag in
  let r := vela_bits_sub x y in
  vela_mk_int tag
    (if vela_bits_sub_overflows s x y r
     then (if s then (if vela_bits_head x then vela_bits_min s x else vela_bits_max s x)
           else vela_bits_min s x)
     else r).
Definition vela_int_sat_mul (tag : nat) (a b : vela_int tag) : vela_int tag :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  let s := vela_tag_signed tag in
  vela_mk_int tag
    (if vela_bits_mul_overflows s x y
     then (if vela_xorb (vela_int_negative tag x) (vela_int_negative tag y)
           then vela_bits_min s x else vela_bits_max s x)
     else vela_bits_mul x y).
Definition vela_int_sat_neg (tag : nat) (a : vela_int tag) : vela_int tag :=
  let x := vela_int_bits tag a in
  let s := vela_tag_signed tag in
  vela_mk_int tag
    (if s
     then (if vela_bits_eqb x (vela_bits_min s x) then vela_bits_max s x else vela_bits_neg x)
     else vela_bits_zero_like x).
Definition vela_int_ok (tag : nat) (x : vela_bits) : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Ok (vela_int tag) vela_ArithmeticError (vela_mk_int tag x).
Definition vela_int_err (tag : nat) (e : vela_ArithmeticError)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  vela_Result_Err (vela_int tag) vela_ArithmeticError e.
Definition vela_int_chk_add (tag : nat) (a b : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  let r := vela_bits_add x y in
  if vela_bits_add_overflows (vela_tag_signed tag) x y r
  then vela_int_err tag (vela_ArithmeticError_Overflow tt)
  else vela_int_ok tag r.
Definition vela_int_chk_sub (tag : nat) (a b : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  let r := vela_bits_sub x y in
  if vela_bits_sub_overflows (vela_tag_signed tag) x y r
  then vela_int_err tag (vela_ArithmeticError_Overflow tt)
  else vela_int_ok tag r.
Definition vela_int_chk_mul (tag : nat) (a b : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  if vela_bits_mul_overflows (vela_tag_signed tag) x y
  then vela_int_err tag (vela_ArithmeticError_Overflow tt)
  else vela_int_ok tag (vela_bits_mul x y).
Definition vela_int_chk_div (tag : nat) (a b : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  let x := vela_int_bits tag a in
  let y := vela_int_bits tag b in
  let s := vela_tag_signed tag in
  if vela_bits_is_zero y then vela_int_err tag (vela_ArithmeticError_ZeroDivisor tt) else
  if vela_and s (vela_and (vela_bits_eqb x (vela_bits_min s x)) (vela_bits_eqb y (vela_bits_fill y true)))
  then vela_int_err tag (vela_ArithmeticError_Overflow tt)
  else vela_Result_Ok (vela_int tag) vela_ArithmeticError (vela_int_div tag a b).
Definition vela_int_chk_rem (tag : nat) (a b : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  if vela_bits_is_zero (vela_int_bits tag b)
  then vela_int_err tag (vela_ArithmeticError_ZeroDivisor tt)
  else vela_Result_Ok (vela_int tag) vela_ArithmeticError (vela_int_rem tag a b).
Definition vela_int_chk_neg (tag : nat) (a : vela_int tag)
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  let x := vela_int_bits tag a in
  let s := vela_tag_signed tag in
  if (if s then vela_bits_eqb x (vela_bits_min s x) else vela_not (vela_bits_is_zero x))
  then vela_int_err tag (vela_ArithmeticError_Overflow tt)
  else vela_int_ok tag (vela_bits_neg x).
Definition vela_int_chk_shl (tag : nat) (a : vela_int tag) (count : vela_int (4 : nat))
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  let x := vela_int_bits tag a in
  match vela_shift_amount tag count with
  | None => vela_int_err tag (vela_ArithmeticError_InvalidShift tt)
  | Some k =>
      let r := vela_bits_shl_n k x in
      if vela_bits_eqb (vela_bits_shr_n k (vela_int_negative tag r) r) x
      then vela_int_ok tag r
      else vela_int_err tag (vela_ArithmeticError_Overflow tt)
  end.
Definition vela_int_chk_shr (tag : nat) (a : vela_int tag) (count : vela_int (4 : nat))
    : vela_Result (vela_int tag) vela_ArithmeticError :=
  match vela_shift_amount tag count with
  | None => vela_int_err tag (vela_ArithmeticError_InvalidShift tt)
  | Some _ => vela_Result_Ok (vela_int tag) vela_ArithmeticError (vela_int_shr tag a count)
  end.
Definition vela_int_to_nat (tag : nat) (a : vela_int tag) : nat :=
  let bs := vela_int_bits tag a in
  if vela_int_negative tag bs then O else vela_bits_to_nat_acc bs O.
Definition vela_int_from (src dst : nat) (x : vela_int src) : vela_int dst :=
  let bs := vela_int_bits src x in
  vela_mk_int dst (vela_bits_resize (vela_tag_bits dst) (vela_int_negative src bs) bs).
Definition vela_int_try_from (src dst : nat) (x : vela_int src)
    : vela_Result (vela_int dst) vela_ConversionError :=
  let c := vela_int_from src dst x in
  if vela_and
       (vela_int_eq src (vela_int_from dst src c) x)
       (vela_eq_bool (vela_int_negative src (vela_int_bits src x)) (vela_int_negative dst (vela_int_bits dst c)))
  then vela_Result_Ok (vela_int dst) vela_ConversionError c
  else vela_Result_Err (vela_int dst) vela_ConversionError (vela_ConversionError_OutOfRange tt).
Definition vela_int_try_from_Nat (dst : nat) (n : nat)
    : vela_Result (vela_int dst) vela_ConversionError :=
  let w := vela_tag_bits dst in
  if vela_nat_fits (if vela_tag_signed dst then Corelib.Init.Nat.pred w else w) n
  then vela_Result_Ok (vela_int dst) vela_ConversionError (vela_mk_int dst (vela_nat_to_bits w n))
  else vela_Result_Err (vela_int dst) vela_ConversionError (vela_ConversionError_OutOfRange tt).

Inductive vela_char : Type@{vela_u0} :=
| vela_mk_char : nat -> vela_char.

Definition vela_char_code (c : vela_char) : nat :=
  match c with
  | vela_mk_char n => n
  end.

Definition vela_char_eq (a b : vela_char) : bool :=
  Corelib.Init.Nat.eqb (vela_char_code a) (vela_char_code b).
Definition vela_char_ne (a b : vela_char) : bool :=
  vela_not (vela_char_eq a b).
Definition vela_char_lt (a b : vela_char) : bool :=
  Corelib.Init.Nat.ltb (vela_char_code a) (vela_char_code b).
Definition vela_char_le (a b : vela_char) : bool :=
  Corelib.Init.Nat.leb (vela_char_code a) (vela_char_code b).
Definition vela_char_gt (a b : vela_char) : bool :=
  Corelib.Init.Nat.ltb (vela_char_code b) (vela_char_code a).
Definition vela_char_ge (a b : vela_char) : bool :=
  Corelib.Init.Nat.leb (vela_char_code b) (vela_char_code a).
Definition vela_char_to_nat (c : vela_char) : nat :=
  vela_char_code c.
Definition vela_char_to_u32 (c : vela_char) : vela_int (2 : nat) :=
  vela_mk_int (2 : nat) (vela_nat_to_bits 32 (vela_char_code c)).
Definition vela_char_from_u8 (b : vela_int (0 : nat)) : vela_char :=
  vela_mk_char (vela_bits_to_nat_acc (vela_int_bits (0 : nat) b) O).
Definition vela_char_scalar_bits (bs : vela_bits) : bool :=
  vela_and
    (vela_bits_ule bs (vela_x0 (vela_x0 (vela_x1 (vela_x0 (vela_xf (vela_xf (vela_xf (vela_xf vela_bnil)))))))))
    (vela_or
      (vela_bits_ult bs (vela_x0 (vela_x0 (vela_x0 (vela_x0 (vela_xd (vela_x8 (vela_x0 (vela_x0 vela_bnil)))))))))
      (vela_bits_ult (vela_x0 (vela_x0 (vela_x0 (vela_x0 (vela_xd (vela_xf (vela_xf (vela_xf vela_bnil)))))))) bs)).
Definition vela_char_try_from_u32 (v : vela_int (2 : nat))
    : vela_Result vela_char vela_ConversionError :=
  let bs := vela_int_bits (2 : nat) v in
  if vela_char_scalar_bits bs
  then vela_Result_Ok vela_char vela_ConversionError (vela_mk_char (vela_bits_to_nat_acc bs O))
  else vela_Result_Err vela_char vela_ConversionError (vela_ConversionError_OutOfRange tt).
Definition vela_char_try_from_Nat (n : nat)
    : vela_Result vela_char vela_ConversionError :=
  if vela_and (vela_nat_fits 32 n) (vela_char_scalar_bits (vela_nat_to_bits 32 n))
  then vela_Result_Ok vela_char vela_ConversionError (vela_mk_char n)
  else vela_Result_Err vela_char vela_ConversionError (vela_ConversionError_OutOfRange tt).

Definition vela_u8_zero : vela_int (0 : nat) :=
  vela_mk_int (0 : nat) (vela_bits_pad 8 false vela_bnil).

Definition vela_in_extent (addr base len : vela_int (4 : nat)) : bool :=
  vela_and
    (vela_int_le (4 : nat) base addr)
    (vela_int_lt (4 : nat) addr (vela_int_add (4 : nat) base len)).

Inductive vela_ByteStore : Type@{vela_u0} :=
| vela_bs_empty : vela_ByteStore
| vela_bs_fill : vela_int (4 : nat) -> vela_int (4 : nat) -> vela_int (0 : nat) -> vela_ByteStore -> vela_ByteStore
| vela_bs_write : vela_int (4 : nat) -> vela_int (0 : nat) -> vela_ByteStore -> vela_ByteStore
| vela_bs_copy : vela_int (4 : nat) -> vela_int (4 : nat) -> vela_int (4 : nat) -> vela_ByteStore -> vela_ByteStore -> vela_ByteStore.

Fixpoint vela_store_lookup (st : vela_ByteStore) (addr : vela_int (4 : nat)) {struct st} : vela_int (0 : nat) :=
  match st with
  | vela_bs_empty => vela_u8_zero
  | vela_bs_fill base len val rest =>
      if vela_in_extent addr base len then val else vela_store_lookup rest addr
  | vela_bs_write waddr val rest =>
      if vela_int_eq (4 : nat) addr waddr then val else vela_store_lookup rest addr
  | vela_bs_copy dbase sbase count src_st rest =>
      if vela_in_extent addr dbase count then
        vela_store_lookup src_st (vela_int_add (4 : nat) sbase (vela_int_sub (4 : nat) addr dbase))
      else
        vela_store_lookup rest addr
  end.

Inductive vela_Span (A : Type@{vela_u0}) : Type@{vela_u0} :=
| vela_mk_span :
    vela_int (4 : nat) ->
    vela_int (4 : nat) ->
    bool ->
    bool ->
    bool ->
    vela_ByteStore ->
    vela_Span A.

Definition vela_Span_Base (A : Type@{vela_u0}) (s : vela_Span A) : vela_int (4 : nat) :=
  match s with
  | vela_mk_span _ base _ _ _ _ _ => base
  end.

Definition vela_Span_Length (A : Type@{vela_u0}) (s : vela_Span A) : vela_int (4 : nat) :=
  match s with
  | vela_mk_span _ _ len _ _ _ _ => len
  end.

Definition vela_Span_Tag (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  match s with
  | vela_mk_span _ _ _ tag _ _ _ => tag
  end.

Definition vela_Span_PermRead (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  match s with
  | vela_mk_span _ _ _ _ pr _ _ => pr
  end.

Definition vela_Span_PermWrite (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  match s with
  | vela_mk_span _ _ _ _ _ pw _ => pw
  end.

Definition vela_Span_Store (A : Type@{vela_u0}) (s : vela_Span A) : vela_ByteStore :=
  match s with
  | vela_mk_span _ _ _ _ _ _ st => st
  end.

Definition vela_Span_CanRead (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  vela_and (vela_Span_Tag A s) (vela_Span_PermRead A s).

Definition vela_Span_CanWrite (A : Type@{vela_u0}) (s : vela_Span A) : bool :=
  vela_and (vela_Span_Tag A s) (vela_Span_PermWrite A s).

Definition vela_Span_AllocZeroed (A : Type@{vela_u0}) (base cap : vela_int (4 : nat)) : vela_Span A :=
  vela_mk_span A base cap true true true vela_bs_empty.

Definition vela_Span_ReadOnly (A : Type@{vela_u0}) (s : vela_Span A) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    false
    (vela_Span_Store A s).

Definition vela_Span_Invalidate (A : Type@{vela_u0}) (s : vela_Span A) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    false
    false
    false
    (vela_Span_Store A s).

Definition vela_Span_Disjoint (A : Type@{vela_u0}) (a b : vela_Span A) : bool :=
  vela_or
    (vela_int_le (4 : nat)
      (vela_int_add (4 : nat) (vela_Span_Base A a) (vela_Span_Length A a))
      (vela_Span_Base A b))
    (vela_int_le (4 : nat)
      (vela_int_add (4 : nat) (vela_Span_Base A b) (vela_Span_Length A b))
      (vela_Span_Base A a)).

Definition vela_Span_Read (A : Type@{vela_u0}) (s : vela_Span A) (idx : vela_int (4 : nat)) : vela_int (0 : nat) :=
  vela_store_lookup (vela_Span_Store A s) (vela_int_add (4 : nat) (vela_Span_Base A s) idx).

Definition vela_Span_Write (A : Type@{vela_u0}) (s : vela_Span A) (idx : vela_int (4 : nat)) (val : vela_int (0 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    (vela_Span_PermWrite A s)
    (vela_bs_write (vela_int_add (4 : nat) (vela_Span_Base A s) idx) val (vela_Span_Store A s)).

Definition vela_Span_Fill (A : Type@{vela_u0}) (s : vela_Span A) (off count : vela_int (4 : nat)) (val : vela_int (0 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A s)
    (vela_Span_Length A s)
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    (vela_Span_PermWrite A s)
    (vela_bs_fill (vela_int_add (4 : nat) (vela_Span_Base A s) off) count val (vela_Span_Store A s)).

Definition vela_Span_Slice (A : Type@{vela_u0}) (s : vela_Span A) (off count : vela_int (4 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_int_add (4 : nat) (vela_Span_Base A s) off)
    count
    (vela_Span_Tag A s)
    (vela_Span_PermRead A s)
    (vela_Span_PermWrite A s)
    (vela_Span_Store A s).

Definition vela_Span_CopyPrefix (A : Type@{vela_u0}) (dst src : vela_Span A) (count : vela_int (4 : nat)) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A dst)
    (vela_Span_Length A dst)
    (vela_Span_Tag A dst)
    (vela_Span_PermRead A dst)
    (vela_Span_PermWrite A dst)
    (vela_bs_copy (vela_Span_Base A dst) (vela_Span_Base A src) count (vela_Span_Store A src) (vela_Span_Store A dst)).

Definition vela_Span_Restore (A : Type@{vela_u0}) (parent view : vela_Span A) : vela_Span A :=
  vela_mk_span A
    (vela_Span_Base A parent)
    (vela_Span_Length A parent)
    (vela_Span_Tag A parent)
    (vela_Span_PermRead A parent)
    (vela_Span_PermWrite A parent)
    (vela_Span_Store A view).

Definition vela_Congr (A B : Type@{vela_u0}) (x y : A) (f : A -> B)
    (p : @Corelib.Init.Logic.eq A x y) : @Corelib.Init.Logic.eq B (f x) (f y) :=
  @Corelib.Init.Logic.f_equal A B f x y p.

Fixpoint vela_Vec (A : Type@{vela_u0}) (n : nat) {struct n} : Type@{vela_u0} :=
  match n with
  | O => unit
  | S k => @prod A (vela_Vec A k)
  end.
Definition vela_VNil (A : Type@{vela_u0}) (_ : unit) : vela_Vec A O := tt.
Definition vela_VCons (A : Type@{vela_u0}) (n : nat) (x : A) (xs : vela_Vec A n)
    : vela_Vec A (S n) := @pair A (vela_Vec A n) x xs.

Inductive vela_Fin : nat -> Type@{vela_u0} :=
| vela_fzero : forall n : nat, vela_Fin (S n)
| vela_fsucc : forall n : nat, vela_Fin n -> vela_Fin (S n).
Definition vela_FZero (n : nat) (_ : unit) : vela_Fin (S n) := vela_fzero n.
Definition vela_FSucc (n : nat) (i : vela_Fin n) : vela_Fin (S n) := vela_fsucc n i.
Fixpoint vela_lookup (A : Type@{vela_u0}) (n : nat) (i : vela_Fin n) {struct i}
    : vela_Vec A n -> A :=
  match i in vela_Fin size return vela_Vec A size -> A with
  | vela_fzero k => fun v => @fst A (vela_Vec A k) v
  | vela_fsucc k j => fun v => vela_lookup A k j (@snd A (vela_Vec A k) v)
  end.
Definition vela_At (A : Type@{vela_u0}) (n : nat) (xs : vela_Vec A n) (i : vela_Fin n)
    : A := vela_lookup A n i xs.
Fixpoint vela_Vec_At_Nat (A : Type@{vela_u0}) (n : nat) (d : A) (idx : nat) {struct n}
    : vela_Vec A n -> A :=
  match n return vela_Vec A n -> A with
  | O => fun _ => d
  | S k => fun v =>
      match idx with
      | O => @fst A (vela_Vec A k) v
      | S j => vela_Vec_At_Nat A k d j (@snd A (vela_Vec A k) v)
      end
  end.
Fixpoint vela_Vec_Update (A : Type@{vela_u0}) (n : nat) (idx : nat) (val : A) {struct n}
    : vela_Vec A n -> vela_Vec A n :=
  match n return vela_Vec A n -> vela_Vec A n with
  | O => fun v => v
  | S k => fun v =>
      match idx with
      | O => @pair A (vela_Vec A k) val (@snd A (vela_Vec A k) v)
      | S j => @pair A (vela_Vec A k) (@fst A (vela_Vec A k) v) (vela_Vec_Update A k j val (@snd A (vela_Vec A k) v))
      end
  end.
Definition vela_ByteLength (n : nat) (_ : vela_Vec nat n) : nat := n.

Inductive vela_TextBuilder (capacity : nat) : Type@{vela_u0} :=
| vela_text_builder : bool -> nat -> vela_TextBuilder capacity.
Definition vela_EmptyBuilder (capacity : nat) (_ : unit) : vela_TextBuilder capacity :=
  vela_text_builder capacity true O.
Definition vela_FormatStep (capacity : nat) (builder : vela_TextBuilder capacity) (chunk : nat)
    : vela_TextBuilder capacity :=
  match builder with
  | vela_text_builder _ ok used =>
      vela_text_builder capacity
        (vela_and ok (Corelib.Init.Nat.leb (Corelib.Init.Nat.add used chunk) capacity))
        (Corelib.Init.Nat.add used chunk)
  end.
Definition vela_Fits (capacity : nat) (builder : vela_TextBuilder capacity) : bool :=
  match builder with
  | vela_text_builder _ ok _ => ok
  end.
Definition vela_Written (capacity : nat) (builder : vela_TextBuilder capacity) : nat :=
  match builder with
  | vela_text_builder _ _ used => used
  end.

Definition vela_nat_to_usize (n : nat) : vela_int (4 : nat) :=
  vela_mk_int (4 : nat) (vela_nat_to_bits 64 n).

Inductive vela_Seq (A : Type@{vela_u0}) : Type@{vela_u0} :=
| vela_Seq_Empty : vela_Seq A
| vela_Seq_Cons : A -> vela_Seq A -> vela_Seq A.

Definition vela_Seq_Singleton (A : Type@{vela_u0}) (x : A) : vela_Seq A :=
  vela_Seq_Cons A x (vela_Seq_Empty A).

Fixpoint vela_Seq_Count (A : Type@{vela_u0}) (s : vela_Seq A) {struct s} : nat :=
  match s with
  | vela_Seq_Empty _ => O
  | vela_Seq_Cons _ _ xs => S (vela_Seq_Count A xs)
  end.

Fixpoint vela_Seq_At (A : Type@{vela_u0}) (d : A) (s : vela_Seq A) (idx : nat) {struct s} : A :=
  match s with
  | vela_Seq_Empty _ => d
  | vela_Seq_Cons _ x xs =>
      match idx with
      | O => x
      | S k => vela_Seq_At A d xs k
      end
  end.

Fixpoint vela_Seq_Update (A : Type@{vela_u0}) (s : vela_Seq A) (idx : nat) (val : A) {struct s} : vela_Seq A :=
  match s with
  | vela_Seq_Empty _ => vela_Seq_Empty A
  | vela_Seq_Cons _ x xs =>
      match idx with
      | O => vela_Seq_Cons A val xs
      | S k => vela_Seq_Cons A x (vela_Seq_Update A xs k val)
      end
  end.

Fixpoint vela_Seq_Append (A : Type@{vela_u0}) (a b : vela_Seq A) {struct a} : vela_Seq A :=
  match a with
  | vela_Seq_Empty _ => b
  | vela_Seq_Cons _ x xs => vela_Seq_Cons A x (vela_Seq_Append A xs b)
  end.

Fixpoint vela_Seq_Take (A : Type@{vela_u0}) (s : vela_Seq A) (n : nat) {struct n} : vela_Seq A :=
  match n with
  | O => vela_Seq_Empty A
  | S k =>
      match s with
      | vela_Seq_Empty _ => vela_Seq_Empty A
      | vela_Seq_Cons _ x xs => vela_Seq_Cons A x (vela_Seq_Take A xs k)
      end
  end.

Fixpoint vela_Seq_Skip (A : Type@{vela_u0}) (s : vela_Seq A) (n : nat) {struct n} : vela_Seq A :=
  match n with
  | O => s
  | S k =>
      match s with
      | vela_Seq_Empty _ => vela_Seq_Empty A
      | vela_Seq_Cons _ _ xs => vela_Seq_Skip A xs k
      end
  end.

Definition vela_Seq_Slice (A : Type@{vela_u0}) (s : vela_Seq A) (off cnt : nat) : vela_Seq A :=
  vela_Seq_Take A (vela_Seq_Skip A s off) cnt.

Definition vela_Seq_Contains (A : Type@{vela_u0}) (s : vela_Seq A) (_ : A) : bool :=
  match s with
  | vela_Seq_Empty _ => false
  | vela_Seq_Cons _ _ _ => true
  end.

Fixpoint vela_Seq_All (A : Type@{vela_u0}) (s : vela_Seq A) (p : A -> bool) {struct s} : bool :=
  match s with
  | vela_Seq_Empty _ => true
  | vela_Seq_Cons _ x xs => vela_and (p x) (vela_Seq_All A xs p)
  end.

Fixpoint vela_Seq_Any (A : Type@{vela_u0}) (s : vela_Seq A) (p : A -> bool) {struct s} : bool :=
  match s with
  | vela_Seq_Empty _ => false
  | vela_Seq_Cons _ x xs => vela_or (p x) (vela_Seq_Any A xs p)
  end.

Fixpoint vela_Seq_Eq (A : Type@{vela_u0}) (eqA : A -> A -> bool) (a b : vela_Seq A) {struct a} : bool :=
  match a, b with
  | vela_Seq_Empty _, vela_Seq_Empty _ => true
  | vela_Seq_Cons _ x xs, vela_Seq_Cons _ y ys => vela_and (eqA x y) (vela_Seq_Eq A eqA xs ys)
  | _, _ => false
  end.

Fixpoint vela_Vec_Model (A : Type@{vela_u0}) (n : nat) {struct n} : vela_Vec A n -> vela_Seq A :=
  match n return vela_Vec A n -> vela_Seq A with
  | O => fun _ => vela_Seq_Empty A
  | S k => fun v => vela_Seq_Cons A (@fst A (vela_Vec A k) v) (vela_Vec_Model A k (@snd A (vela_Vec A k) v))
  end.

Definition vela_Span_Model (A : Type@{vela_u0}) (_ : vela_Span A) : vela_Seq (vela_int (0 : nat)) :=
  vela_Seq_Empty (vela_int (0 : nat)).

Inductive vela_Slots (A : Type@{vela_u0}) (cap : nat) : Type@{vela_u0} :=
| vela_Slots_Mk :
    vela_int (4 : nat) ->
    vela_int (4 : nat) ->
    bool ->
    bool ->
    bool ->
    vela_Seq A ->
    vela_Seq A ->
    vela_Slots A cap.

Definition vela_Slots_Base (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_int (4 : nat) :=
  match s with
  | vela_Slots_Mk _ _ base _ _ _ _ _ _ => base
  end.

Definition vela_Slots_LiveCount (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_int (4 : nat) :=
  match s with
  | vela_Slots_Mk _ _ _ live _ _ _ _ _ => live
  end.

Definition vela_Slots_Tag (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  match s with
  | vela_Slots_Mk _ _ _ _ tag _ _ _ _ => tag
  end.

Definition vela_Slots_PermRead (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ pr _ _ _ => pr
  end.

Definition vela_Slots_PermWrite (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ _ pw _ _ => pw
  end.

Definition vela_Slots_RepModel (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_Seq A :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ _ _ rep _ => rep
  end.

Definition vela_Slots_Model (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : vela_Seq A :=
  match s with
  | vela_Slots_Mk _ _ _ _ _ _ _ _ m => m
  end.

Definition vela_Slots_CanRead (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  vela_and (vela_Slots_Tag A cap s) (vela_Slots_PermRead A cap s).

Definition vela_Slots_CanWrite (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) : bool :=
  vela_and (vela_Slots_Tag A cap s) (vela_Slots_PermWrite A cap s).

Definition vela_Slots_AllocVacant (A : Type@{vela_u0}) (cap : nat) (base : vela_int (4 : nat)) : vela_Slots A cap :=
  vela_Slots_Mk A cap base (vela_nat_to_usize O) true true true (vela_Seq_Empty A) (vela_Seq_Empty A).

Definition vela_Slots_Write (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (idx : vela_int (4 : nat)) (val : A)
    : vela_Slots A cap :=
  vela_Slots_Mk A cap
    (vela_Slots_Base A cap s)
    idx
    (vela_Slots_Tag A cap s)
    (vela_Slots_PermRead A cap s)
    (vela_Slots_PermWrite A cap s)
    (vela_Seq_Singleton A val)
    (vela_Seq_Singleton A val).

Definition vela_Slots_Read (A : Type@{vela_u0}) (cap : nat) (d : A) (s : vela_Slots A cap) (idx : vela_int (4 : nat)) : A :=
  vela_Seq_At A d (vela_Slots_Model A cap s) (vela_int_to_nat (4 : nat) idx).

Definition vela_Slots_LivePrefix (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (cnt : vela_int (4 : nat)) : bool :=
  vela_int_eq (4 : nat) (vela_Slots_LiveCount A cap s) cnt.

Definition vela_Slots_VacantRange (A : Type@{vela_u0}) (cap : nat) (_ : vela_Slots A cap) (start stop : vela_int (4 : nat)) : bool :=
  vela_int_le (4 : nat) start stop.

Definition vela_Slots_Disjoint (A : Type@{vela_u0}) (n m : nat) (a : vela_Slots A n) (b : vela_Slots A m) : bool :=
  vela_int_ne (4 : nat) (vela_Slots_Base A n a) (vela_Slots_Base A m b).

Definition vela_Slots_RepEqual (A : Type@{vela_u0}) (n m : nat) (_ : vela_Slots A n) (_ : vela_Slots A m) (_ : vela_int (4 : nat)) : bool :=
  true.

Definition vela_Slots_CopyRepresentation (A : Type@{vela_u0}) (n m : nat) (src : vela_Slots A n) (dst : vela_Slots A m) (_ : vela_int (4 : nat))
    : vela_Slots A m :=
  vela_Slots_Mk A m
    (vela_Slots_Base A m dst)
    (vela_nat_to_usize O)
    (vela_Slots_Tag A m dst)
    (vela_Slots_PermRead A m dst)
    (vela_Slots_PermWrite A m dst)
    (vela_Slots_Model A n src)
    (vela_Seq_Empty A).

Definition vela_Slots_TransferSource (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (_ : vela_int (4 : nat))
    : vela_Slots A cap :=
  vela_Slots_Mk A cap
    (vela_Slots_Base A cap s)
    (vela_nat_to_usize O)
    (vela_Slots_Tag A cap s)
    (vela_Slots_PermRead A cap s)
    (vela_Slots_PermWrite A cap s)
    (vela_Seq_Empty A)
    (vela_Seq_Empty A).

Definition vela_Slots_TransferDest (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (cnt : vela_int (4 : nat))
    : vela_Slots A cap :=
  vela_Slots_Mk A cap
    (vela_Slots_Base A cap s)
    cnt
    (vela_Slots_Tag A cap s)
    (vela_Slots_PermRead A cap s)
    (vela_Slots_PermWrite A cap s)
    (vela_Slots_RepModel A cap s)
    (vela_Slots_RepModel A cap s).

Definition vela_Slots_TransferType (A : Type@{vela_u0}) (n m : nat) (src : vela_Slots A n) (dst : vela_Slots A m) (cnt : vela_int (4 : nat))
    : @prod (vela_Slots A n) (vela_Slots A m) :=
  @pair (vela_Slots A n) (vela_Slots A m)
    (vela_Slots_TransferSource A n src cnt)
    (vela_Slots_TransferDest A m dst cnt).

Definition vela_PrefixModel (A : Type@{vela_u0}) (cap : nat) (s : vela_Slots A cap) (_ : vela_int (4 : nat)) : vela_Seq A :=
  vela_Slots_Model A cap s.

Definition vela_LoopState (A : Type@{vela_u0}) (x : A) (_ : nat) : A := x.
"""

