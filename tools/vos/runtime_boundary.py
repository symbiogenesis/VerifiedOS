# SPDX-License-Identifier: Apache-2.0
"""Source-derived runtime boundary inventory and Q47 adversarial/seeded controls.

Implements the host-side source scanner and behavioral fixture evaluator for
[the runtime boundary contract](../../docs/implementation/contracts/runtime-boundary-hardening.md#qualification-record).
Host-source scanning and fixture evaluation never substitute for linked purecap
CHERI target binary qualification, so `exact_native_acceptance` and
`production_admission` are always `False`.
"""

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypedDict

ACTIVE_TARGET_COMPONENTS: tuple[str, ...] = (
    "kernel",
    "supervisor",
    "copy-service",
    "storage",
    "pool",
    "router",
    "dma-service",
    "transactor",
    "inference-admission",
)

OPTIONAL_TARGET_COMPONENTS: tuple[str, ...] = (
    "witness-validator",
    "attested-tls",
    "backup",
)

EXCLUDED_HARNESS_DIRS: frozenset[str] = frozenset({"test", "tests", "host", "build", "out"})

FORBIDDEN_RUNTIME_SYMBOLS: tuple[str, ...] = (
    "atexit",
    "setjmp",
    "longjmp",
    "signal",
    "sigaltstack",
    "environ",
    "getenv",
    "__cxa_throw",
    "_Unwind_Resume",
    "malloc",
    "free",
    "realloc",
    "calloc",
)

UNCONDITIONAL_FORBIDDEN_SYMBOLS: frozenset[str] = frozenset({
    "atexit",
    "setjmp",
    "longjmp",
    "sigaltstack",
    "getenv",
    "__cxa_throw",
    "_Unwind_Resume",
    "malloc",
    "realloc",
    "calloc",
})

CONTEXT_SENSITIVE_SYMBOLS: frozenset[str] = frozenset({"signal", "free", "environ"})

FORBIDDEN_HEADERS: frozenset[str] = frozenset({"signal.h", "setjmp.h", "ucontext.h"})

_INCLUDE_RE = re.compile(r"^\s*#\s*include\s*[<\"]([^>\"]+)[>\"]", re.MULTILINE)
_PREPROC_LINE_RE = re.compile(r"^[ \t]*#(?:[^\r\n\\]|\\\r?\n)*", re.MULTILINE)
_FUNC_PTR_TYPEDEF_RE = re.compile(
    r"\btypedef\s+(.+?)\(\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\(([^;]*)\)\s*;",
    re.DOTALL,
)
_FUNC_PTR_MEMBER_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_\s\*]*?)\(\s*\*\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\(([^;{}]*)\)\s*;",
    re.DOTALL,
)
_FUNC_DECL_RE = re.compile(
    r"(?:^|[;}])\s*(?!typedef\b|return\b|else\b|struct\b|enum\b|union\b)"
    r"((?:const\s+|volatile\s+|struct\s+|enum\s+|unsigned\s+|signed\s+)*"
    r"[A-Za-z_][A-Za-z0-9_]*(?:\s*\*+)?)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;{}]*)\)\s*;",
    re.DOTALL,
)
_EXTERN_DECL_RE = re.compile(
    r"\bextern\s+([^;{}()]+?)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\s*\[[^\]]*\])?\s*;",
    re.DOTALL,
)
_TYPED_LOCAL_RE = re.compile(
    r"\b(?:const\s+|volatile\s+|unsigned\s+|signed\s+|struct\s+|enum\s+)*"
    r"(?:void|char|short|int|long|size_t|ssize_t|bool|_Bool|uint\d+_t|int\d+_t|"
    r"[A-Za-z_][A-Za-z0-9_]*_t)\s*\*?\s*\*?\s*(signal|free|environ)\b"
)


class ExportedDeclaration(TypedDict):
    component: str
    header: str
    kind: Literal["function", "callback_typedef", "callback_field", "extern_state"]
    name: str
    signature: str
    callbacks: list[str]
    mutable_params: list[str]


class ForbiddenSymbolFinding(TypedDict):
    component: str
    file: str
    line: int
    symbol: str
    reason: str


class ComponentBoundarySummary(TypedDict):
    component: str
    present: bool
    optional: bool
    headers: list[str]
    target_sources: list[str]
    excluded_harness_files: list[str]
    exported_count: int
    callback_count: int
    mutable_state_count: int
    forbidden_findings: int


class BoundaryInventory(TypedDict):
    exact_native_acceptance: Literal[False]
    production_admission: Literal[False]
    scope_note: str
    components_scanned: list[str]
    components_absent_optional: list[str]
    components: list[ComponentBoundarySummary]
    exported_declarations: list[ExportedDeclaration]
    callback_boundaries: list[ExportedDeclaration]
    mutable_state_boundaries: list[ExportedDeclaration]
    forbidden_symbol_findings: list[ForbiddenSymbolFinding]


def _strip_c_comments_and_strings(text: str, *, keep_includes: bool = False) -> str:
    """Replace C comments and literals with spaces while preserving line numbers."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_line_comment = False
    in_block_comment = False
    in_string = False
    in_char = False
    at_line_start = True
    in_include_line = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                at_line_start = True
                in_include_line = False
                out.append("\n")
            else:
                out.append(" ")
            i += 1
        elif in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                out.append("  ")
                i += 2
            elif ch == "\n":
                out.append("\n")
                i += 1
            else:
                out.append(" ")
                i += 1
        elif in_string:
            if ch == "\\" and i + 1 < n:
                out.append(" " if nxt != "\n" else " ")
                if nxt == "\n":
                    out.append("\n")
                else:
                    out.append(" ")
                i += 2
            elif ch == '"':
                in_string = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        elif in_char:
            if ch == "\\" and i + 1 < n:
                out.append("  ")
                i += 2
            elif ch == "'":
                in_char = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
        elif ch == "/" and nxt == "/":
            in_line_comment = True
            out.append("  ")
            i += 2
        elif ch == "/" and nxt == "*":
            in_block_comment = True
            out.append("  ")
            i += 2
        elif ch == '"' and not (keep_includes and in_include_line):
            in_string = True
            out.append(" ")
            i += 1
        elif ch == "'":
            in_char = True
            out.append(" ")
            i += 1
        else:
            if ch == "\n":
                at_line_start = True
                in_include_line = False
            elif at_line_start and ch not in " \t\r":
                at_line_start = False
                if keep_includes and text[i:].lstrip().startswith("#include"):
                    in_include_line = True
            out.append(ch)
            i += 1
    return "".join(out)


def _collapse_ws(text: str) -> str:
    return " ".join(text.split())


def _split_params(params: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in params:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur.clear()
        else:
            cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def _is_mutable_pointer_param(param: str) -> bool:
    if not param or param == "void" or "*" not in param:
        return False
    # Check whether the pointed-to target lacks a leading `const` qualifier.
    target = param.split("*", 1)[0].strip()
    return not target.startswith("const ") and " const" not in target


def _parse_header_declarations(
    component: str,
    rel_header: str,
    raw_text: str,
    known_callbacks: set[str],
) -> list[ExportedDeclaration]:
    stripped = _strip_c_comments_and_strings(raw_text)
    no_preproc = _PREPROC_LINE_RE.sub("", stripped)
    decls: list[ExportedDeclaration] = []
    seen: set[tuple[str, str]] = set()

    for match in _FUNC_PTR_TYPEDEF_RE.finditer(no_preproc):
        ret_t, name, params = match.groups()
        known_callbacks.add(name)
        sig = _collapse_ws(f"typedef {ret_t} (*{name})({params})")
        if ("callback_typedef", name) not in seen:
            seen.add(("callback_typedef", name))
            decls.append({
                "component": component,
                "header": rel_header,
                "kind": "callback_typedef",
                "name": name,
                "signature": sig,
                "callbacks": [name],
                "mutable_params": [p for p in _split_params(params) if _is_mutable_pointer_param(p)],
            })

    for match in _FUNC_PTR_MEMBER_RE.finditer(no_preproc):
        ret_t, name, params = match.groups()
        if ret_t.strip().startswith("typedef"):
            continue
        sig = _collapse_ws(f"{ret_t} (*{name})({params})")
        if ("callback_field", name) not in seen:
            seen.add(("callback_field", name))
            decls.append({
                "component": component,
                "header": rel_header,
                "kind": "callback_field",
                "name": name,
                "signature": sig,
                "callbacks": [name],
                "mutable_params": [p for p in _split_params(params) if _is_mutable_pointer_param(p)],
            })

    for match in _EXTERN_DECL_RE.finditer(no_preproc):
        typ, name = match.groups()
        typ_clean = _collapse_ws(typ)
        if typ_clean.startswith("const ") or " const " in f" {typ_clean} ":
            continue
        if ("extern_state", name) not in seen:
            seen.add(("extern_state", name))
            decls.append({
                "component": component,
                "header": rel_header,
                "kind": "extern_state",
                "name": name,
                "signature": f"extern {typ_clean} {name}",
                "callbacks": [],
                "mutable_params": [f"{typ_clean} {name}"],
            })

    for match in _FUNC_DECL_RE.finditer(no_preproc):
        ret_t, name, params = match.groups()
        if name in {"if", "for", "while", "switch", "sizeof"}:
            continue
        param_list = _split_params(params)
        cb_params = [
            p for p in param_list
            if "(*" in p or any(re.search(rf"\b{re.escape(cb)}\b", p) for cb in known_callbacks)
        ]
        mut_params = [p for p in param_list if _is_mutable_pointer_param(p)]
        sig = _collapse_ws(f"{ret_t} {name}({params})")
        if ("function", name) not in seen:
            seen.add(("function", name))
            decls.append({
                "component": component,
                "header": rel_header,
                "kind": "function",
                "name": name,
                "signature": sig,
                "callbacks": cb_params,
                "mutable_params": mut_params,
            })

    return decls


def scan_c_for_forbidden_symbols(
    component: str,
    rel_file: str,
    raw_text: str,
) -> list[ForbiddenSymbolFinding]:
    """Scan a C source or header for forbidden native unwind/runtime symbols."""
    findings: list[ForbiddenSymbolFinding] = []
    comment_stripped = _strip_c_comments_and_strings(raw_text, keep_includes=True)

    for match in _INCLUDE_RE.finditer(comment_stripped):
        header = match.group(1).strip()
        base_header = header.rsplit("/", 1)[-1]
        if base_header in FORBIDDEN_HEADERS:
            line_no = comment_stripped.count("\n", 0, match.start()) + 1
            findings.append({
                "component": component,
                "file": rel_file,
                "line": line_no,
                "symbol": base_header,
                "reason": f"forbidden runtime/unwind header <{header}> included",
            })

    code_only = _strip_c_comments_and_strings(raw_text, keep_includes=False)
    typed_locals: set[str] = {m.group(1) for m in _TYPED_LOCAL_RE.finditer(code_only)}

    for lineno, line in enumerate(code_only.splitlines(), start=1):
        stripped_line = line.strip()
        if not stripped_line:
            continue
        # Remove struct member dereferences `.field` / `->field` before scanning symbols.
        no_members = re.sub(r"(?:\.|->)\s*[A-Za-z_][A-Za-z0-9_]*", " ", line)

        for sym in sorted(UNCONDITIONAL_FORBIDDEN_SYMBOLS):
            if re.search(rf"\b{re.escape(sym)}\b", no_members):
                findings.append({
                    "component": component,
                    "file": rel_file,
                    "line": lineno,
                    "symbol": sym,
                    "reason": f"forbidden native unwind/runtime symbol `{sym}`",
                })

        for sym in sorted(CONTEXT_SENSITIVE_SYMBOLS):
            if re.search(rf"\b{re.escape(sym)}\s*\(", no_members):
                findings.append({
                    "component": component,
                    "file": rel_file,
                    "line": lineno,
                    "symbol": sym,
                    "reason": f"forbidden native runtime call `{sym}(...)`",
                })
            elif re.search(rf"\bextern\b[^;]*\b{re.escape(sym)}\b", no_members):
                findings.append({
                    "component": component,
                    "file": rel_file,
                    "line": lineno,
                    "symbol": sym,
                    "reason": f"forbidden external runtime symbol `{sym}`",
                })
            elif sym == "environ" and re.search(r"\benviron\b", no_members) and sym not in typed_locals:
                findings.append({
                    "component": component,
                    "file": rel_file,
                    "line": lineno,
                    "symbol": sym,
                    "reason": "forbidden shared Unix runtime symbol `environ`",
                })
            elif (
                sym in {"signal", "free"}
                and re.search(rf"\b{re.escape(sym)}\b", no_members)
                and sym not in typed_locals
            ):
                findings.append({
                    "component": component,
                    "file": rel_file,
                    "line": lineno,
                    "symbol": sym,
                    "reason": f"undeclared reference to forbidden runtime symbol `{sym}`",
                })

    return findings


def _is_harness_path(component_dir: Path, path: Path) -> bool:
    rel_parts = path.relative_to(component_dir).parts
    return any(part in EXCLUDED_HARNESS_DIRS for part in rel_parts[:-1])


def scan_boundary_inventory(
    root: Path,
    extra_components: tuple[str, ...] = (),
) -> BoundaryInventory:
    """Discover target C headers and sources directly from `root` and audit boundaries."""
    ordered_specs: list[tuple[str, bool]] = [
        *((name, False) for name in ACTIVE_TARGET_COMPONENTS),
        *((name, True) for name in OPTIONAL_TARGET_COMPONENTS),
        *((name, False) for name in extra_components if name not in ACTIVE_TARGET_COMPONENTS),
    ]

    components_scanned: list[str] = []
    components_absent_optional: list[str] = []
    component_summaries: list[ComponentBoundarySummary] = []
    all_decls: list[ExportedDeclaration] = []
    all_findings: list[ForbiddenSymbolFinding] = []
    known_callbacks: set[str] = set()

    # First pass collects callback typedef names across headers so function signatures
    # referencing typedefs in other headers (e.g. `vos_kernel_effect_state`) resolve cleanly.
    headers_by_comp: dict[str, list[Path]] = {}
    for comp, optional in ordered_specs:
        comp_dir = root / comp
        if not comp_dir.is_dir():
            if optional:
                components_absent_optional.append(comp)
            continue
        inc_dir = comp_dir / "include"
        hdrs = sorted(inc_dir.rglob("*.h")) if inc_dir.is_dir() else []
        headers_by_comp[comp] = hdrs
        for hdr in hdrs:
            stripped = _strip_c_comments_and_strings(hdr.read_text(encoding="utf-8", errors="replace"))
            no_preproc = _PREPROC_LINE_RE.sub("", stripped)
            for m in _FUNC_PTR_TYPEDEF_RE.finditer(no_preproc):
                known_callbacks.add(m.group(2))

    for comp, optional in ordered_specs:
        comp_dir = root / comp
        if not comp_dir.is_dir():
            continue
        components_scanned.append(comp)
        hdrs = headers_by_comp.get(comp, [])
        all_c = sorted(comp_dir.rglob("*.c"))
        target_sources = [p for p in all_c if not _is_harness_path(comp_dir, p)]
        excluded_harness = [p for p in all_c if _is_harness_path(comp_dir, p)]

        comp_decls: list[ExportedDeclaration] = []
        comp_findings: list[ForbiddenSymbolFinding] = []

        for hdr in hdrs:
            rel_hdr = hdr.relative_to(root).as_posix()
            raw = hdr.read_text(encoding="utf-8", errors="replace")
            comp_decls.extend(_parse_header_declarations(comp, rel_hdr, raw, known_callbacks))
            comp_findings.extend(scan_c_for_forbidden_symbols(comp, rel_hdr, raw))

        for src in target_sources:
            rel_src = src.relative_to(root).as_posix()
            raw = src.read_text(encoding="utf-8", errors="replace")
            comp_findings.extend(scan_c_for_forbidden_symbols(comp, rel_src, raw))

        all_decls.extend(comp_decls)
        all_findings.extend(comp_findings)

        cb_count = sum(
            1 for d in comp_decls if d["kind"] in {"callback_typedef", "callback_field"} or d["callbacks"]
        )
        mut_count = sum(1 for d in comp_decls if d["mutable_params"] or d["kind"] == "extern_state")
        component_summaries.append({
            "component": comp,
            "present": True,
            "optional": optional,
            "headers": [h.relative_to(root).as_posix() for h in hdrs],
            "target_sources": [s.relative_to(root).as_posix() for s in target_sources],
            "excluded_harness_files": [s.relative_to(root).as_posix() for s in excluded_harness],
            "exported_count": len(comp_decls),
            "callback_count": cb_count,
            "mutable_state_count": mut_count,
            "forbidden_findings": len(comp_findings),
        })

    callback_boundaries = [
        d for d in all_decls if d["kind"] in {"callback_typedef", "callback_field"} or d["callbacks"]
    ]
    mutable_state_boundaries = [
        d for d in all_decls if d["mutable_params"] or d["kind"] == "extern_state"
    ]

    return {
        "exact_native_acceptance": False,
        "production_admission": False,
        "scope_note": (
            "Host-source boundary inventory and forbidden-symbol audit only; "
            "supplies no linked purecap CHERI target binary admission verdict."
        ),
        "components_scanned": components_scanned,
        "components_absent_optional": components_absent_optional,
        "components": component_summaries,
        "exported_declarations": all_decls,
        "callback_boundaries": callback_boundaries,
        "mutable_state_boundaries": mutable_state_boundaries,
        "forbidden_symbol_findings": all_findings,
    }


# ---------------------------------------------------------------------------
# Q47 Adversarial Callback & Teardown Fixture Evaluator + Seeded Defects
# ---------------------------------------------------------------------------

type CallbackDefect = Literal[
    "none",
    "drop-object-id-check",
    "drop-range-check",
    "drop-utf8-check",
    "trust-iterator-len",
    "allow-reentrant-drop",
    "expose-uninitialized-prefix",
]

type TeardownDefect = Literal[
    "none",
    "reuse-with-pending-dma",
    "reuse-with-queued-reply",
    "unwind-cleanup-on-abandon",
    "skip-memgrow-view-invalidation",
]

type HolderClass = Literal[
    "RunningHart",
    "SavedContext",
    "RegisteredHandle",
    "PeerCap",
    "QueuedReply",
    "OutstandingDma",
]

ALL_HOLDER_CLASSES: tuple[HolderClass, ...] = (
    "RunningHart",
    "SavedContext",
    "RegisteredHandle",
    "PeerCap",
    "QueuedReply",
    "OutstandingDma",
)


@dataclass(frozen=True)
class ObjectId:
    generation: int
    slot: int


@dataclass(frozen=True)
class SliceView:
    obj: ObjectId
    data: bytes
    cap: int
    length: int
    init_prefix: int

    def valid(self) -> bool:
        return 0 <= self.init_prefix <= self.length <= self.cap <= len(self.data)


@dataclass(frozen=True)
class ValidatedRange:
    obj: ObjectId
    start: int
    end: int
    require_utf8: bool = True


def utf8_valid_bytes(data: bytes) -> bool:
    """Validate strict RFC 3629 UTF-8 byte sequences."""
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    return True


def checked_slice_substr(
    view: SliceView,
    rng: ValidatedRange,
    defect: CallbackDefect = "none",
) -> bytes | None:
    if not view.valid():
        return None
    if defect != "drop-object-id-check" and rng.obj != view.obj:
        return None
    bound = view.length if defect == "expose-uninitialized-prefix" else view.init_prefix
    if defect != "drop-range-check" and not (0 <= rng.start <= rng.end <= bound):
        return None
    sub = view.data[rng.start:rng.end]
    if defect != "drop-utf8-check" and rng.require_utf8 and not utf8_valid_bytes(sub):
        return None
    return sub


def two_pass_extract(
    pass1: SliceView,
    pass2: SliceView,
    expected_obj: ObjectId,
    dst_cap: int,
    defect: CallbackDefect = "none",
) -> bytes | None:
    if not pass1.valid() or not pass2.valid():
        return None
    if defect != "drop-object-id-check" and (
        pass1.obj != expected_obj or pass2.obj != expected_obj
    ):
        return None
    if pass1.init_prefix > dst_cap or pass2.init_prefix > dst_cap:
        return None
    if pass2.init_prefix < pass1.init_prefix:
        return None
    return pass2.data[: pass1.init_prefix]


@dataclass
class CollectionState:
    obj: ObjectId
    buf: bytearray
    cap: int
    length: int = 0
    init_prefix: int = 0
    reentry_locked: bool = False
    owned: bool = True
    dropped: bool = False
    drop_count: int = 0

    def invariant_ok(self) -> bool:
        bounds_ok = 0 <= self.init_prefix <= self.length <= self.cap <= len(self.buf)
        drop_ok = self.drop_count <= 1 and (
            (not self.dropped and self.drop_count == 0)
            or (self.dropped and not self.owned and self.init_prefix == 0 and self.length == 0 and self.drop_count == 1)
        )
        return bounds_ok and drop_ok


def iter_collect(
    st: CollectionState,
    reported_len: int,
    items: list[int],
    defect: CallbackDefect = "none",
) -> bool:
    if st.reentry_locked or not st.owned or st.dropped:
        return False
    if defect == "trust-iterator-len":
        # Defective mutant trusts lying `reported_len` as initialized length.
        st.length = reported_len
        st.init_prefix = reported_len
        return True
    written = 0
    for byte in items:
        if st.length >= st.cap or not (0 <= byte < 256):
            break
        st.buf[st.length] = byte
        st.length += 1
        st.init_prefix += 1
        written += 1
    return written == len(items)


def safe_binary_search_with_adversarial_cmp(
    view: SliceView,
    cmp_answers: list[int],
) -> int | None:
    if not view.valid() or view.init_prefix == 0:
        return None
    lo = 0
    hi = view.init_prefix
    steps = 0
    while lo < hi and steps < len(cmp_answers):
        mid = lo + (hi - lo) // 2
        ans = cmp_answers[steps]
        steps += 1
        if ans == 0:
            return mid
        if ans < 0:
            lo = mid + 1
        else:
            hi = mid
    return None


def run_reentrant_callback(
    st: CollectionState,
    reenter: bool = False,
    drop_inside: bool = False,
    defect: CallbackDefect = "none",
) -> tuple[bool, bool]:
    """Return `(outer_ok, reentry_or_double_drop_rejected)`."""
    if st.reentry_locked or not st.owned or st.dropped:
        return (False, True)
    st.reentry_locked = True
    rejected = True
    try:
        if reenter and st.reentry_locked:
            rejected = True
        if drop_inside:
            dropped_inner = drop_collection(st, defect=defect)
            rejected = not dropped_inner
    finally:
        st.reentry_locked = False
    return (True, rejected)


def drop_collection(st: CollectionState, defect: CallbackDefect = "none") -> bool:
    if defect != "allow-reentrant-drop" and (st.reentry_locked or not st.owned or st.dropped):
        return False
    _ = bytes(st.buf[: st.init_prefix])
    st.init_prefix = 0
    st.length = 0
    st.owned = False
    st.dropped = True
    st.drop_count += 1
    return True


@dataclass(frozen=True)
class HolderEntry:
    cls: HolderClass
    ctx: int
    backing: ObjectId
    active: bool = True


@dataclass(frozen=True)
class GuestView:
    epoch: int
    obj: ObjectId
    base: int
    length: int
    live: bool = True


@dataclass
class RuntimeTeardownState:
    backing: ObjectId
    phase: Literal["live", "quarantined", "reusable"] = "live"
    zeroized: bool = False
    holders: list[HolderEntry] = field(default_factory=list)
    abandoned: bool = False
    cleanup_frames_run: int = 0
    dtor_reclaims_run: int = 0
    native_frames_unwound: int = 0
    guest_views: list[GuestView] = field(default_factory=list)
    mem_epoch: int = 0


def native_abandon(st: RuntimeTeardownState, defect: TeardownDefect = "none") -> None:
    st.abandoned = True
    if st.phase == "live":
        st.phase = "quarantined"
    if defect == "unwind-cleanup-on-abandon":
        st.cleanup_frames_run += 1
        st.dtor_reclaims_run += 1
        st.native_frames_unwound += 1


def disable_caller_registration(st: RuntimeTeardownState, caller_ctx: int) -> None:
    st.holders = [
        HolderEntry(h.cls, h.ctx, h.backing, False)
        if h.cls == "RegisteredHandle" and h.ctx == caller_ctx and h.backing == st.backing
        else h
        for h in st.holders
    ]


def retire_holder(st: RuntimeTeardownState, cls: HolderClass, ctx: int) -> None:
    st.holders = [
        HolderEntry(h.cls, h.ctx, h.backing, False)
        if h.cls == cls and h.ctx == ctx
        else h
        for h in st.holders
    ]


def try_zeroize_and_reuse(
    st: RuntimeTeardownState,
    new_backing: ObjectId,
    defect: TeardownDefect = "none",
) -> bool:
    if st.phase != "quarantined":
        return False
    for h in st.holders:
        if not h.active:
            continue
        if defect == "reuse-with-pending-dma" and h.cls == "OutstandingDma":
            continue
        if defect == "reuse-with-queued-reply" and h.cls == "QueuedReply":
            continue
        return False
    st.zeroized = True
    st.phase = "reusable"
    st.backing = new_backing
    return True


def guest_trap_cancel_or_grow(
    st: RuntimeTeardownState,
    *,
    grow_mem: bool,
    defect: TeardownDefect = "none",
) -> None:
    if grow_mem:
        st.mem_epoch += 1
    if defect != "skip-memgrow-view-invalidation":
        st.guest_views = [
            GuestView(gv.epoch, gv.obj, gv.base, gv.length, False)
            for gv in st.guest_views
        ]


@dataclass(frozen=True)
class ControlVerdict:
    name: str
    passed: bool
    detail: str


def run_adversarial_controls(
    cb_defect: CallbackDefect = "none",
    td_defect: TeardownDefect = "none",
) -> list[ControlVerdict]:
    """Run all Q47 positive and negative adversarial callback & teardown controls."""
    verdicts: list[ControlVerdict] = []
    oid1 = ObjectId(1, 1)
    oid2 = ObjectId(1, 2)

    # 1. Valid operation positive control
    v_ok = SliceView(oid1, b"hello", 5, 5, 5)
    sub_ok = checked_slice_substr(v_ok, ValidatedRange(oid1, 0, 5, True), defect=cb_defect)
    verdicts.append(ControlVerdict("valid_operation", sub_ok == b"hello", f"got {sub_ok!r}"))

    # 2. Foreign-string range negative control
    v_short = SliceView(oid2, b"abc", 3, 3, 3)
    foreign = checked_slice_substr(v_short, ValidatedRange(oid1, 0, 2, True), defect=cb_defect)
    verdicts.append(ControlVerdict("foreign_string_range", foreign is None, f"got {foreign!r}"))

    # 3. Non-ASCII invalid UTF-8 negative control
    v_bad_utf8 = SliceView(oid1, b"\xff\x80ab", 4, 4, 4)
    bad_utf8 = checked_slice_substr(v_bad_utf8, ValidatedRange(oid1, 0, 2, True), defect=cb_defect)
    verdicts.append(ControlVerdict("non_ascii_utf8_violation", bad_utf8 is None, f"got {bad_utf8!r}"))

    # 4. Partial initialization negative control
    v_partial = SliceView(oid1, b"ab\x00\x00", 4, 4, 2)
    uninit = checked_slice_substr(v_partial, ValidatedRange(oid1, 0, 4, True), defect=cb_defect)
    verdicts.append(ControlVerdict("partial_initialization", uninit is None, f"got {uninit!r}"))

    # 5. Changing borrow (two-pass shrinkage and object switch)
    p1 = SliceView(oid1, b"abcd", 4, 4, 4)
    p2_shrunk = SliceView(oid1, b"a\x00\x00\x00", 4, 1, 1)
    p2_foreign = SliceView(oid2, b"wxyz", 4, 4, 4)
    verdicts.append(ControlVerdict(
        "changing_borrow_shrink",
        two_pass_extract(p1, p2_shrunk, oid1, 4, defect=cb_defect) is None,
        "shrunk pass-2 borrow refused",
    ))
    verdicts.append(ControlVerdict(
        "changing_borrow_object_switch",
        two_pass_extract(p1, p2_foreign, oid1, 4, defect=cb_defect) is None,
        "object-switched pass-2 borrow refused",
    ))

    # 6. False iterator length (lying size_hint = 1000 vs 2 items)
    col = CollectionState(oid1, bytearray(4), 4)
    iter_collect(col, 1000, [65, 66], defect=cb_defect)
    verdicts.append(ControlVerdict(
        "false_iterator_length",
        col.invariant_ok() and col.init_prefix == 2 and col.length == 2,
        f"init={col.init_prefix}, len={col.length}, inv={col.invariant_ok()}",
    ))

    # 7. Inconsistent comparator in binary search
    idx = safe_binary_search_with_adversarial_cmp(v_ok, [-1, 1, -1, 1, 0])
    verdicts.append(ControlVerdict(
        "inconsistent_comparator",
        idx is None or (0 <= idx < v_ok.init_prefix),
        f"idx={idx!r}",
    ))

    # 8. Reentrant drop / double drop
    outer_ok, inner_rejected = run_reentrant_callback(col, reenter=True, drop_inside=True, defect=cb_defect)
    d1 = drop_collection(col, defect=cb_defect)
    d2 = drop_collection(col, defect=cb_defect)
    verdicts.append(ControlVerdict(
        "reentrant_drop_and_exit",
        outer_ok and inner_rejected and d1 and (not d2) and col.invariant_ok() and col.drop_count == 1,
        f"outer={outer_ok}, inner_rejected={inner_rejected}, d1={d1}, d2={d2}, count={col.drop_count}",
    ))

    # 9. Native abandonment: 0 cleanup frames, 0 dtor reclaims, 0 native unwinds
    holders = [HolderEntry(cls, idx, oid1, True) for idx, cls in enumerate(ALL_HOLDER_CLASSES)]
    td = RuntimeTeardownState(backing=oid1, phase="live", holders=holders, guest_views=[GuestView(0, oid1, 0, 4, True)])
    native_abandon(td, defect=td_defect)
    verdicts.append(ControlVerdict(
        "native_abandonment_no_unwind",
        td.abandoned and td.phase == "quarantined" and td.cleanup_frames_run == 0
        and td.dtor_reclaims_run == 0 and td.native_frames_unwound == 0,
        f"cleanup={td.cleanup_frames_run}, dtor={td.dtor_reclaims_run}, unwind={td.native_frames_unwound}",
    ))

    # 10. Disabling caller registration leaves other contexts & classes active
    disable_caller_registration(td, 2)
    still_active = [h.cls for h in td.holders if h.active]
    verdicts.append(ControlVerdict(
        "missing_retirement_ack_other_holders",
        "RegisteredHandle" not in still_active and len(still_active) == 5
        and not try_zeroize_and_reuse(td, oid2, defect=td_defect)
        and td.phase == "quarantined" and not td.zeroized,
        f"active={still_active}",
    ))

    # 11. Late DMA / late queued reply each independently prevent reuse until retired
    for idx, cls in enumerate(ALL_HOLDER_CLASSES):
        if cls in {"RegisteredHandle", "QueuedReply", "OutstandingDma"}:
            continue
        retire_holder(td, cls, idx)
    td_reply_only = RuntimeTeardownState(
        backing=oid1,
        phase="quarantined",
        holders=[HolderEntry("QueuedReply", 4, oid1, True)],
        abandoned=True,
    )
    td_dma_only = RuntimeTeardownState(
        backing=oid1,
        phase="quarantined",
        holders=[HolderEntry("OutstandingDma", 5, oid1, True)],
        abandoned=True,
    )
    refused_with_reply = not try_zeroize_and_reuse(td_reply_only, oid2, defect=td_defect)
    refused_with_dma = not try_zeroize_and_reuse(td_dma_only, oid2, defect=td_defect)
    retire_holder(td, "QueuedReply", 4)
    retire_holder(td, "OutstandingDma", 5)
    reused_clean = try_zeroize_and_reuse(td, oid2, defect=td_defect)
    verdicts.append(ControlVerdict(
        "late_dma_or_reply",
        refused_with_reply and refused_with_dma and reused_clean and td.zeroized and td.phase == "reusable",
        f"refused_reply={refused_with_reply}, refused_dma={refused_with_dma}, reused={reused_clean}",
    ))

    # 12. Guest trap/cancel/memory growth never unwinds native and invalidates views
    guest_trap_cancel_or_grow(td, grow_mem=True, defect=td_defect)
    verdicts.append(ControlVerdict(
        "guest_trap_cancel_memgrow",
        td.native_frames_unwound == 0 and td.mem_epoch == 1 and all(not gv.live for gv in td.guest_views),
        f"unwound={td.native_frames_unwound}, epoch={td.mem_epoch}",
    ))

    return verdicts


class SeededDefectReport(TypedDict):
    total_mutants: int
    executed_kills: int
    stillborn_mutants: int
    survivors: list[str]


def run_seeded_defect_matrix() -> SeededDefectReport:
    """Verify both behavioral mutants and injected-symbol mutants are killed."""
    survivors: list[str] = []
    total = 0
    kills = 0

    cb_mutants: tuple[CallbackDefect, ...] = (
        "drop-object-id-check",
        "drop-range-check",
        "drop-utf8-check",
        "trust-iterator-len",
        "allow-reentrant-drop",
        "expose-uninitialized-prefix",
    )
    for mutant in cb_mutants:
        total += 1
        verdicts = run_adversarial_controls(cb_defect=mutant)
        if all(v.passed for v in verdicts):
            survivors.append(f"callback:{mutant}")
        else:
            kills += 1

    td_mutants: tuple[TeardownDefect, ...] = (
        "reuse-with-pending-dma",
        "reuse-with-queued-reply",
        "unwind-cleanup-on-abandon",
        "skip-memgrow-view-invalidation",
    )
    for mutant in td_mutants:
        total += 1
        verdicts = run_adversarial_controls(td_defect=mutant)
        if all(v.passed for v in verdicts):
            survivors.append(f"teardown:{mutant}")
        else:
            kills += 1

    # Source-scanner seeded mutants (forbidden native unwind/runtime symbols)
    symbol_snippets: dict[str, str] = {
        "atexit": "void f(void (*cb)(void)) { atexit(cb); }\n",
        "setjmp": "#include <setjmp.h>\nvoid f(jmp_buf b) { setjmp(b); }\n",
        "longjmp": "void f(void *b) { longjmp(b, 1); }\n",
        "signal": "#include <signal.h>\nvoid f(void (*h)(int)) { signal(2, h); }\n",
        "sigaltstack": "void f(void *ss) { sigaltstack(ss, 0); }\n",
        "environ": "extern char **environ;\nchar *f(void) { return environ[0]; }\n",
        "getenv": "char *f(const char *k) { return getenv(k); }\n",
        "__cxa_throw": "void f(void *p) { __cxa_throw(p, 0, 0); }\n",
        "_Unwind_Resume": "void f(void *p) { _Unwind_Resume(p); }\n",
        "malloc": "void *f(unsigned n) { return malloc(n); }\n",
        "free": "void f(void *p) { free(p); }\n",
        "realloc": "void *f(void *p, unsigned n) { return realloc(p, n); }\n",
        "calloc": "void *f(unsigned n) { return calloc(n, 1); }\n",
    }
    with tempfile.TemporaryDirectory(prefix="vos-q47-seed-") as td:
        root = Path(td)
        for sym, code in symbol_snippets.items():
            total += 1
            comp_dir = root / "kernel"
            (comp_dir / "src").mkdir(parents=True, exist_ok=True)
            (comp_dir / "include").mkdir(parents=True, exist_ok=True)
            (comp_dir / "src" / "seeded.c").write_text(code, encoding="utf-8", newline="")
            inv = scan_boundary_inventory(root)
            detected = {f["symbol"] for f in inv["forbidden_symbol_findings"]}
            if sym in detected or (sym == "signal" and "signal.h" in detected) or (sym == "setjmp" and "setjmp.h" in detected):
                kills += 1
            else:
                survivors.append(f"symbol:{sym}")

    return {
        "total_mutants": total,
        "executed_kills": kills,
        "stillborn_mutants": 0,
        "survivors": survivors,
    }
