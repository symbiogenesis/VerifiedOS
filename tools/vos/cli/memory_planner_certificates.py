# SPDX-License-Identifier: Apache-2.0
"""Encode and certify optional off-device memory plans with pinned LRAT tools."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from vos import memory_planner as planner
from vos import memory_planner_certificates as certificates
from vos.cli.memory_planner import unique_object
from vos.corpus import find_root


def _finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise certificates.CertificateError("nonfinite JSON number")
    return result


def _nonfinite_constant(value: str) -> object:
    raise certificates.CertificateError(f"nonfinite JSON number: {value}")


def read_json(path: Path, inputs: dict[str, str]) -> object:
    """Reject ambiguous JSON and identify the exact bytes that were parsed."""
    data = path.read_bytes()
    inputs[str(path)] = hashlib.sha256(data).hexdigest()
    return json.loads(data, object_pairs_hook=unique_object, parse_float=_finite_float,
                      parse_constant=_nonfinite_constant)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "demo", "encode", "certify", "verify", "proof"))
    parser.add_argument("--instance", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--lrat", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--bound", type=int)
    parser.add_argument("--pool-limits", type=Path)
    parser.add_argument("--conflict-budget", type=int, default=10000)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-domain-values", type=int, default=4096)
    parser.add_argument("--dimacs", action="store_true", help="encode: write DIMACS instead of JSON")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    inputs: dict[str, str] = {}
    try:
        if args.action == "setup":
            result = certificates.setup(find_root())
        elif args.action == "demo":
            result = certificates.demo(find_root())
        elif args.action == "proof":
            result = certificates.proof(find_root())
        else:
            if args.instance is None:
                raise certificates.CertificateError("--instance is required")
            instance = planner.parse_instance(read_json(args.instance, inputs))
            candidate = read_json(args.candidate, inputs) if args.candidate else None
            pool_limits = read_json(args.pool_limits, inputs) if args.pool_limits else None
            if args.candidate and not isinstance(candidate, list):
                raise certificates.CertificateError("candidate placement must be a JSON array")
            if pool_limits is not None and not isinstance(pool_limits, dict):
                raise certificates.CertificateError("pool limits must be a JSON object")
            if args.pool_limits and pool_limits is None:
                raise certificates.CertificateError("pool limits must be a JSON object")
            limits = certificates.Limits(max_domain_values=args.max_domain_values)
            if args.action == "encode":
                bound = args.bound
                if candidate is not None:
                    if bound is not None:
                        raise certificates.CertificateError("encode accepts candidate or bound, not both")
                    bound = sum(planner.pool_heights(instance, candidate).values()) - 1
                encoded = certificates.encode(instance, objective_bound=bound,
                                              pool_limits=pool_limits, limits=limits)
                if args.dimacs:
                    print(encoded.dimacs(), end="")
                    return 0
                result = encoded.identity()
            elif args.action == "verify":
                if args.evidence is None:
                    raise certificates.CertificateError("verify requires --evidence")
                result = certificates.replay(instance, read_json(args.evidence, inputs), find_root(),
                                             input_sha256=inputs)
            else:
                if args.bound is not None:
                    raise certificates.CertificateError("certify derives its strict bound from --candidate")
                result = certificates.certify(instance, candidate, find_root(), certificate_path=args.lrat,
                                              pool_limits=pool_limits, limits=limits,
                                              conflict_budget=args.conflict_budget, timeout=args.timeout,
                                              input_sha256=inputs)
    except (ValueError, OSError, TypeError) as error:
        print(json.dumps({"status": "unknown", "findings": [str(error)],
                          "input_sha256": inputs, "scope": certificates.evidence_scope()}, indent=2))
        return 1
    if inputs:
        result["input_sha256"] = inputs
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.action in {"certify", "verify"}:
        return 0 if result["evidence"]["certificate_status"] == "checked LRAT refutation" else 1
    return 0
