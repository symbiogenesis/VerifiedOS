# SPDX-License-Identifier: Apache-2.0
"""Host observation accounting for the composed-roster measurement contract.

The producer owns capture completeness and attribution. This reader checks the
declared finite window, its identities, and observed resource use; it supplies no
target acceptance, authority-death proof, or containment bound.
"""

import json
import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
from typing import Never, cast

from vos.jsonc import Json

SCOPE = "host capture analysis; target acceptance pending"
IDENTITY_KEYS = {"roster_revision", "image_sha256", "composition_sha256"}


@dataclass(frozen=True)
class ExpectedIdentity:
    roster_revision: str
    image_sha256: str
    composition_sha256: str
    capture_sha256: str


@dataclass(frozen=True)
class Domain:
    name: str
    period_ticks: int
    background_ticks_per_period: int
    quarantine_capacity_bytes: int


@dataclass(frozen=True)
class Teardown:
    name: str
    domain: str
    retire_tick: int
    reuse_tick: int
    swept_capability_bytes: int
    quarantined_bytes: int


@dataclass(frozen=True)
class Quantum:
    domain: str
    start_tick: int
    end_tick: int


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _noninteger(_value: str) -> Never:
    raise ValueError("floating-point and non-finite JSON numbers are unsupported")


def _load(raw: bytes) -> Json:
    try:
        return cast(Json, json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                                    parse_float=_noninteger, parse_constant=_noninteger))
    except RecursionError as err:
        raise ValueError("JSON nesting exceeds the decoder limit") from err


def _object(value: Json, keys: set[str], what: str) -> dict[str, Json]:
    if not isinstance(value, dict) or value.keys() != keys:
        raise ValueError(f"{what} has missing or unknown fields")
    return value


def _rows(value: Json, what: str) -> list[Json]:
    if not isinstance(value, list):
        raise TypeError(f"{what} must be an array")
    return value


def _integer(value: object, what: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{what} must be an integer at least {minimum}, never bool or float")
    return value


def _name(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must be a nonempty identifier")
    return value


def _digest(value: object, what: str, *, revision: bool = False) -> str:
    widths = (40, 64) if revision else (64,)
    if (not isinstance(value, str) or len(value) not in widths
            or re.fullmatch(r"[0-9a-fA-F]+", value) is None):
        raise ValueError(f"{what} must be a full {'Git object ID' if revision else 'SHA-256 digest'}")
    return value.lower()


def expected_identity(raw: bytes) -> ExpectedIdentity:
    """Decode independently supplied expectations, with no self-binding fallback."""
    row = _object(_load(raw), IDENTITY_KEYS | {"capture_sha256"}, "expected identity")
    return ExpectedIdentity(
        _digest(row["roster_revision"], "roster_revision", revision=True),
        _digest(row["image_sha256"], "image_sha256"),
        _digest(row["composition_sha256"], "composition_sha256"),
        _digest(row["capture_sha256"], "capture_sha256"),
    )


def _domains(raw: Json, start: int, end: int) -> tuple[Domain, ...]:
    domains: dict[str, Domain] = {}
    for value in _rows(raw, "domains"):
        row = _object(value, {"id", "period_ticks", "background_ticks_per_period",
                              "quarantine_capacity_bytes"}, "domain")
        name = _name(row["id"], "domain id")
        period = _integer(row["period_ticks"], "period_ticks", 1)
        budget = _integer(row["background_ticks_per_period"], "background_ticks_per_period", 1)
        capacity = _integer(row["quarantine_capacity_bytes"], "quarantine_capacity_bytes", 1)
        if name in domains:
            raise ValueError(f"duplicate domain: {name!r}")
        if start % period or end % period or budget > period:
            raise ValueError(f"domain {name!r}: unaligned observation or budget exceeds period")
        domains[name] = Domain(name, period, budget, capacity)
    if not domains:
        raise ValueError("domains must declare at least one accounting bucket")
    return tuple(domains.values())


def _teardowns(raw: Json, start: int, end: int, domains: set[str]) -> tuple[Teardown, ...]:
    rows: list[Teardown] = []
    seen: set[str] = set()
    for value in _rows(raw, "teardowns"):
        row = _object(value, {"id", "domain", "retire_tick", "reuse_tick",
                              "swept_capability_bytes", "quarantined_bytes"}, "teardown")
        name = _name(row["id"], "teardown id")
        domain = _name(row["domain"], "teardown domain")
        retire = _integer(row["retire_tick"], "retire_tick")
        reuse = _integer(row["reuse_tick"], "reuse_tick")
        swept = _integer(row["swept_capability_bytes"], "swept_capability_bytes")
        amount = _integer(row["quarantined_bytes"], "quarantined_bytes")
        if name in seen or domain not in domains:
            raise ValueError(f"teardown {name!r}: duplicate identity or unknown domain")
        if not start <= retire < end or not retire <= reuse <= end or (amount and retire == reuse):
            raise ValueError(f"teardown {name!r}: unfinished or invalid quarantine interval")
        seen.add(name)
        rows.append(Teardown(name, domain, retire, reuse, swept, amount))
    return tuple(rows)


def _quanta(raw: Json, start: int, end: int, domains: set[str]) -> tuple[Quantum, ...]:
    rows: list[Quantum] = []
    for value in _rows(raw, "sweep_quanta"):
        row = _object(value, {"domain", "start_tick", "end_tick"}, "sweep quantum")
        domain = _name(row["domain"], "quantum domain")
        begin = _integer(row["start_tick"], "quantum start_tick")
        stop = _integer(row["end_tick"], "quantum end_tick")
        if domain not in domains or not start <= begin < stop <= end:
            raise ValueError("sweep quantum has an unknown domain or invalid interval")
        rows.append(Quantum(domain, begin, stop))
    previous: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: (item.domain, item.start_tick)):
        if row.start_tick < previous.get(row.domain, start):
            raise ValueError(f"domain {row.domain!r}: overlapping sweep quanta")
        previous[row.domain] = row.end_tick
    return tuple(rows)


def _ratio(numerator: int, denominator: int) -> dict[str, Json]:
    value = Fraction(numerator, denominator)
    return {"numerator": value.numerator, "denominator": value.denominator}


def _peak_quarantine(rows: tuple[Teardown, ...]) -> int:
    deltas: dict[int, int] = {}
    for row in rows:
        deltas[row.retire_tick] = deltas.get(row.retire_tick, 0) + row.quarantined_bytes
        deltas[row.reuse_tick] = deltas.get(row.reuse_tick, 0) - row.quarantined_bytes
    running = peak = 0
    for tick in sorted(deltas):
        running += deltas[tick]
        peak = max(peak, running)
    return peak


def _peak_period_service(rows: tuple[Quantum, ...], period: int) -> int:
    """Split quanta at period boundaries without expanding long or idle windows.

    Edge periods carry partial charges. Entire interior periods contribute a
    constant run represented by two deltas, so even a huge tick coordinate costs
    work proportional to the number of recorded quanta, not elapsed ticks.
    """
    edges: dict[int, int] = {}
    deltas: dict[int, int] = {}
    for row in rows:
        first, last = row.start_tick // period, (row.end_tick - 1) // period
        if first == last:
            edges[first] = edges.get(first, 0) + row.end_tick - row.start_tick
        else:
            edges[first] = edges.get(first, 0) + period - row.start_tick % period
            edges[last] = edges.get(last, 0) + (row.end_tick - 1) % period + 1
            if last > first + 1:
                deltas[first + 1] = deltas.get(first + 1, 0) + period
                deltas[last] = deltas.get(last, 0) - period
    running = peak = 0
    for index in sorted(edges.keys() | deltas.keys()):
        running += deltas.get(index, 0)
        peak = max(peak, running + edges.get(index, 0))
    return peak


def _measure(rows: tuple[Teardown, ...], duration: int, tick_hz: int) -> dict[str, Json]:
    footprint = sum(row.swept_capability_bytes for row in rows)
    return {
        "teardown_count": len(rows),
        "teardowns_per_second": _ratio(len(rows) * tick_hz, duration),
        "swept_capability_bytes_total": footprint,
        "swept_capability_bytes_mean": _ratio(footprint, len(rows)) if rows else None,
        "swept_capability_bytes_max": max((row.swept_capability_bytes for row in rows), default=0),
        "quarantine_peak_bytes": _peak_quarantine(rows),
    }


def analyze(raw: bytes, expected: ExpectedIdentity) -> dict[str, Json]:
    """Account for a declared capture or refuse with TypeError or ValueError."""
    # Validate direct API callers too; a dataclass annotation is not a decoder.
    expected = expected_identity(json.dumps(asdict(expected)).encode("utf-8"))
    if sha256(raw).hexdigest() != expected.capture_sha256:
        raise ValueError("capture bytes do not match expected capture_sha256")
    capture = _object(_load(raw), {"schema_version", "identity", "window", "complete",
                                   "domains", "teardowns", "sweep_quanta"}, "capture")
    if _integer(capture["schema_version"], "schema_version", 1) != 1:
        raise ValueError("unsupported allocation-churn schema_version")
    if capture["complete"] is not True:
        raise ValueError("unfinished capture: complete must be true")
    identity = _object(capture["identity"], IDENTITY_KEYS, "capture identity")
    for key in sorted(IDENTITY_KEYS):
        if _digest(identity[key], key, revision=key == "roster_revision") != getattr(expected, key):
            raise ValueError(f"capture {key} does not match expected identity")
    window = _object(capture["window"], {"start_tick", "end_tick", "tick_hz"}, "window")
    start = _integer(window["start_tick"], "start_tick")
    end = _integer(window["end_tick"], "end_tick")
    tick_hz = _integer(window["tick_hz"], "tick_hz", 1)
    if end <= start:
        raise ValueError("observation window must have positive duration")
    domains = _domains(capture["domains"], start, end)
    names = {domain.name for domain in domains}
    teardowns = _teardowns(capture["teardowns"], start, end, names)
    quanta = _quanta(capture["sweep_quanta"], start, end, names)
    findings: list[Json] = []
    domain_reports: list[Json] = []
    for domain in domains:
        events = tuple(row for row in teardowns if row.domain == domain.name)
        service = tuple(row for row in quanta if row.domain == domain.name)
        if any(row.swept_capability_bytes for row in events) and not service:
            raise ValueError(f"domain {domain.name!r}: swept footprint has no recorded sweep service")
        peak_bytes = _peak_quarantine(events)
        peak_ticks = _peak_period_service(service, domain.period_ticks)
        if peak_bytes > domain.quarantine_capacity_bytes:
            findings.append(f"domain {domain.name}: quarantine peak {peak_bytes} exceeds "
                            f"capacity {domain.quarantine_capacity_bytes}")
        if peak_ticks > domain.background_ticks_per_period:
            findings.append(f"domain {domain.name}: sweep service {peak_ticks} ticks in one "
                            f"period exceeds budget {domain.background_ticks_per_period}")
        domain_reports.append({
            "id": domain.name,
            **_measure(events, end - start, tick_hz),
            "quarantine_capacity_bytes": domain.quarantine_capacity_bytes,
            "quarantine_margin_bytes": domain.quarantine_capacity_bytes - peak_bytes,
            "period_ticks": domain.period_ticks,
            "observed_periods": (end - start) // domain.period_ticks,
            "background_ticks_per_period": domain.background_ticks_per_period,
            "sweep_ticks_total": sum(row.end_tick - row.start_tick for row in service),
            "sweep_ticks_peak_per_period": peak_ticks,
            "background_margin_ticks": domain.background_ticks_per_period - peak_ticks,
        })
    return {
        "scope": SCOPE,
        "milestone_acceptance": "open",
        "identity": asdict(expected),
        "window": window,
        "within_declared_limits": not findings,
        "findings": findings,
        "totals": _measure(teardowns, end - start, tick_hz),
        "domains": domain_reports,
    }
