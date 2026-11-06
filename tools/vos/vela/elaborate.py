# SPDX-License-Identifier: Apache-2.0
"""Bounded, untrusted elaboration of mathematical Vela into existing CIC terms.

The surface parser owns syntax. This consumer checks its exact-source protocol,
then proposes terms for independent kernel checking; it supplies neither checked
parsing nor an independent source semantics. Vec is a recursive product family,
Fin an indexed inductive, and lookup recurses structurally on the finite index.
"""

import hashlib
from collections.abc import Callable, Sequence
from typing import cast

from vos.vela import StaticEvaluation
from vos.vela.ast import ValueType, VelaError
from vos.vela.elaborate_declarations import _DeclarationsMixin
from vos.vela.elaborate_intrinsics import _IntrinsicsMixin
from vos.vela.elaborate_patterns import _PatternsMixin
from vos.vela.elaborate_proofs import _ProofsMixin
from vos.vela.elaborate_protocol import (
    _IDENTIFIER,
    _OPERATORS,
    _Protocol,
)
from vos.vela.elaborate_solver import _SolverMixin
from vos.vela.elaborate_statements import _StatementsMixin
from vos.vela.elaborate_strings import _StringsMixin
from vos.vela.elaborate_types import (
    _BOOL,
    _CHAR,
    _INT_SPECS,
    _NAT,
    _NUMERICS_ALIASES,
    _PRELUDE,
    _PROP,
    _SORT,
    _U8,
    _UNIT,
    _USIZE,
    MAX_CONSTANT_NAT,
    MAX_DEPTH,
    MAX_NAT_BITS,
    MAX_OUTPUT_BYTES,
    MAX_PATTERN_NAT,
    MAX_REDUCTIONS,
    MAX_STRING_BYTES,
    MAX_UNIVERSE,
    MAX_WORK,
    Elaboration,
    Node,
    _app,
    _apps,
    _Binding,
    _constant,
    _ImplInstance,
    _int_term,
    _InterfaceInfo,
    _IntSpec,
    _Meta,
    _parse_numeric_magnitude,
    _RecordField,
    _RecordInfo,
    _Term,
    _term,
    _UnionCtor,
    _UnionInfo,
)
from vos.vela.elaborate_whnf import _WhnfMixin

__all__ = [
    "MAX_CONSTANT_NAT",
    "MAX_DEPTH",
    "MAX_NAT_BITS",
    "MAX_OUTPUT_BYTES",
    "MAX_PATTERN_NAT",
    "MAX_REDUCTIONS",
    "MAX_STRING_BYTES",
    "MAX_UNIVERSE",
    "MAX_WORK",
    "Elaboration",
    "Node",
    "_Elaborator",
    "_Protocol",
    "_checked_elaboration",
    "elaborate",
    "elaborate_package",
    "evaluate",
]


class _Elaborator(
    _WhnfMixin,
    _PatternsMixin,
    _ProofsMixin,
    _StatementsMixin,
    _StringsMixin,
    _SolverMixin,
    _IntrinsicsMixin,
    _DeclarationsMixin,
):
    def __init__(self, protocol: _Protocol) -> None:
        self.protocol = protocol
        self.serial = 0
        self.work = MAX_WORK
        self.reductions = MAX_REDUCTIONS
        self.metas: list[_Meta] = []
        self.decl_first_meta = 0
        self.whnf_cache: dict[int, tuple[_Term, _Term]] = {}
        self.types: dict[int, _Term] = {}
        # Callable parameter labels are source metadata, never CIC constructors.
        self.parameter_names: dict[int, str] = {}
        self.nullary_parameters: set[int] = set()
        self.constant_parameters: set[int] = set()
        self.readonly_span_vars: set[int] = set()
        self.ref_parameters: set[int] = set()
        self.out_parameters: set[int] = set()
        self.out_param_names: set[str] = set()
        self.uninitialized_out_params: set[str] = set()
        self.callable_ref_updates: dict[str, tuple[tuple[int, ...], dict[int, _Term]]] = {}
        self.callable_ensures: dict[
            str, list[tuple[tuple[int, ...], tuple[tuple[int, int], ...], int | None, _Term]]
        ] = {}
        self.last_call_updates: list[tuple[Node, _Binding]] = []
        self.static_forbidden: set[int] | None = None
        self.globals: dict[str, _Binding] = {}
        self.constants: dict[str, _Binding] = {}
        self.definitions: dict[str, _Term] = {}
        self.records: dict[str, _RecordInfo] = {}
        self.records_by_type: dict[str, _RecordInfo] = {}
        self.records_by_ctor: dict[str, _RecordInfo] = {}
        self.record_projections: dict[str, tuple[_RecordInfo, int]] = {}
        self.unions: dict[str, _UnionInfo] = {}
        self.unions_by_type: dict[str, _UnionInfo] = {}
        self.union_ctors: dict[str, tuple[_UnionInfo, _UnionCtor]] = {}
        self.unions_by_ctor: dict[str, tuple[_UnionInfo, _UnionCtor]] = {}
        self.interfaces: dict[str, _InterfaceInfo] = {}
        self.impls: dict[str, list[_ImplInstance]] = {}
        self.active_interface_witnesses: dict[tuple[str, tuple[_Term, ...]], dict[str, _Binding]] = {}
        self.active_interface_ensures: dict[tuple[str, tuple[_Term, ...]], dict[str, tuple[tuple[int, ...], tuple[_Term, ...]]]] = {}
        self.callable_where_constraints: dict[str, tuple[tuple[int, ...], tuple[tuple[str, tuple[_Term, ...]], ...]]] = {}
        self.var_preconditions: dict[int, list[tuple[tuple[int, ...], _Term]]] = {}
        self.expected_call_type: _Term | None = None
        self.module_name: str = ""
        self.public_symbols: set[str] = set()
        self.private_symbols: set[str] = set()
        self.available_modules: dict[str, _Elaborator] = {}
        self.imported_modules: set[str] = set()
        self.inaccessible_private_symbols: dict[str, str] = {}
        self.builtin_unions: set[str] = {"Result", "ArithmeticError", "ConversionError"}
        self.builtin_union_ctors: set[str] = {
            "Err", "Ok", "Overflow", "ZeroDivisor", "InvalidShift", "OutOfRange",
        }
        self.active_facts: list[_Term] = []
        self.callable_preconditions: dict[str, list[tuple[tuple[int, ...], _Term]]] = {}
        self.fix_names: dict[int, str] = {}
        self.current_rec_var: _Term | None = None
        self.current_rec_name: str | None = None
        self.current_rec_generics: list[_Term] = []
        self.current_rec_params: list[_Term] = []
        self.current_rec_witnesses: list[_Term] = []
        self.current_rec_candidates: list[tuple[int, int]] = []
        self.current_rec_used: bool = False
        self.smaller_vars: dict[int, set[int]] = {}
        self.current_return_type: _Term | None = None
        self.mutable_locals: set[str] = set()
        self.entry_env: dict[str, _Binding] = {}
        self.final_ref_bindings: dict[str, _Binding] = {}
        self.final_return_facts: list[_Term] = []
        self.in_post_env_theorem: bool = False
        self.used_domain_solver_in_proof: bool = False
        self.final_theorem_facts: tuple[_Binding, ...] = ()
        self.frozen_collections: set[str] = set()
        self.lifted_invariants: dict[str, set[str]] = {}
        self.active_lift_scopes: int = 0
        self.in_loop_depth: int = 0
        self.output: list[str] = []
        self.site: Node | None = None
        self._builtins()

    def fail(self, kind: str, message: str, node: Node | None = None) -> VelaError:
        return self.protocol.error(kind, message, self.site if node is None else node)

    def tick(self, reduction: bool = False) -> None:
        self.work -= 1
        if reduction:
            self.reductions -= 1
        if self.work < 0 or self.reductions < 0:
            raise self.fail("limit", "elaboration work or definitional reduction budget exhausted")

    def fresh(self, value_type: _Term) -> _Term:
        index = self.serial
        self.serial += 1
        self.types[index] = value_type
        return _term("var", value=index)

    def pi(self, domain: _Term, codomain: _Term, *, nullary: bool = False) -> _Term:
        variable = self.fresh(domain)
        if nullary:
            self.nullary_parameters.add(cast("int", variable.value))
        return _term("pi", domain, codomain, value=variable.value)

    def _builtins(self) -> None:
        def bind(name: str, value_type: _Term, generics: int = 0) -> None:
            self.globals[name] = _Binding(_constant(name), value_type, generics)
            self.constants[name] = self.globals[name]

        for name in ("Nat", "bool", "char", "Unit"):
            bind(name, _SORT)
        for spec in _INT_SPECS.values():
            bind(spec.name, _SORT)
        self.globals["byte"] = self.globals["u8"]
        for alias_name, target_name in _NUMERICS_ALIASES.items():
            self.globals[f"Vela.Numerics.{alias_name}"] = self.globals[target_name]
        bind("Prop", _SORT)
        bind("Succ", self.pi(_NAT, _NAT))
        a = self.fresh(_SORT)
        b = self.fresh(_SORT)
        n = self.fresh(_NAT)
        x = self.fresh(a)
        y = self.fresh(a)
        z = self.fresh(a)

        def telescope(parameters: tuple[_Term, ...], result: _Term) -> _Term:
            for parameter in reversed(parameters):
                result = _term("pi", self.types[cast("int", parameter.value)], result, value=parameter.value)
            return result

        def eq(left: _Term, right: _Term) -> _Term:
            return _apps(_constant("Eq"), a, left, right)

        bind("Eq", telescope((a, x, y), _PROP), 1)
        self.constants["Refl"] = _Binding(_constant("Refl"), telescope((a, x), eq(x, x)), 1)
        self.constants["Symm"] = _Binding(
            _constant("Symm"), telescope((a, x, y), self.pi(eq(x, y), eq(y, x))), 3
        )
        self.constants["Trans"] = _Binding(
            _constant("Trans"), telescope((a, x, y, z), self.pi(eq(x, y), self.pi(eq(y, z), eq(x, z)))), 4
        )
        f = self.fresh(self.pi(a, b))
        congr_result = _apps(_constant("Eq"), b, _app(f, x), _app(f, y))
        self.constants["Congr"] = _Binding(
            _constant("Congr"), telescope((a, b, x, y, f), self.pi(eq(x, y), congr_result)), 4
        )
        bind("Fst", telescope((a, b), self.pi(_term("prod", a, b), a)), 2)
        bind("Snd", telescope((a, b), self.pi(_term("prod", a, b), b)), 2)
        bind("Vec", telescope((a, n), _SORT))
        bind("Fin", telescope((n,), _SORT))
        vec = _apps(_constant("Vec"), a, n)
        fin = _app(_constant("Fin"), n)
        successor = _app(_constant("Succ"), n)
        bind("VNil", telescope((a,), self.pi(_UNIT, _apps(_constant("Vec"), a, _term("nat", value=0)), nullary=True)), 1)
        bind("VCons", telescope((a, n), self.pi(a, self.pi(vec, _apps(_constant("Vec"), a, successor)))), 2)
        bind("FZero", telescope((n,), self.pi(_UNIT, _app(_constant("Fin"), successor), nullary=True)), 1)
        bind("FSucc", telescope((n,), self.pi(fin, _app(_constant("Fin"), successor))), 1)
        bind("At", telescope((a, n), self.pi(vec, self.pi(fin, a))), 2)
        self.constants["Vec_At_Nat"] = _Binding(
            _constant("Vec_At_Nat"), telescope((a, n), self.pi(a, self.pi(_NAT, self.pi(vec, a)))), 2
        )
        self.constants["Vec_Update"] = _Binding(
            _constant("Vec_Update"), telescope((a, n), self.pi(_NAT, self.pi(a, self.pi(vec, vec)))), 2
        )
        vec_nat = _apps(_constant("Vec"), _NAT, n)
        tb = _app(_constant("TextBuilder"), n)
        bind("ByteLength", telescope((n,), self.pi(vec_nat, _NAT)), 1)
        bind("TextBuilder", telescope((n,), _SORT))
        bind("EmptyBuilder", telescope((n,), self.pi(_UNIT, tb, nullary=True)), 1)
        bind("Fits", telescope((n,), self.pi(tb, _BOOL)), 1)
        bind("Written", telescope((n,), self.pi(tb, _NAT)), 1)
        self.constants["TextBuilderVal"] = _Binding(
            _constant("TextBuilderVal"), telescope((n,), self.pi(_BOOL, self.pi(_NAT, tb))), 1
        )
        self.constants["FormatStep"] = _Binding(
            _constant("FormatStep"), telescope((n,), self.pi(tb, self.pi(_NAT, tb))), 1
        )
        for name in ("+", "*", "-", "/", "%"):
            bind(name, self.pi(_NAT, self.pi(_NAT, _NAT)))
        for name in ("<=", "<", ">=", ">"):
            bind(name, self.pi(_NAT, self.pi(_NAT, _BOOL)))
        for name in ("&&", "||", "==>", "<==>"):
            bind(name, self.pi(_BOOL, self.pi(_BOOL, _BOOL)))
        bind("!", self.pi(_BOOL, _BOOL))
        for name, domain in (
            ("eq_nat", _NAT),
            ("ne_nat", _NAT),
            ("eq_bool", _BOOL),
            ("ne_bool", _BOOL),
            ("eq_unit", _UNIT),
            ("ne_unit", _UNIT),
            ("char_eq", _CHAR),
            ("char_ne", _CHAR),
            ("char_lt", _CHAR),
            ("char_le", _CHAR),
            ("char_gt", _CHAR),
            ("char_ge", _CHAR),
        ):
            bind(name, self.pi(domain, self.pi(domain, _BOOL)))
        self.constants["char_to_nat"] = _Binding(_constant("char_to_nat"), self.pi(_CHAR, _NAT))
        self.constants["char_to_u32"] = _Binding(
            _constant("char_to_u32"), self.pi(_CHAR, _INT_SPECS["u32"].const)
        )
        self.constants["char_from_u8"] = _Binding(_constant("char_from_u8"), self.pi(_U8, _CHAR))
        bind("Span", telescope((a,), _SORT))
        span_a = _app(_constant("Span"), a)
        self.constants["Span_Base"] = _Binding(_constant("Span_Base"), telescope((a,), self.pi(span_a, _USIZE)), 1)
        self.constants["Span_Length"] = _Binding(_constant("Span_Length"), telescope((a,), self.pi(span_a, _USIZE)), 1)
        self.constants["Span_Tag"] = _Binding(_constant("Span_Tag"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_PermRead"] = _Binding(_constant("Span_PermRead"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_PermWrite"] = _Binding(_constant("Span_PermWrite"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_CanRead"] = _Binding(_constant("Span_CanRead"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_CanWrite"] = _Binding(_constant("Span_CanWrite"), telescope((a,), self.pi(span_a, _BOOL)), 1)
        self.constants["Span_AllocZeroed"] = _Binding(
            _constant("Span_AllocZeroed"),
            telescope((a,), self.pi(_USIZE, self.pi(_USIZE, span_a))),
            1,
        )
        self.constants["Span_ReadOnly"] = _Binding(
            _constant("Span_ReadOnly"),
            telescope((a,), self.pi(span_a, span_a)),
            1,
        )
        self.constants["Span_Invalidate"] = _Binding(
            _constant("Span_Invalidate"),
            telescope((a,), self.pi(span_a, span_a)),
            1,
        )
        self.constants["Span_Disjoint"] = _Binding(
            _constant("Span_Disjoint"),
            telescope((a,), self.pi(span_a, self.pi(span_a, _BOOL))),
            1,
        )
        self.constants["Span_Read"] = _Binding(
            _constant("Span_Read"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, a))),
            1,
        )
        self.constants["Span_Write"] = _Binding(
            _constant("Span_Write"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, self.pi(a, span_a)))),
            1,
        )
        self.constants["Span_Fill"] = _Binding(
            _constant("Span_Fill"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, self.pi(_USIZE, self.pi(a, span_a))))),
            1,
        )
        self.constants["Span_Slice"] = _Binding(
            _constant("Span_Slice"),
            telescope((a,), self.pi(span_a, self.pi(_USIZE, self.pi(_USIZE, span_a)))),
            1,
        )
        self.constants["Span_CopyPrefix"] = _Binding(
            _constant("Span_CopyPrefix"),
            telescope((a,), self.pi(span_a, self.pi(span_a, self.pi(_USIZE, span_a)))),
            1,
        )
        self.constants["Span_Restore"] = _Binding(
            _constant("Span_Restore"),
            telescope((a,), self.pi(span_a, self.pi(span_a, span_a))),
            1,
        )
        bind("Seq", telescope((a,), _SORT))
        seq_a = _app(_constant("Seq"), a)
        self.constants["Seq_Empty"] = _Binding(_constant("Seq_Empty"), telescope((a,), seq_a), 1)
        self.constants["Seq_Cons"] = _Binding(
            _constant("Seq_Cons"), telescope((a,), self.pi(a, self.pi(seq_a, seq_a))), 1
        )
        self.constants["Seq_Singleton"] = _Binding(
            _constant("Seq_Singleton"), telescope((a,), self.pi(a, seq_a)), 1
        )
        self.constants["Seq_Count"] = _Binding(
            _constant("Seq_Count"), telescope((a,), self.pi(seq_a, _NAT)), 1
        )
        self.constants["Seq_At"] = _Binding(
            _constant("Seq_At"), telescope((a,), self.pi(a, self.pi(seq_a, self.pi(_NAT, a)))), 1
        )
        self.constants["Seq_Update"] = _Binding(
            _constant("Seq_Update"), telescope((a,), self.pi(seq_a, self.pi(_NAT, self.pi(a, seq_a)))), 1
        )
        self.constants["Seq_Append"] = _Binding(
            _constant("Seq_Append"), telescope((a,), self.pi(seq_a, self.pi(seq_a, seq_a))), 1
        )
        self.constants["Seq_Take"] = _Binding(
            _constant("Seq_Take"), telescope((a,), self.pi(seq_a, self.pi(_NAT, seq_a))), 1
        )
        self.constants["Seq_Skip"] = _Binding(
            _constant("Seq_Skip"), telescope((a,), self.pi(seq_a, self.pi(_NAT, seq_a))), 1
        )
        self.constants["Seq_Slice"] = _Binding(
            _constant("Seq_Slice"), telescope((a,), self.pi(seq_a, self.pi(_NAT, self.pi(_NAT, seq_a)))), 1
        )
        self.constants["Seq_Contains"] = _Binding(
            _constant("Seq_Contains"), telescope((a,), self.pi(seq_a, self.pi(a, _BOOL))), 1
        )
        self.constants["Seq_All"] = _Binding(
            _constant("Seq_All"), telescope((a,), self.pi(seq_a, self.pi(self.pi(a, _BOOL), _BOOL))), 1
        )
        self.constants["Seq_Any"] = _Binding(
            _constant("Seq_Any"), telescope((a,), self.pi(seq_a, self.pi(self.pi(a, _BOOL), _BOOL))), 1
        )
        self.constants["Seq_Eq"] = _Binding(
            _constant("Seq_Eq"),
            telescope((a,), self.pi(self.pi(a, self.pi(a, _BOOL)), self.pi(seq_a, self.pi(seq_a, _BOOL)))),
            1,
        )
        self.constants["nat_to_usize"] = _Binding(
            _constant("nat_to_usize"), self.pi(_NAT, _USIZE), 0
        )
        self.constants["Vec_Model"] = _Binding(
            _constant("Vec_Model"), telescope((a, n), self.pi(vec, seq_a)), 2
        )
        self.constants["Span_Model"] = _Binding(
            _constant("Span_Model"), telescope((a,), self.pi(span_a, _app(_constant("Seq"), _U8))), 1
        )
        bind("Slots", telescope((a, n), _SORT))
        slots_an = _apps(_constant("Slots"), a, n)
        m = self.fresh(_NAT)
        slots_am = _apps(_constant("Slots"), a, m)
        self.constants["Slots_Mk"] = _Binding(
            _constant("Slots_Mk"),
            telescope(
                (a, n),
                self.pi(
                    _USIZE,
                    self.pi(
                        _USIZE,
                        self.pi(
                            _BOOL,
                            self.pi(_BOOL, self.pi(_BOOL, self.pi(seq_a, self.pi(seq_a, slots_an)))),
                        ),
                    ),
                ),
            ),
            2,
        )
        self.constants["Slots_Base"] = _Binding(
            _constant("Slots_Base"), telescope((a, n), self.pi(slots_an, _USIZE)), 2
        )
        self.constants["Slots_LiveCount"] = _Binding(
            _constant("Slots_LiveCount"), telescope((a, n), self.pi(slots_an, _USIZE)), 2
        )
        self.constants["Slots_Tag"] = _Binding(
            _constant("Slots_Tag"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_PermRead"] = _Binding(
            _constant("Slots_PermRead"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_PermWrite"] = _Binding(
            _constant("Slots_PermWrite"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_CanRead"] = _Binding(
            _constant("Slots_CanRead"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_CanWrite"] = _Binding(
            _constant("Slots_CanWrite"), telescope((a, n), self.pi(slots_an, _BOOL)), 2
        )
        self.constants["Slots_RepModel"] = _Binding(
            _constant("Slots_RepModel"), telescope((a, n), self.pi(slots_an, seq_a)), 2
        )
        self.constants["Slots_Model"] = _Binding(
            _constant("Slots_Model"), telescope((a, n), self.pi(slots_an, seq_a)), 2
        )
        self.constants["Slots_AllocVacant"] = _Binding(
            _constant("Slots_AllocVacant"), telescope((a, n), self.pi(_USIZE, slots_an)), 2
        )
        self.constants["Slots_Write"] = _Binding(
            _constant("Slots_Write"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, self.pi(a, slots_an)))),
            2,
        )
        self.constants["Slots_Read"] = _Binding(
            _constant("Slots_Read"),
            telescope((a, n), self.pi(a, self.pi(slots_an, self.pi(_USIZE, a)))),
            2,
        )
        self.constants["Slots_LivePrefix"] = _Binding(
            _constant("Slots_LivePrefix"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, _BOOL))),
            2,
        )
        self.constants["Slots_VacantRange"] = _Binding(
            _constant("Slots_VacantRange"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, self.pi(_USIZE, _BOOL)))),
            2,
        )
        self.constants["Slots_Disjoint"] = _Binding(
            _constant("Slots_Disjoint"),
            telescope((a, n, m), self.pi(slots_an, self.pi(slots_am, _BOOL))),
            3,
        )
        self.constants["Slots_RepEqual"] = _Binding(
            _constant("Slots_RepEqual"),
            telescope((a, n, m), self.pi(slots_an, self.pi(slots_am, self.pi(_USIZE, _BOOL)))),
            3,
        )
        self.constants["Slots_CopyRepresentation"] = _Binding(
            _constant("Slots_CopyRepresentation"),
            telescope((a, n, m), self.pi(slots_an, self.pi(slots_am, self.pi(_USIZE, slots_am)))),
            3,
        )
        self.constants["Slots_TransferSource"] = _Binding(
            _constant("Slots_TransferSource"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, slots_an))),
            2,
        )
        self.constants["Slots_TransferDest"] = _Binding(
            _constant("Slots_TransferDest"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, slots_an))),
            2,
        )
        self.constants["Slots_TransferType"] = _Binding(
            _constant("Slots_TransferType"),
            telescope(
                (a, n, m),
                self.pi(slots_an, self.pi(slots_am, self.pi(_USIZE, _term("prod", slots_an, slots_am)))),
            ),
            3,
        )
        self.constants["PrefixModel"] = _Binding(
            _constant("PrefixModel"),
            telescope((a, n), self.pi(slots_an, self.pi(_USIZE, seq_a))),
            2,
        )
        self.constants["LoopState"] = _Binding(
            _constant("LoopState"),
            telescope((a,), self.pi(a, self.pi(_NAT, a))),
            1,
        )
        self._register_builtin_unions()
        self._register_int_constants()

    def _register_builtin_unions(self) -> None:
        # ArithmeticError { Overflow(); ZeroDivisor(); InvalidShift(); }
        ae_type_const = "vela_ArithmeticError"
        ae_rep_type = _term("sum", _UNIT, _term("sum", _UNIT, _UNIT))
        ae_type_binding = _Binding(_constant(ae_type_const), _SORT, 0)
        self.globals["ArithmeticError"] = ae_type_binding
        self.constants[ae_type_const] = ae_type_binding
        ae_ctors: list[_UnionCtor] = []
        for idx, cname in enumerate(("Overflow", "ZeroDivisor", "InvalidShift")):
            c_const = f"vela_ArithmeticError_{cname}"
            u_var = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", u_var.value))
            c_sig = _term("pi", _UNIT, _constant(ae_type_const), value=u_var.value)
            c_binding = _Binding(_constant(c_const), c_sig, 0)
            self.globals[cname] = c_binding
            self.constants[c_const] = c_binding
            ae_ctors.append(_UnionCtor(cname, c_const, c_binding, (), _UNIT, idx))
        ae_info = _UnionInfo(
            "ArithmeticError",
            ae_type_const,
            ae_type_binding,
            (),
            tuple(ae_ctors),
            (ae_rep_type, _term("sum", _UNIT, _UNIT), _UNIT),
        )
        self.unions["ArithmeticError"] = ae_info
        self.unions_by_type[ae_type_const] = ae_info
        for uc in ae_ctors:
            self.union_ctors[uc.name] = (ae_info, uc)
            self.unions_by_ctor[uc.ctor_const] = (ae_info, uc)

        # ConversionError { OutOfRange(); }
        ce_type_const = "vela_ConversionError"
        ce_type_binding = _Binding(_constant(ce_type_const), _SORT, 0)
        self.globals["ConversionError"] = ce_type_binding
        self.constants[ce_type_const] = ce_type_binding
        oor_const = "vela_ConversionError_OutOfRange"
        oor_u = self.fresh(_UNIT)
        self.nullary_parameters.add(cast("int", oor_u.value))
        oor_sig = _term("pi", _UNIT, _constant(ce_type_const), value=oor_u.value)
        oor_binding = _Binding(_constant(oor_const), oor_sig, 0)
        self.globals["OutOfRange"] = oor_binding
        self.constants[oor_const] = oor_binding
        oor_ctor = _UnionCtor("OutOfRange", oor_const, oor_binding, (), _UNIT, 0)
        ce_info = _UnionInfo(
            "ConversionError",
            ce_type_const,
            ce_type_binding,
            (),
            (oor_ctor,),
            (_UNIT,),
        )
        self.unions["ConversionError"] = ce_info
        self.unions_by_type[ce_type_const] = ce_info
        self.union_ctors["OutOfRange"] = (ce_info, oor_ctor)
        self.unions_by_ctor[oor_const] = (ce_info, oor_ctor)

        # Result<TValue, TError> { Err(TError Error); Ok(TValue Value); }
        res_type_const = "vela_Result"
        tv_var = self.fresh(_SORT)
        te_var = self.fresh(_SORT)
        res_rep = _term("sum", te_var, tv_var)
        res_sig = self.wrap("pi", [tv_var, te_var], _SORT)
        res_type_binding = _Binding(_constant(res_type_const), res_sig, 2)
        self.globals["Result"] = res_type_binding
        self.constants[res_type_const] = res_type_binding
        res_app = _apps(_constant(res_type_const), tv_var, te_var)

        err_fvar = self.fresh(te_var)
        self.parameter_names[cast("int", err_fvar.value)] = "Error"
        err_const = "vela_Result_Err"
        err_sig = self.wrap("pi", [tv_var, te_var, err_fvar], res_app)
        err_binding = _Binding(_constant(err_const), err_sig, 2)
        self.globals["Err"] = err_binding
        self.constants[err_const] = err_binding
        err_ctor = _UnionCtor(
            "Err", err_const, err_binding, (_RecordField("Error", err_fvar, te_var, ""),), te_var, 0
        )

        ok_fvar = self.fresh(tv_var)
        self.parameter_names[cast("int", ok_fvar.value)] = "Value"
        ok_const = "vela_Result_Ok"
        ok_sig = self.wrap("pi", [tv_var, te_var, ok_fvar], res_app)
        ok_binding = _Binding(_constant(ok_const), ok_sig, 2)
        self.globals["Ok"] = ok_binding
        self.constants[ok_const] = ok_binding
        ok_ctor = _UnionCtor(
            "Ok", ok_const, ok_binding, (_RecordField("Value", ok_fvar, tv_var, ""),), tv_var, 1
        )

        res_info = _UnionInfo(
            "Result",
            res_type_const,
            res_type_binding,
            (tv_var, te_var),
            (err_ctor, ok_ctor),
            (res_rep, tv_var),
        )
        self.unions["Result"] = res_info
        self.unions_by_type[res_type_const] = res_info
        self.union_ctors["Err"] = (res_info, err_ctor)
        self.union_ctors["Ok"] = (res_info, ok_ctor)
        self.unions_by_ctor[err_const] = (res_info, err_ctor)
        self.unions_by_ctor[ok_const] = (res_info, ok_ctor)

    def _register_int_constants(self) -> None:
        ae_const = _constant(self.unions["ArithmeticError"].type_const)
        ce_const = _constant(self.unions["ConversionError"].type_const)
        res_const = _constant(self.unions["Result"].type_const)
        res_char_conv = _apps(res_const, _CHAR, ce_const)
        self.constants["char_try_from_u32"] = _Binding(
            _constant("char_try_from_u32"), self.pi(_INT_SPECS["u32"].const, res_char_conv)
        )
        self.constants["char_try_from_Nat"] = _Binding(
            _constant("char_try_from_Nat"), self.pi(_NAT, res_char_conv)
        )
        for spec in _INT_SPECS.values():
            t = spec.const
            res_arith = _apps(res_const, t, ae_const)
            res_conv = _apps(res_const, t, ce_const)
            for op in (
                "add", "sub", "mul", "div", "rem", "and", "or", "xor",
                "wrap_add", "wrap_sub", "wrap_mul", "sat_add", "sat_sub", "sat_mul",
            ):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(t, t)))
            for op in ("neg", "not", "wrap_neg", "sat_neg"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, t))
            for op in ("eq", "ne", "lt", "le", "gt", "ge"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(t, _BOOL)))
            for op in ("shl", "shr", "wrap_shl"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(_USIZE, t)))
            for op in ("chk_add", "chk_sub", "chk_mul", "chk_div", "chk_rem"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(t, res_arith)))
            cname_cneg = f"int_chk_neg_{spec.name}"
            self.constants[cname_cneg] = _Binding(_constant(cname_cneg), self.pi(t, res_arith))
            for op in ("chk_shl", "chk_shr"):
                cname = f"int_{op}_{spec.name}"
                self.constants[cname] = _Binding(_constant(cname), self.pi(t, self.pi(_USIZE, res_arith)))
            cname_nat = f"int_to_nat_{spec.name}"
            self.constants[cname_nat] = _Binding(_constant(cname_nat), self.pi(t, _NAT))
            cname_tf_nat = f"int_try_from_Nat_{spec.name}"
            self.constants[cname_tf_nat] = _Binding(_constant(cname_tf_nat), self.pi(_NAT, res_conv))
            for src in _INT_SPECS.values():
                cname_from = f"int_from_{src.name}_{spec.name}"
                self.constants[cname_from] = _Binding(_constant(cname_from), self.pi(src.const, t))
                cname_tf = f"int_try_from_{src.name}_{spec.name}"
                self.constants[cname_tf] = _Binding(_constant(cname_tf), self.pi(src.const, res_conv))

    def _int_spec(self, type_term: _Term) -> _IntSpec | None:
        resolved = self.whnf(type_term)
        if resolved.kind == "const" and isinstance(resolved.value, str):
            return _INT_SPECS.get(resolved.value)
        return None

    def meta(self, value_type: _Term, environment: dict[str, _Binding]) -> _Term:
        index = len(self.metas)
        scope: set[int] = set()
        for binding in environment.values():
            scope.update(self.free(binding.term))
        self.metas.append(_Meta(value_type, frozenset(scope)))
        return _term("meta", value=index)

    def resolve(self, term: _Term) -> _Term:
        self.tick()
        if term.kind == "meta":
            solution = self.metas[cast("int", term.value)].solution
            if solution is not None:
                return self.resolve(solution)
        return term

    def substitute(
        self,
        term: _Term,
        variable: int,
        replacement: _Term,
        memo: dict[int, tuple[_Term, _Term]] | None = None,
    ) -> _Term:
        if memo is None:
            memo = {}
        tid = id(term)
        if tid in memo:
            return memo[tid][1]
        self.tick()
        resolved = self.resolve(term)
        if resolved.kind == "var" and resolved.value == variable:
            memo[tid] = (term, replacement)
            return replacement
        if resolved.kind in {"pi", "lam"} and resolved.value == variable:
            new_dom = self.substitute(resolved.args[0], variable, replacement, memo)
            res = (
                resolved
                if new_dom is resolved.args[0]
                else _term(resolved.kind, new_dom, resolved.args[1], value=resolved.value)
            )
            memo[tid] = (term, res)
            return res
        if resolved.kind == "let" and resolved.value == variable:
            new_dom = self.substitute(resolved.args[0], variable, replacement, memo)
            new_val = self.substitute(resolved.args[1], variable, replacement, memo)
            res = (
                resolved
                if (new_dom is resolved.args[0] and new_val is resolved.args[1])
                else _term("let", new_dom, new_val, resolved.args[2], value=resolved.value)
            )
            memo[tid] = (term, res)
            return res
        if resolved.kind == "fix" and resolved.value == variable:
            new_sig = self.substitute(resolved.args[0], variable, replacement, memo)
            res = (
                resolved
                if new_sig is resolved.args[0]
                else _term(
                    "fix",
                    new_sig,
                    resolved.args[1],
                    resolved.args[2],
                    resolved.args[3],
                    value=resolved.value,
                )
            )
            memo[tid] = (term, res)
            return res
        if not resolved.args:
            memo[tid] = (term, resolved)
            return resolved
        new_args = tuple(self.substitute(value, variable, replacement, memo) for value in resolved.args)
        if all(na is oa for na, oa in zip(new_args, resolved.args, strict=True)):
            memo[tid] = (term, resolved)
            return resolved
        res = _Term(resolved.kind, resolved.value, new_args)
        memo[tid] = (term, res)
        return res

    def free(
        self, term: _Term, memo: dict[int, tuple[_Term, frozenset[int]]] | None = None
    ) -> set[int]:
        if memo is None:
            memo = {}
        tid = id(term)
        if tid in memo:
            return set(memo[tid][1])
        self.tick()
        term = self.resolve(term)
        if term.kind == "var":
            fset = frozenset({cast("int", term.value)})
            memo[tid] = (term, fset)
            return set(fset)
        result: set[int] = set()
        for argument in term.args:
            result.update(self.free(argument, memo))
        if term.kind in {"pi", "lam", "let", "fix"}:
            result.discard(cast("int", term.value))
        memo[tid] = (term, frozenset(result))
        return result


    def reset_budget(self) -> None:
        self.work = MAX_WORK
        self.reductions = MAX_REDUCTIONS

    def natural_limit(self) -> int:
        return MAX_CONSTANT_NAT if self.static_forbidden is not None else (1 << MAX_NAT_BITS) - 1


    def unify(self, left: _Term, right: _Term) -> None:
        self.tick()
        left, right = self.whnf(left), self.whnf(right)
        if (left.kind == right.kind and left.kind in {"pi", "lam"}
                and (cast("int", left.value) in self.nullary_parameters)
                != (cast("int", right.value) in self.nullary_parameters)):
            raise self.fail("type", "zero-parameter and explicit-parameter callables have different source arities")
        if (left.kind == right.kind and left.kind in {"pi", "lam"}
                and (cast("int", left.value) in self.constant_parameters)
                != (cast("int", right.value) in self.constant_parameters)):
            raise self.fail("type", "callable constant-parameter requirements differ")
        if left == right:
            return
        # Decimal literals abbreviate constructor chains; expose one successor
        # when an inferred predecessor is constrained by a concrete index.
        for literal, successor in ((left, right), (right, left)):
            if (literal.kind == "nat" and cast("int", literal.value) > 0
                    and successor.kind == "app" and successor.args[0] == _constant("Succ")):
                self.unify(_term("nat", value=cast("int", literal.value) - 1), successor.args[1])
                return
        if right.kind == "meta" and left.kind != "meta":
            left, right = right, left
        if left.kind == "meta":
            index = cast("int", left.value)
            if self.occurs(index, right):
                raise self.fail("type", "infinite type or cyclic dependent inference (occurs check)")
            record = self.metas[index]
            if not self.free(right) <= record.scope:
                raise self.fail("type", "inference would let a local dependent value escape its scope")
            # Narrow nested unsolved variables too: a future solution cannot escape indirectly.
            self.restrict(right, record.scope)
            self.unify(record.type, self.infer(right))
            record.solution = right
            return
        if left.kind != right.kind or left.value != right.value:
            if left.kind == right.kind and left.kind in {"pi", "lam"}:
                self.unify(left.args[0], right.args[0])
                aligned = self.substitute(right.args[1], cast("int", right.value), _term("var", value=left.value))
                self.unify(left.args[1], aligned)
                return
            raise self.fail("type", "terms or dependent indices are not definitionally equal")
        if len(left.args) != len(right.args):
            raise self.fail("type", "incompatible type constructors")
        for first, second in zip(left.args, right.args, strict=True):
            self.unify(first, second)

    def restrict(self, term: _Term, scope: frozenset[int]) -> None:
        term = self.resolve(term)
        if term.kind == "meta":
            record = self.metas[cast("int", term.value)]
            record.scope = record.scope & scope
        for child in term.args:
            self.restrict(child, scope)

    def infer(self, term: _Term) -> _Term:
        self.tick()
        term = self.resolve(term)
        kind = term.kind
        if kind == "meta":
            return self.metas[cast("int", term.value)].type
        if kind == "var":
            return self.types[cast("int", term.value)]
        if kind == "sort":
            return _term("sort", value=max(0, cast("int", term.value) + 1))
        if kind == "const":
            if term.value == "Prop":
                return _SORT
            return self.constants[cast("str", term.value)].type
        if kind == "nat":
            return _NAT
        if kind == "int":
            return term.args[0]
        if kind == "bool":
            return _BOOL
        if kind == "char":
            return _CHAR
        if kind == "unit":
            return _UNIT
        if kind == "static":
            return term.args[0]
        if kind == "let":
            return self.substitute(self.infer(term.args[2]), cast("int", term.value), term.args[1])
        if kind == "pi":
            domain = self.sort(term.args[0])
            result = self.sort(term.args[1])
            return _term("sort", value=-1 if result == -1 else max(domain, result))
        if kind == "lam":
            return _term("pi", term.args[0], self.infer(term.args[1]), value=term.value)
        if kind == "app":
            function_type = self.whnf(self.infer(term.args[0]))
            if function_type.kind != "pi":
                raise self.fail("type", "application requires a function")
            self.unify(self.infer(term.args[1]), function_type.args[0])
            return self.substitute(function_type.args[1], cast("int", function_type.value), term.args[1])
        if kind == "fix":
            return term.args[0]
        if kind in {"prod", "sum"}:
            return _term("sort", value=max(self.sort(term.args[0]), self.sort(term.args[1]), 0))
        if kind == "sigT":
            return _term("sort", value=max(self.sort(term.args[0]), self.sort(term.args[1].args[1]), 0))
        if kind == "pair":
            return _term("prod", term.args[0], term.args[1])
        if kind == "existT":
            return _term("sigT", term.args[0], term.args[1])
        if kind == "projT1":
            return term.args[0]
        if kind == "projT2":
            p1 = _term("projT1", term.args[0], term.args[1], term.args[2])
            return self.substitute(term.args[1].args[1], cast("int", term.args[1].value), p1)
        if kind == "ex":
            self.sort(term.args[0])
            if self.whnf(self.infer(term.args[1].args[1])) != _PROP:
                raise self.fail("type", "existential quantifier body must be a proposition")
            return _PROP
        if kind == "ex_intro":
            return _term("ex", term.args[0], term.args[1])
        if kind in {"inl", "inr"}:
            return _term("sum", term.args[0], term.args[1])
        if kind == "if":
            return term.args[0]
        if kind in {"bool_match", "unit_match", "pair_match", "sigT_match", "nat_match", "sum_match"}:
            return self.substitute(term.args[0].args[1], cast("int", term.args[0].value), term.args[1])
        raise self.fail("type", "cannot infer internal term")

    def sort(self, term: _Term) -> int:
        value_type = self.whnf(self.infer(term))
        if value_type.kind != "sort":
            raise self.fail("type", "expected a type or proposition")
        level = cast("int", value_type.value)
        if level > MAX_UNIVERSE + 1:
            raise self.fail("limit", "universe formation exceeds the supported hierarchy")
        return level

    def node(self, raw: object, kind: str | None = None) -> Node:
        if not isinstance(raw, dict) or not isinstance(raw.get("kind"), str):
            raise self.fail("protocol", "expected a syntax node")
        node = cast("Node", raw)
        if kind is not None and node["kind"] != kind:
            raise self.fail("protocol", f"expected a '{kind}' node", node)
        return node

    def nodes(self, raw: object) -> list[Node]:
        if not isinstance(raw, list):
            raise self.fail("protocol", "expected a syntax-node list")
        return [self.node(value) for value in raw]

    def name(self, raw: object) -> str:
        if (not isinstance(raw, dict) or not isinstance(raw.get("text"), str)
                or not _IDENTIFIER.fullmatch(raw["text"])):
            raise self.fail("protocol", "expected a located name")
        return cast("str", raw["text"])

    def operator(self, raw: object) -> str:
        if not isinstance(raw, dict) or not isinstance(raw.get("text"), str) or raw["text"] not in _OPERATORS:
            raise self.fail("protocol", "expected a supported located operator")
        return cast("str", raw["text"])

    def no_roles(self, node: Node, *roles: str) -> None:
        for role in roles:
            value = node.get(role)
            if value is not None and value != []:
                raise self.fail("unsupported", f"'{role}' requires the full frontend", node)

    def bind_local(self, environment: dict[str, _Binding], name: str, binding: _Binding) -> None:
        if "." in name or (name != "_" and name in environment):
            raise self.fail("name", f"duplicate or invalid local binding '{name}'")
        if name != "_":
            environment[name] = binding

    def instantiate(self, binding: _Binding, environment: dict[str, _Binding],
                    arguments: list[Node] | None = None) -> _Binding:
        term, value_type = binding.term, binding.type
        if arguments is not None and len(arguments) != binding.generics:
            raise self.fail("type", f"expected {binding.generics} explicit generic arguments, got {len(arguments)}")
        for index in range(binding.generics):
            value_type = self.whnf(value_type)
            if value_type.kind != "pi":
                raise self.fail("type", "invalid generic telescope")
            domain = value_type.args[0]
            if arguments is None:
                argument = self.meta(domain, environment)
            else:
                argument = self.argument(arguments[index], domain, environment)
            term = _app(term, argument)
            value_type = self.substitute(value_type.args[1], cast("int", value_type.value), argument)
        return _Binding(term, value_type)

    def lookup(self, name: str, environment: dict[str, _Binding], *, raw: bool = False) -> _Binding:
        binding = environment.get(name, self.globals.get(name))
        if binding is None:
            if name in self.inaccessible_private_symbols:
                mod = self.inaccessible_private_symbols[name]
                raise self.fail("name", f"cannot access private declaration '{name}' of module '{mod}'")
            raise self.fail("name", f"unknown or forward name '{name}'")
        if self.static_forbidden is not None and id(binding) in self.static_forbidden:
            raise self.fail("type", f"constant initializer depends on nonstatic binding '{name}'")
        return binding if raw else self.instantiate(binding, environment)

    def argument(self, node: Node, expected: _Term, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "type_argument":
            value = self.type(self.node(node["type"]), environment)
            if self.whnf(expected) == _NAT and self.whnf(self.infer(value)) == _USIZE:
                value = self.whnf(_app(_constant("int_to_nat_usize"), value))
            self.unify(self.infer(value), expected)
            return value
        if node["kind"] in {"type", "function_type", "group_type", "tuple_type", "computed_type"}:
            if node["kind"] == "type" and self.name(node["name"]) == "_" and not self.nodes(node["arguments"]):
                return self.meta(expected, environment)
            value = self.type(node, environment, require_sort=False)
            if self.whnf(expected) == _NAT and self.whnf(self.infer(value)) == _USIZE:
                value = self.whnf(_app(_constant("int_to_nat_usize"), value))
            self.unify(self.infer(value), expected)
            return value
        if self.whnf(expected) == _NAT and not self._is_unsuffixed_int_expr(node):
            expr_b = self.expression(node, environment)
            if self.whnf(expr_b.type) == _USIZE:
                return self.whnf(_app(_constant("int_to_nat_usize"), expr_b.term))
            self.unify(expr_b.type, expected)
            return expr_b.term
        return self.check(node, expected, environment)

    def static_argument(self, node: Node, expected: _Term, environment: dict[str, _Binding],
                        *, type_syntax: bool = False) -> _Term:
        """Check the complete source dependency graph before reducing an argument."""
        previous = self.static_forbidden
        self.static_forbidden = (set() if previous is None else previous) | {
            id(binding) for binding in environment.values() if not binding.constant}
        try:
            value = self.argument(node, expected, environment) if type_syntax else self.check(node, expected, environment)
            self.complete(value)
            available = set().union(*(self.free(binding.term) for binding in environment.values()
                                      if binding.constant))
            dependencies = self.free(value)
            if not dependencies <= available:
                raise self.fail("type", "constant parameter requires a static argument", node)
            expected_whnf = self.whnf(expected)
            if expected_whnf in {_NAT, _BOOL, _CHAR, _UNIT} or self._int_spec(expected_whnf) is not None:
                marked = _term("static", expected, value)
                return marked if dependencies else self.whnf(marked)
            return value
        finally:
            self.static_forbidden = previous

    def specialize(self, term: _Term, depth: int = 0) -> _Term:
        """Instantiate logical templates while preserving deferred static demands."""
        self.tick(True)
        if depth > MAX_DEPTH:
            raise self.fail("limit", "static specialization exceeds its nesting budget")
        term = self.resolve(term)
        if term.kind == "fix":
            return term
        if term.kind == "let":
            return _term("let", term.args[0], term.args[1], self.specialize(term.args[2], depth + 1), value=term.value)
        if term.kind == "static":
            value = self.specialize(term.args[1], depth + 1)
            marked = _term("static", term.args[0], value)
            return marked if self.free(value) else self.whnf(marked)
        if term.kind == "const" and term.value in self.definitions:
            if self.definitions[term.value].kind == "fix":
                return term
            return self.specialize(self.definitions[term.value], depth + 1)
        if term.kind == "app":
            function = self.specialize(term.args[0], depth + 1)
            argument = self.specialize(term.args[1], depth + 1)
            if function.kind == "let":
                body = self.specialize(_app(function.args[2], argument), depth + 1)
                return _term("let", function.args[0], function.args[1], body, value=function.value)
            if function.kind == "lam":
                return self.specialize(self.substitute(function.args[1], cast("int", function.value), argument), depth + 1)
            result = _app(function, argument)
            reduced = self.whnf(result)
            return result if reduced == result else self.specialize(reduced, depth + 1)
        specialized = _Term(term.kind, term.value, tuple(self.specialize(child, depth + 1) for child in term.args))
        if term.kind in {"if", "bool_match", "unit_match", "pair_match", "sigT_match", "nat_match", "sum_match", "projT1", "projT2"}:
            reduced = self.whnf(specialized)
            return specialized if reduced == specialized else self.specialize(reduced, depth + 1)
        return specialized

    def apply(self, binding: _Binding, arguments: list[Node], environment: dict[str, _Binding]) -> _Binding:
        call_site = self.site
        term, value_type = binding.term, binding.type
        callee_head, callee_gen_args = self.spine(self.resolve(term))
        is_rec_call = (
            self.current_rec_var is not None
            and callee_head == self.current_rec_var
        )
        specializing = False
        specialized_term = term
        runtime_arguments: list[tuple[_Term, _Term]] = []
        future = self.whnf(value_type)
        protects_runtime = False
        while future.kind == "pi":
            protects_runtime = protects_runtime or cast("int", future.value) in self.constant_parameters
            future = self.whnf(future.args[1])
        val_args: list[_Term] = []
        loan_targets: dict[int, tuple[Node, _Term]] = {}
        seen_loan_names: set[str] = set()
        all_arg_var_names: set[str] = set()
        out_loan_names: set[str] = set()
        if not arguments:
            if is_rec_call:
                raise self.fail("type", f"zero-parameter declaration '{self.current_rec_name}' cannot be structurally recursive")
            value_type = self.whnf(value_type)
            if value_type.kind != "pi" or cast("int", value_type.value) not in self.nullary_parameters:
                raise self.fail("type", "zero-argument call requires a zero-parameter source callable")
            self.unify(value_type.args[0], _UNIT)
            argument = _term("unit")
            val_args.append(argument)
            term = _app(term, argument)
            specialized_term = _app(specialized_term, argument)
            value_type = self.substitute(value_type.args[1], cast("int", value_type.value), argument)
        else:
            labeled = False
            for idx, node in enumerate(arguments):
                self.node(node, "argument")
                label = node["label"]
                if label is None and labeled:
                    raise self.fail("name", "positional arguments cannot follow a named argument", node)
                labeled = labeled or label is not None
                value_type = self.whnf(value_type)
                if value_type.kind == "meta":
                    domain = self.meta(_SORT, environment)
                    variable = self.fresh(domain)
                    result = self.meta(_SORT, environment)
                    self.unify(value_type, _term("pi", domain, result, value=variable.value))
                    value_type = self.whnf(value_type)
                if value_type.kind != "pi":
                    raise self.fail("type", "too many arguments or a non-callable value", node)
                param_var_id = cast("int", value_type.value)
                if param_var_id in self.nullary_parameters:
                    raise self.fail("type", "a zero-parameter callable accepts no explicit arguments", node)
                if label is not None:
                    spelling = self.name(label)
                    expected = self.parameter_names.get(param_var_id)
                    if expected is None:
                        raise self.fail("name", "unnamed callable parameters do not accept argument labels", node)
                    if spelling != expected:
                        raise self.fail("name", f"expected argument label '{expected}', got '{spelling}'", node)
                is_out_param = param_var_id in self.out_parameters
                is_ref_param = param_var_id in self.ref_parameters
                arg_val_node = self._unwrap_group(self.node(node["value"]))
                arg_mod = (
                    cast("Node", arg_val_node["operator"]).get("text")
                    if (
                        arg_val_node["kind"] == "unary"
                        and isinstance(arg_val_node.get("operator"), dict)
                        and cast("Node", arg_val_node["operator"]).get("text") in {"ref", "in", "out"}
                    )
                    else None
                )
                if is_out_param and arg_mod != "out":
                    raise self.fail("type", "an 'out' parameter requires an 'out' call-site argument modifier", node)
                if not is_out_param and arg_mod == "out":
                    raise self.fail("type", "'out' call-site argument modifier requires an 'out' parameter", node)
                if arg_mod == "out":
                    arg_ident_node = self._unwrap_group(self.node(arg_val_node["value"]))
                    if arg_ident_node["kind"] != "name":
                        raise self.fail("type", "'out' argument target must be a mutable local or loan variable", node)
                    arg_vname = self.name(arg_ident_node["name"])
                    if arg_vname not in self.mutable_locals:
                        raise self.fail("type", f"cannot pass immutable binding '{arg_vname}' as an 'out' argument", node)
                    if arg_vname in self.frozen_collections:
                        raise self.fail(
                            "type",
                            f"cannot mutate collection '{arg_vname}' with 'out' while it is traversed by 'foreach'",
                            node,
                        )
                    if arg_vname in all_arg_var_names:
                        raise self.fail("type", f"overlapping loan for '{arg_vname}' in call", node)
                    seen_loan_names.add(arg_vname)
                    all_arg_var_names.add(arg_vname)
                    out_loan_names.add(arg_vname)
                    target_b = self.lookup(arg_vname, environment)
                    self.site = node
                    self.unify(target_b.type, value_type.args[0])
                    argument = target_b.term
                    loan_targets[idx] = (arg_ident_node, value_type.args[0])
                    required_static = False
                else:
                    arg_ident_node = (
                        self._unwrap_group(self.node(arg_val_node["value"]))
                        if arg_mod in {"ref", "in"}
                        else arg_val_node
                    )
                    if arg_ident_node["kind"] == "name":
                        arg_vname = self.name(arg_ident_node["name"])
                        lifted_set = self.lifted_invariants.get(arg_vname)
                        if lifted_set is not None and len(lifted_set) > 0:
                            clause_n = min(lifted_set)
                            raise self.fail(
                                "type",
                                f"cannot pass record '{arg_vname}' to a callable while invariant '{clause_n}' is lifted",
                                node,
                            )
                        if is_ref_param or arg_mod == "ref":
                            if arg_vname not in self.mutable_locals:
                                raise self.fail("type", f"cannot pass immutable binding '{arg_vname}' as a 'ref' argument", node)
                            if arg_vname in self.frozen_collections:
                                raise self.fail(
                                    "type",
                                    f"cannot mutate collection '{arg_vname}' with 'ref' while it is traversed by 'foreach'",
                                    node,
                                )
                            if arg_vname in all_arg_var_names:
                                raise self.fail("type", f"overlapping loan for '{arg_vname}' in call", node)
                            seen_loan_names.add(arg_vname)
                            loan_targets[idx] = (arg_ident_node, value_type.args[0])
                        elif arg_vname in seen_loan_names:
                            raise self.fail("type", f"overlapping loan for '{arg_vname}' in call", node)
                        all_arg_var_names.add(arg_vname)
                    required_static = param_var_id in self.constant_parameters
                    checker = self.static_argument if required_static else self.check
                    argument = checker(
                        arg_ident_node if arg_ident_node is not arg_val_node else self.node(node["value"]),
                        value_type.args[0],
                        environment,
                    )
                val_args.append(argument)
                specializing = specializing or required_static
                if required_static:
                    specialized_term = _app(specialized_term, argument)
                elif protects_runtime:
                    variable = self.fresh(value_type.args[0])
                    runtime_arguments.append((variable, argument))
                    specialized_term = _app(specialized_term, variable)
                else:
                    specialized_term = _app(specialized_term, argument)
                term = _app(term, argument)
                value_type = self.substitute(value_type.args[1], param_var_id, argument)
        if (
            callee_head.kind == "const"
            and isinstance(callee_head.value, str)
            and callee_head.value in self.records_by_ctor
        ):
            rinfo = self.records_by_ctor[callee_head.value]
            self._check_record_invariants(rinfo, callee_gen_args, term, environment, call_site)
        if callee_head.kind == "const" and callee_head.value in self.callable_preconditions:
            full_args = callee_gen_args + val_args
            for param_ids, req_term in self.callable_preconditions[callee_head.value]:
                if len(full_args) >= len(param_ids):
                    inst_req = req_term
                    for pid, arg_val in zip(param_ids, full_args, strict=False):
                        inst_req = self.substitute(inst_req, pid, arg_val)
                    self._check_precondition_term(inst_req, environment, call_site)
        if callee_head.kind == "var" and cast("int", callee_head.value) in self.var_preconditions:
            full_args_v = callee_gen_args + val_args
            for param_ids, req_term in self.var_preconditions[cast("int", callee_head.value)]:
                if len(full_args_v) >= len(param_ids):
                    inst_req = req_term
                    for pid, arg_val in zip(param_ids, full_args_v, strict=False):
                        inst_req = self.substitute(inst_req, pid, arg_val)
                    self._check_precondition_term(inst_req, environment, call_site)
        if (
            callee_head.kind == "const"
            and isinstance(callee_head.value, str)
            and callee_head.value in self.callable_where_constraints
        ):
            _, w_specs = self.callable_where_constraints[callee_head.value]
            if self.expected_call_type is not None:
                peek_type = value_type
                for _ in w_specs:
                    peek_w = self.whnf(peek_type)
                    if peek_w.kind == "pi":
                        peek_type = peek_w.args[1]
                self._try_unify(peek_type, self.expected_call_type)
            witness_terms = self._resolve_interface_witnesses(
                callee_head.value, callee_gen_args + val_args, environment, call_site
            )
            for w_term in witness_terms:
                value_type = self.whnf(value_type)
                if value_type.kind != "pi":
                    raise self.fail("type", "invalid interface witness telescope", call_site)
                self.unify(self.infer(w_term), value_type.args[0])
                term = _app(term, w_term)
                specialized_term = _app(specialized_term, w_term)
                value_type = self.substitute(value_type.args[1], cast("int", value_type.value), w_term)
        elif is_rec_call and self.current_rec_witnesses:
            for w_term in self.current_rec_witnesses:
                value_type = self.whnf(value_type)
                if value_type.kind != "pi":
                    raise self.fail("type", "invalid recursive interface witness telescope", call_site)
                self.unify(self.infer(w_term), value_type.args[0])
                term = _app(term, w_term)
                specialized_term = _app(specialized_term, w_term)
                value_type = self.substitute(value_type.args[1], cast("int", value_type.value), w_term)
        for vname in out_loan_names:
            self.uninitialized_out_params.discard(vname)
        if (
            self.in_post_env_theorem
            and not protects_runtime
            and callee_head.kind == "const"
            and isinstance(callee_head.value, str)
            and callee_head.value in self.definitions
            and not self._is_prop_type(value_type)
        ):
            term = self._simplify_term_with_facts(term, environment)
        post_loan_terms: dict[int, _Term] = {}
        if loan_targets:
            full_args = callee_gen_args + val_args
            u_param_ids: tuple[int, ...] = ()
            idx_to_term: dict[int, _Term] = {}
            if (
                callee_head.kind == "const"
                and isinstance(callee_head.value, str)
                and callee_head.value in self.callable_ref_updates
            ):
                u_param_ids, idx_to_term = self.callable_ref_updates[callee_head.value]
            for idx, (t_node, t_dom) in loan_targets.items():
                if idx in idx_to_term and len(full_args) >= len(u_param_ids):
                    upd_term = idx_to_term[idx]
                    for pid, aval in zip(u_param_ids, full_args, strict=False):
                        upd_term = self.substitute(upd_term, pid, aval)
                    if self.in_post_env_theorem:
                        upd_term = self._simplify_term_with_facts(upd_term, environment)
                else:
                    upd_term = self.fresh(t_dom)
                post_loan_terms[idx] = upd_term
                self.last_call_updates.append((t_node, _Binding(upd_term, t_dom)))
        if (
            callee_head.kind == "const"
            and isinstance(callee_head.value, str)
            and callee_head.value in self.callable_ensures
        ):
            full_args = callee_gen_args + val_args
            for e_param_ids, post_loan_pairs, res_var_id, ens_term in self.callable_ensures[callee_head.value]:
                if len(full_args) >= len(e_param_ids):
                    inst_ens = ens_term
                    for pid, aval in zip(e_param_ids, full_args, strict=False):
                        inst_ens = self.substitute(inst_ens, pid, aval)
                    if res_var_id is not None:
                        inst_ens = self.substitute(inst_ens, res_var_id, term)
                    for p_idx, post_vid in post_loan_pairs:
                        replacement = post_loan_terms.get(
                            p_idx, val_args[p_idx] if p_idx < len(val_args) else _term("var", value=post_vid)
                        )
                        inst_ens = self.substitute(inst_ens, post_vid, replacement)
                    if self.whnf(inst_ens) != _term("bool", value=1):
                        self.active_facts.append(inst_ens)
        if is_rec_call:
            self.current_rec_used = True
            if len(callee_gen_args) != len(self.current_rec_generics):
                raise self.fail("type", "recursive call requires full generic instantiation")
            for g_arg, g_param in zip(callee_gen_args, self.current_rec_generics, strict=True):
                if not self._try_unify(g_arg, g_param):
                    raise self.fail("type", "polymorphic recursion with varying generic arguments is not supported")
            if len(val_args) != len(self.current_rec_params) or not self.current_rec_params:
                raise self.fail("type", f"recursive call to '{self.current_rec_name}' must supply all parameters")
            decreasing_indices = {
                i
                for i, pv in enumerate(self.current_rec_params)
                if (
                    self.resolve(val_args[i]).kind == "var"
                    and cast("int", self.resolve(val_args[i]).value)
                    in self.smaller_vars.get(cast("int", pv.value), set())
                )
            }
            self.current_rec_candidates = [
                (p_idx, p_var_id)
                for p_idx, p_var_id in self.current_rec_candidates
                if p_idx in decreasing_indices
            ]
            if not self.current_rec_candidates:
                raise self.fail(
                    "type",
                    f"recursive call to '{self.current_rec_name}' must pass a structurally smaller pattern binder for its decreasing parameter",
                )
        if protects_runtime:
            term = self.specialize(specialized_term) if specializing else specialized_term
            for variable, argument in reversed(runtime_arguments):
                term = _term("let", self.types[cast("int", variable.value)], argument, term, value=variable.value)
        return _Binding(term, value_type)

    def telescope(self, generic_nodes: list[Node], parameter_nodes: list[Node],
                  environment: dict[str, _Binding], *, unit: bool = False) -> tuple[list[_Term], dict[str, _Binding]]:
        extended = dict(environment)
        variables: list[_Term] = []
        for node in generic_nodes:
            self.site = node
            self.node(node, "generic_parameter")
            mode = node["mode"]
            if not isinstance(mode, str) or mode not in {"type", "ghost"}:
                raise self.fail("unsupported", f"generic mode '{mode}' requires the full frontend")
            if mode == "ghost" and node["type"] is None:
                raise self.fail("protocol", "ghost binder lacks its type")
            domain = _SORT if node["type"] is None else self.type(self.node(node["type"]), extended)
            if mode == "type" and self.whnf(domain).kind != "sort":
                raise self.fail("type", "a type generic requires a universe kind")
            variable = self.fresh(domain)
            variables.append(variable)
            self.bind_local(extended, self.name(node["name"]), _Binding(variable, domain))
        for node in parameter_nodes:
            self.site = node
            if node["kind"] != "parameter":
                raise self.fail("protocol", "invalid parameter role")
            self.no_roles(node, "grade")
            param_type_node = self.node(node["type"])
            is_readonly_span = (
                param_type_node["kind"] == "modified_type"
                and param_type_node.get("modifier") == "in"
            )
            is_ref_param = (
                param_type_node["kind"] == "modified_type"
                and param_type_node.get("modifier") == "ref"
            )
            is_out_param = (
                param_type_node["kind"] == "modified_type"
                and param_type_node.get("modifier") == "out"
            )
            domain = self.type(param_type_node, extended, allow_out=True)
            variable = self.fresh(domain)
            variables.append(variable)
            if is_readonly_span:
                self.readonly_span_vars.add(cast("int", variable.value))
            if is_ref_param:
                self.ref_parameters.add(cast("int", variable.value))
            if is_out_param:
                self.out_parameters.add(cast("int", variable.value))
            static = cast("bool", node.get("const", False))
            if static and is_out_param:
                raise self.fail("type", "constant parameter cannot be an 'out' loan", node)
            if static:
                self.constant_parameters.add(cast("int", variable.value))
            if node["name"] is not None:
                name = self.name(node["name"])
                self.parameter_names[cast("int", variable.value)] = name
                if is_ref_param or is_out_param:
                    self.mutable_locals.add(name)
                if is_out_param:
                    self.out_param_names.add(name)
                    self.uninitialized_out_params.add(name)
                self.bind_local(extended, name, _Binding(variable, domain, constant=static))
            elif is_out_param:
                raise self.fail("type", "'out' parameter requires a parameter name", node)
        if unit and not parameter_nodes:
            variable = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", variable.value))
            variables.append(variable)
        return variables, extended

    def wrap(self, kind: str, variables: list[_Term], result: _Term) -> _Term:
        for variable in reversed(variables):
            result = _term(kind, self.types[cast("int", variable.value)], result, value=variable.value)
        return result

    def type(
        self,
        node: Node,
        environment: dict[str, _Binding],
        *,
        require_sort: bool = True,
        allow_out: bool = False,
    ) -> _Term:
        self.tick()
        self.site = node
        kind = node["kind"]
        if kind == "type":
            name = self.name(node["name"])
            arguments = self.nodes(node["arguments"])
            if name == "_" and not arguments:
                result = self.meta(_SORT, environment)
            elif name == "Type":
                if not arguments:
                    result = _SORT
                elif len(arguments) == 1 and arguments[0]["kind"] == "nat":
                    level = int(cast("str", arguments[0]["value"]).replace("_", ""))
                    if not 0 <= level <= MAX_UNIVERSE:
                        raise self.fail("limit", f"Type level must be between 0 and {MAX_UNIVERSE}")
                    result = _term("sort", value=level)
                else:
                    raise self.fail("unsupported", "only numeric Type<n> universe levels are supported")
            elif name == "Prop":
                if arguments:
                    raise self.fail("type", "Prop takes no type arguments")
                result = _PROP
            else:
                parts = name.split(".")
                if (
                    len(parts) > 1
                    and not arguments
                    and name not in environment
                    and name not in self.globals
                    and (parts[0] in environment or parts[0] in self.globals)
                ):
                    curr = self.lookup(parts[0], environment)
                    curr_head, _ = self.spine(self.whnf(curr.type))
                    if curr_head.kind == "const" and isinstance(curr_head.value, str) and curr_head.value in self.records_by_type:
                        for seg in parts[1:]:
                            curr = self._project_member(curr, seg, node)
                        result = curr.term
                    else:
                        binding = self.lookup(name, environment, raw=True)
                        result = binding.term
                else:
                    binding = self.lookup(name, environment, raw=True)
                    result, value_type = binding.term, binding.type
                    for argument in arguments:
                        value_type = self.whnf(value_type)
                        if value_type.kind != "pi":
                            raise self.fail("type", f"too many arguments to '{name}'")
                        value = (self.static_argument(argument, value_type.args[0], environment, type_syntax=True)
                                 if cast("int", value_type.value) in self.constant_parameters else
                                 self.argument(argument, value_type.args[0], environment))
                        result = _app(result, value)
                        value_type = self.substitute(value_type.args[1], cast("int", value_type.value), value)
        elif kind in {"group_type", "type_argument"}:
            result = self.type(self.node(node["type"]), environment, require_sort=require_sort, allow_out=allow_out)
        elif kind == "tuple_type":
            values = [self.type(value, environment) for value in self.nodes(node["types"])]
            if len(values) < 2:
                raise self.fail("protocol", "a product type requires at least two components")
            result = values[-1]
            for value in reversed(values[:-1]):
                result = _term("prod", value, result)
        elif kind == "computed_type":
            result = self.expression(self.node(node["value"]), environment).term
        elif kind == "function_type":
            self.no_roles(node, "captures", "effects", "contracts")
            if node["mode"] != "Fn":
                raise self.fail("unsupported", "only pure Fn callable types are supported")
            variables, extended = self.telescope(self.nodes(node["generics"]), self.nodes(node["parameters"]), environment, unit=True)
            result = self.wrap("pi", variables, self.type(self.node(node["result"]), extended))
        elif kind == "modified_type":
            if node.get("lifetime") is not None:
                raise self.fail("unsupported", "explicit loan lifetimes require the full frontend", node)
            modifier = node.get("modifier")
            if modifier == "out":
                if not allow_out:
                    raise self.fail("type", "'out' type modifier is only permitted on callable parameters", node)
                inner_type = self.type(self.node(node["type"]), environment, require_sort=require_sort)
                inner_w = self.whnf(inner_type)
                if inner_w in (_PROP, _UNIT) or inner_w.kind in {"pi", "sort"}:
                    raise self.fail("type", "'out' parameter requires a runtime value type", node)
                result = inner_type
            elif modifier in {"in", "ref"}:
                inner_type = self.type(self.node(node["type"]), environment, require_sort=require_sort)
                inner_w = self.whnf(inner_type)
                inner_head, inner_args = self.spine(inner_w)
                supported_loan = (
                    (inner_head == _constant("Span") and len(inner_args) == 1 and self.whnf(inner_args[0]) == _U8)
                    or (inner_head == _constant("Slots") and len(inner_args) == 2)
                    or (inner_head == _constant("Vec") and len(inner_args) == 2)
                    or (inner_head == _constant("Seq") and len(inner_args) == 1)
                    or (inner_head == _constant("TextBuilder") and len(inner_args) == 1)
                    or (
                        inner_head.kind == "const"
                        and isinstance(inner_head.value, str)
                        and inner_head.value in self.records_by_type
                    )
                )
                if not supported_loan:
                    raise self.fail(
                        "unsupported",
                        f"modifier '{modifier}' is only supported on Span<byte>, Slots<T, capacity>, Vec<T, n>, Seq<T>, TextBuilder<capacity> or record types in the first-slice carrier",
                        node,
                    )
                result = inner_type
            else:
                raise self.fail("unsupported", f"type modifier '{modifier}' requires the full frontend", node)
        else:
            raise self.fail("unsupported", f"'{kind}' is not a supported mathematical type")
        if require_sort:
            self.sort(result)
        return result

    def check(self, node: Node, expected: _Term, environment: dict[str, _Binding]) -> _Term:
        self.site = node
        if node["kind"] == "expression_body":
            return self.check(self.node(node["value"]), expected, environment)
        if node["kind"] == "group":
            return self.check(self.node(node["value"]), expected, environment)
        if node["kind"] not in {"lambda", "typed_lambda", "block"} and (
            self._is_propagatable_union(expected)
            or (self.current_return_type is not None and expected == self.current_return_type)
        ):
            split_prop = self._split_first_propagate(node)
            if split_prop is not None:
                prop_node, rebuild = split_prop
                return self._elaborate_propagate(
                    prop_node,
                    environment,
                    expected,
                    lambda temp_name, _ok_b, ok_env: self.check(
                        rebuild(
                            {
                                "kind": "name",
                                "span": prop_node["span"],
                                "name": {"text": temp_name, "span": prop_node["span"]},
                            }
                        ),
                        expected,
                        ok_env,
                    ),
                )
        if node["kind"] in {"lambda", "typed_lambda"}:
            return self.lambda_(node, environment, expected).term
        if node["kind"] == "block":
            return self.block(node, environment, expected).term
        if node["kind"] == "let_expression":
            return self.check(self.node(node["body"]), expected, self.local(self.node(node["binding"]), environment))
        if node["kind"] == "if_expression":
            return self.if_expression(node, environment, expected).term
        if node["kind"] == "with_expression":
            return self.with_expression(node, environment, expected).term
        if node["kind"] == "match_expression":
            return self.match(node, environment, expected, expression_arms=True).term
        if node["kind"] == "tuple":
            expected_normal = self.whnf(expected)
            if expected_normal.kind == "prod":
                values = self.nodes(node["values"])
                if len(values) < 2:
                    raise self.fail("protocol", "a product requires at least two components")
                first = self.check(values[0], expected_normal.args[0], environment)
                if len(values) == 2:
                    second = self.check(values[1], expected_normal.args[1], environment)
                else:
                    rest = {"kind": "tuple", "span": node["span"], "values": values[1:]}
                    second = self.check(rest, expected_normal.args[1], environment)
                return _term("pair", expected_normal.args[0], expected_normal.args[1], first, second)
        if node["kind"] == "nat" and node["suffix"] == "":
            spec = self._int_spec(expected)
            if spec is not None:
                mag = _parse_numeric_magnitude(cast("str", node["value"]))
                if not spec.min_val <= mag <= spec.max_val:
                    raise self.fail(
                        "type",
                        f"integer literal {mag} is out of range for '{spec.name}' ({spec.min_val}..{spec.max_val})",
                        node,
                    )
                return _int_term(spec, mag)
        if node["kind"] == "unary" and self._int_spec(expected) is not None:
            res_u = self._elaborate_unary(node, environment, expected_int=expected)
            self.site = node
            self.unify(res_u.type, expected)
            return res_u.term
        if node["kind"] == "binary" and self._int_spec(expected) is not None:
            res_b = self._elaborate_binary(node, environment, expected_int=expected)
            self.site = node
            self.unify(res_b.type, expected)
            return res_b.term
        prev_expected_call = self.expected_call_type
        if node["kind"] == "call":
            self.expected_call_type = expected
        try:
            value = self.expression(node, environment)
        finally:
            self.expected_call_type = prev_expected_call
        self.site = node
        self.unify(value.type, expected)
        return value.term

    def lambda_(self, node: Node, environment: dict[str, _Binding], expected: _Term | None = None) -> _Binding:
        parameter_role = "lambda_parameter"
        if node["kind"] == "typed_lambda":
            parameter_role = "parameter"
            signature = self.type(self.node(node["signature"]), environment)
            if expected is not None:
                self.unify(signature, expected)
            signature_node = self.node(node["signature"], "function_type")
            if self.nodes(signature_node["generics"]):
                raise self.fail("unsupported", "generic lambda telescopes require explicit declarations", node)
            node = {"kind": "lambda", "parameters": signature_node["parameters"], "body": node["body"], "span": node["span"]}
            expected = signature
        parameters = self.nodes(node["parameters"])
        variables: list[_Term] = []
        extended = dict(environment)
        current = expected
        if not parameters:
            variable = self.fresh(_UNIT)
            self.nullary_parameters.add(cast("int", variable.value))
            variables.append(variable)
            if current is not None:
                current = self.whnf(current)
                if current.kind != "pi":
                    raise self.fail("type", "lambda requires a callable expected type", node)
                if cast("int", current.value) not in self.nullary_parameters:
                    raise self.fail("type", "an empty lambda requires a zero-parameter source interface", node)
                self.unify(current.args[0], _UNIT)
                current = self.substitute(current.args[1], cast("int", current.value), variable)
        for parameter in parameters:
            self.site = parameter
            if parameter["kind"] != parameter_role:
                raise self.fail("protocol", "invalid lambda parameter syntax role")
            self.no_roles(parameter, "grade")
            annotation = parameter["type"]
            if annotation is None and parameter_role != "lambda_parameter":
                raise self.fail("protocol", "a declared callable parameter requires a type")
            domain = (self.meta(_SORT, extended) if annotation is None
                      else self.type(self.node(annotation), extended))
            expected_pi = None if current is None else self.whnf(current)
            if expected_pi is not None:
                if expected_pi.kind != "pi":
                    raise self.fail("type", "lambda has more parameters than its expected type")
                if cast("int", expected_pi.value) in self.nullary_parameters:
                    raise self.fail("type", "an explicit lambda parameter cannot satisfy a zero-parameter source interface")
                self.unify(domain, expected_pi.args[0])
            variable = self.fresh(domain)
            variables.append(variable)
            static = cast("bool", parameter.get("const", False))
            if expected_pi is not None:
                expected_static = cast("int", expected_pi.value) in self.constant_parameters
                if annotation is None:
                    static = expected_static
                elif static != expected_static:
                    raise self.fail("type", "lambda constant-parameter requirement differs from its expected type")
            if static:
                self.constant_parameters.add(cast("int", variable.value))
            name = self.name(parameter["name"])
            self.parameter_names[cast("int", variable.value)] = name
            self.bind_local(extended, name, _Binding(variable, domain, constant=static))
            if expected_pi is not None:
                current = self.substitute(expected_pi.args[1], cast("int", expected_pi.value), variable)
        body_node = self.node(node["body"])
        if current is None:
            body = self.block(body_node, extended) if body_node["kind"] == "block" else self.expression(body_node, extended)
        else:
            body = _Binding(self.check(body_node, current, extended), current)
        return _Binding(self.wrap("lam", variables, body.term), self.wrap("pi", variables, body.type))



def _checked_elaboration(
    source: bytes,
    parsed: object,
    *,
    available_modules: dict[str, _Elaborator] | None = None,
) -> tuple[Elaboration, _Elaborator]:
    protocol = _Protocol(source)
    try:
        root = protocol.decode(parsed)
        elaborator = _Elaborator(protocol)
        module = elaborator.name(root["name"])
        elaborator.module_name = module
        if available_modules is not None and available_modules:
            elaborator.available_modules = dict(available_modules)
            elaborator.serial = max(
                elaborator.serial,
                *(mod.serial for mod in available_modules.values()),
            )
        for declaration in elaborator.nodes(root["declarations"]):
            elaborator.declaration(declaration)
        generated_module = "Vela_" + module.replace(".", "_")
        gallina = ("(* SPDX-License-Identifier: Apache-2.0 *)\n"
                   "(* Vela mathematical elaboration: unqualified kernel proposal. "
                   f"Source SHA256: {hashlib.sha256(source).hexdigest()} *)\n"
                   f"Module {generated_module}.\n\n" + _PRELUDE + "\n"
                   + "\n\n".join(elaborator.output) + f"\n\nEnd {generated_module}.\n")
        if len(gallina.encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise protocol.error("limit", "generated Gallina exceeds the output bound")
        return Elaboration(module, gallina), elaborator
    except RecursionError as error:
        raise protocol.error("limit", "elaboration nesting exceeds the host stack bound") from error


def elaborate(
    source: bytes,
    parsed: object,
    *,
    imports: Sequence[tuple[bytes, object]] | None = None,
) -> Elaboration:
    """Check an exact-source schema-2 AST and propose a complete bounded CIC file."""
    available: dict[str, _Elaborator] = {}
    if imports is not None:
        for imp_source, imp_parsed in imports:
            imp_elab, imp_elaborator = _checked_elaboration(
                imp_source, imp_parsed, available_modules=available
            )
            available[imp_elab.module] = imp_elaborator
    return _checked_elaboration(source, parsed, available_modules=available or None)[0]


def elaborate_package(modules: Sequence[tuple[bytes, object]]) -> dict[str, Elaboration]:
    """Elaborate a multi-module package in dependency order, enforcing module visibility."""
    decoded: dict[str, tuple[bytes, object, _Protocol, Node, list[tuple[str, Node]]]] = {}
    order_names: list[str] = []
    for src, parsed in modules:
        protocol = _Protocol(src)
        root = protocol.decode(parsed)
        probe = _Elaborator(protocol)
        mod_name = probe.name(root["name"])
        if mod_name in decoded:
            raise protocol.error("name", f"duplicate module '{mod_name}' in package", root)
        deps = [
            (probe.name(decl["name"]), decl)
            for decl in probe.nodes(root["declarations"])
            if decl["kind"] == "import"
        ]
        decoded[mod_name] = (src, parsed, protocol, root, deps)
        order_names.append(mod_name)

    visited: dict[str, int] = {}
    topo: list[str] = []

    def visit(mod_name: str, call_edge: tuple[_Protocol, Node] | None = None) -> None:
        state = visited.get(mod_name, 0)
        if state == 1:
            if call_edge is not None:
                err_proto, err_node = call_edge
                raise err_proto.error("name", f"circular module import involving '{mod_name}'", err_node)
            _, _, err_proto, err_root, _ = decoded[mod_name]
            raise err_proto.error("name", f"circular module import involving '{mod_name}'", err_root)
        if state == 2:
            return
        visited[mod_name] = 1
        _, _, proto, _, deps = decoded[mod_name]
        for dep_name, imp_node in deps:
            if dep_name == mod_name:
                raise proto.error("name", f"circular module import involving '{mod_name}'", imp_node)
            if dep_name in decoded:
                visit(dep_name, (proto, imp_node))
        visited[mod_name] = 2
        topo.append(mod_name)

    for mname in order_names:
        if visited.get(mname, 0) == 0:
            visit(mname)

    available: dict[str, _Elaborator] = {}
    elaborations: dict[str, Elaboration] = {}
    for mname in topo:
        src, parsed, _, _, _ = decoded[mname]
        elab, elaborator = _checked_elaboration(src, parsed, available_modules=available)
        available[mname] = elaborator
        elaborations[mname] = elab

    return elaborations


def _console_initializer(elaborator: _Elaborator, protocol: _Protocol, parsed: object,
                         prefix_bytes: int, expression_bytes: int) -> Node:
    root = protocol.decode(parsed)
    declarations = elaborator.nodes(root["declarations"])
    if len(declarations) != 1 or declarations[0]["kind"] != "constant":
        raise VelaError("syntax", 3, 1, "expected exactly one constant initializer")
    declaration = declarations[0]
    name = elaborator.name(declaration["name"])
    value = elaborator.node(declaration["value"])
    if (name != "__vela_console_result"
            or declaration["span"] != [len(b"module Playground;\n"), len(protocol.source)]
            or not prefix_bytes <= cast("list[int]", value["span"])[0]
            < cast("list[int]", value["span"])[1] <= prefix_bytes + expression_bytes):
        raise VelaError("syntax", 3, 1, "expected exactly one complete constant initializer")
    return declaration


def _console_value(elaborator: _Elaborator, declaration: Node,
                   value_type: ValueType) -> StaticEvaluation:
    result = elaborator.constant_value(declaration, {})
    normalized = elaborator.whnf(result.term)
    expected = "nat" if value_type == "Nat" else "bool"
    if normalized.kind != expected or elaborator.free(normalized):
        raise VelaError("inference", 1, 1, "constant did not reduce to a closed typed value")
    return StaticEvaluation(value_type, cast("int", normalized.value) if value_type == "Nat"
                            else bool(normalized.value))


def evaluate(source: bytes, parsed: object, expression: str, value_type: ValueType,
             *, parse: Callable[[bytes], object]) -> StaticEvaluation:
    """Reduce one source-bound console constant in the checked module's environment.

    The [mathematical console contract](../../../docs/languages/vela/elaboration-prototype.md#commands-and-acceptance)
    retains the native parser and existing bounded constant reducer.
    """
    _, elaborator = _checked_elaboration(source, parsed)
    if value_type not in {"Nat", "bool"}:
        raise VelaError("type", 1, 1, "expression: expected Nat or bool result type")
    try:
        raw = expression.encode("utf-8")
    except UnicodeEncodeError as error:
        raise VelaError("encoding", 1, 1, "expression: invalid Unicode text") from error
    if len(raw) > 4096:
        raise VelaError("limit", 1, 1, "expression: exceeds 4096 UTF-8 bytes")
    prefix = f"module Playground;\npublic const {value_type} __vela_console_result =\n".encode()
    probe = prefix + raw + b"\n;"
    protocol = _Protocol(probe)
    try:
        declaration = _console_initializer(elaborator, protocol, parse(probe), len(prefix), len(raw))
    except VelaError as error:
        lines = expression.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        line = max(1, error.line - 2)
        column = error.column if line <= len(lines) else len(lines[-1]) + 1
        line = min(line, len(lines))
        column = min(column, len(lines[line - 1]) + 1)
        raise VelaError(error.kind, line, column, f"expression: {error.message}") from error
    except RecursionError as error:
        raise VelaError("limit", 1, 1, "expression: syntax nesting exceeds the host stack bound") from error
    elaborator.protocol = protocol
    try:
        return _console_value(elaborator, declaration, value_type)
    except VelaError as error:
        raise VelaError(error.kind, 1, 1, f"expression: {error.message}") from error
    except RecursionError as error:
        raise VelaError("limit", 1, 1, "expression: elaboration nesting exceeds the host stack bound") from error


