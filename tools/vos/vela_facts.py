# SPDX-License-Identifier: Apache-2.0
"""Bounded diagnostic facts recorded by the pure compiler's own resolver."""

from dataclasses import dataclass
from typing import Literal

from vos.vela_ast import Name, Site, VelaError
from vos.vela_documentation import DocumentationSource

MAX_SYMBOLS = 1024
MAX_OCCURRENCES = 4096
type SymbolKind = Literal["function", "parameter", "variable", "constant"]


@dataclass(frozen=True)
class _Symbol:
    name: Name
    kind: SymbolKind
    detail: str
    inferred: bool | None = None


@dataclass(frozen=True)
class _Occurrence:
    symbol: int
    site: Site
    declaration: bool


class Facts:
    """Collect decisions, without performing name resolution or semantic checks."""

    def __init__(self, source: bytes | None = None,
                 declaration_sites: dict[Site, Site] | None = None) -> None:
        self.symbols: list[_Symbol] = []
        self.occurrences: list[_Occurrence] = []
        self.documentation = None if source is None else DocumentationSource(source)
        self.declaration_sites = {} if declaration_sites is None else dict(declaration_sites)

    def declare(self, name: Name, kind: SymbolKind, detail: str, *, inferred: bool | None = None) -> int:
        if len(self.symbols) >= MAX_SYMBOLS:
            raise VelaError("inspection-limit", name.site.line, name.site.column,
                            "pure inspection exceeds declaration limit")
        identity = len(self.symbols)
        if inferred is not None and (inferred is not False or kind != "variable"):
            raise ValueError("only an explicitly annotated variable carries an inference flag")
        self.symbols.append(_Symbol(name, kind, detail, inferred))
        self.reference(identity, name.site, declaration=True)
        return identity

    def reference(self, identity: int, site: Site, *, declaration: bool = False) -> None:
        if len(self.occurrences) >= MAX_OCCURRENCES:
            raise VelaError("inspection-limit", site.line, site.column,
                            "pure inspection exceeds occurrence limit")
        self.occurrences.append(_Occurrence(identity, site, declaration))

    def result(self) -> dict[str, object]:
        ordered = sorted(enumerate(self.symbols),
                         key=lambda item: (item[1].name.site.line, item[1].name.site.column))
        identities = {old: new for new, (old, _) in enumerate(ordered)}
        symbols: list[dict[str, object]] = [
            {"name": symbol.name.text, "kind": symbol.kind, "detail": symbol.detail,
             "line": symbol.name.site.line, "column": symbol.name.site.column}
            for _, symbol in ordered]
        for data, (_, symbol) in zip(symbols, ordered, strict=True):
            if symbol.inferred is not None:
                data["inferred"] = symbol.inferred
            site = self.declaration_sites.get(symbol.name.site)
            if site is not None and self.documentation is not None:
                try:
                    documentation = self.documentation.at(site)
                except ValueError as error:
                    raise VelaError("inspection-limit", site.line, site.column, str(error)) from error
                if documentation is not None:
                    data["documentation"] = documentation.record()
        occurrences: list[dict[str, object]] = [
            {"symbol": identities[occurrence.symbol], "line": occurrence.site.line,
             "column": occurrence.site.column, "declaration": occurrence.declaration}
            for occurrence in sorted(self.occurrences,
                                     key=lambda item: (item.site.line, item.site.column))]
        return {"status": "ok", "symbols": symbols, "occurrences": occurrences}
