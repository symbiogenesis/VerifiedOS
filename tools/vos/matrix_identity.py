# SPDX-License-Identifier: Apache-2.0
"""Independent finite rational bilinear identities; never execute an input program."""

import ast
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

PIN = "tools/matrix-identity/plinopt.json"
REPORT = "docs/background/rank48-replay.json"
SOURCES = ("tools/vos/matrix_identity.py", "tools/vos/cli/matrix_identity.py")
LIMIT = 1024 * 1024


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = member
    return value


def matrix(text: str) -> list[list[Fraction]]:
    """Read SMS rational entries, refusing duplicates and trailing material."""
    lines = text.splitlines()
    if not lines or len(lines[0].split()) != 3:
        raise ValueError("missing SMS dimensions")
    r, c, domain = lines[0].split()
    if not r.isdecimal() or not c.isdecimal() or domain != "R":
        raise ValueError("expected rational SMS dimensions")
    rows, columns = int(r), int(c)
    if not 1 <= rows <= 64 or not 1 <= columns <= 64:
        raise ValueError("matrix dimensions exceed finite replay bound")
    result = [[Fraction(0) for _ in range(columns)] for _ in range(rows)]
    seen: set[tuple[int, int]] = set()
    ended = False
    for line in lines[1:]:
        if not line.strip():
            continue
        if ended:
            raise ValueError("material after SMS terminator")
        fields = line.split()
        if fields == ["0", "0", "0"]:
            ended = True
            continue
        if len(fields) != 3 or not all(re.fullmatch(r"[0-9]+", v) for v in fields[:2]):
            raise ValueError("invalid sparse matrix entry")
        i, j = int(fields[0]) - 1, int(fields[1]) - 1
        if not 0 <= i < rows or not 0 <= j < columns or (i, j) in seen:
            raise ValueError("duplicate or out-of-range matrix entry")
        if not re.fullmatch(r"-?[0-9]{1,12}(?:/[1-9][0-9]{0,11})?", fields[2]):
            raise ValueError("invalid bounded rational coefficient")
        result[i][j] = Fraction(fields[2])
        seen.add((i, j))
    if not ended:
        raise ValueError("missing SMS terminator")
    return result


def program(text: str, inputs: int, outputs: int) -> tuple[list[list[Fraction]], dict[str, int]]:
    """Symbolically interpret a bounded linear AST, with every arithmetic node charged."""
    if not 1 <= inputs <= 64 or not 1 <= outputs <= 64 or len(text) > LIMIT:
        raise ValueError("program exceeds finite replay bound")
    zero = [Fraction(0)] * inputs
    values = {f"i{i}": [Fraction(int(i == j)) for j in range(inputs)] for i in range(inputs)}
    counts = {"additions_subtractions": 0, "nonunit_scalings": 0, "unary_negations": 0}

    def form(node: ast.AST) -> list[Fraction]:
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            counts["unary_negations"] += 1
            return [-x for x in form(node.operand)]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            left, right = form(node.left), form(node.right)
            counts["additions_subtractions"] += 1
            sign = -1 if isinstance(node.op, ast.Sub) else 1
            return [a + sign * b for a, b in zip(left, right, strict=True)]
        if (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div))
                and isinstance(node.right, ast.Constant) and type(node.right.value) is int):
            scale = node.right.value
            if not 1 <= scale <= 1024:
                raise ValueError("invalid bounded scalar")
            factor = Fraction(1, scale) if isinstance(node.op, ast.Div) else Fraction(scale)
            counts["nonunit_scalings"] += int(factor != 1)
            return [x * factor for x in form(node.left)]
        raise ValueError("undefined variable, nonlinear operation or unsupported program syntax")

    assignments = [line.strip() for line in text.split(";")]
    if assignments[-1] or len(assignments) > 1025:
        raise ValueError("unterminated or oversized program")
    for line in assignments[:-1]:
        match = re.fullmatch(r"([a-z][0-9]+)\s*:=\s*(.{1,512})", line)
        if match is None:
            raise ValueError("invalid program assignment")
        name, expression = match.groups()
        if name in values or name.startswith("i"):
            raise ValueError("overwritten variable")
        try:
            expression_tree = ast.parse(expression, mode="eval")
        except (SyntaxError, RecursionError) as error:
            raise ValueError("invalid program expression") from error
        values[name] = form(expression_tree.body)
    expected = {f"o{i}" for i in range(outputs)}
    if {key for key in values if key.startswith("o")} != expected:
        raise ValueError("missing or extra program outputs")
    return [values.get(f"o{i}", zero) for i in range(outputs)], counts


def tensor(left: list[list[Fraction]], right: list[list[Fraction]],
           output: list[list[Fraction]], order: int) -> int:
    """Check every ordered A-entry/B-entry coefficient of every C entry."""
    size = order * order
    rank = len(left)
    if (type(order) is not int or not 1 <= order <= 8 or not 1 <= rank <= 64
            or len(right) != rank or len(output) != size or any(len(row) != size for row in left + right)
            or any(len(row) != rank for row in output)):
        raise ValueError("bilinear matrix dimensions disagree")
    checked = 0
    for i in range(size):
        for j in range(size):
            products = [left[k][i] * right[k][j] for k in range(rank)]
            for k in range(size):
                coefficient = sum((v * output[k][r] for r, v in enumerate(products) if v), Fraction(0))
                expected = int(i // order == k // order and j % order == k % order
                               and i % order == j // order)
                if coefficient != expected:
                    raise ValueError(f"bilinear coefficient mismatch at C[{k}], A[{i}], B[{j}]")
                checked += 1
    return checked


def verify(inputs: dict[str, bytes], *, order: int = 4) -> dict[str, Any]:
    matrices = []
    operations: dict[str, dict[str, int]] = {}
    for part in ("L", "R", "P"):
        sms = inputs[f"{part}.sms"]
        slp = inputs[f"{part}.slp"]
        if len(sms) > LIMIT or len(slp) > LIMIT:
            raise ValueError("input exceeds finite replay bound")
        parsed = matrix(sms.decode("ascii"))
        actual, counts = program(slp.decode("ascii"), len(parsed[0]), len(parsed))
        if actual != parsed:
            raise ValueError(f"{part} program disagrees with coefficient matrix")
        matrices.append(parsed)
        operations[part] = counts
    checked = tensor(matrices[0], matrices[1], matrices[2], order)
    return {"bilinear_products": len(matrices[0]), "coefficients_checked": checked,
            "operations": operations,
            "linear_operations": sum(sum(counts.values()) for counts in operations.values())}


def pin(root: Path) -> dict[str, Any]:
    value = json.loads((root / PIN).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if (not isinstance(value, dict) or set(value) != {"revision", "files", "license_url"}
            or not re.fullmatch(r"[0-9a-f]{40}", str(value["revision"]))
            or not isinstance(value["files"], dict)
            or set(value["files"]) != {f"{p}.{e}" for p in ("L", "R", "P") for e in ("sms", "slp")}
            or any(not re.fullmatch(r"[0-9a-f]{64}", str(v)) for v in value["files"].values())
            or value["license_url"] != f"https://github.com/jgdumas/plinopt/blob/{value['revision']}/Licence_CeCILL-B_V1-en.txt"):
        raise ValueError("invalid finite identity input pin")
    return value


def replay(root: Path, directory: Path) -> dict[str, Any]:
    record = pin(root)
    inputs = {}
    for key in record["files"]:
        with (directory / f"4x4x4_48_204_{key}").open("rb") as stream:
            inputs[key] = stream.read(LIMIT + 1)
        if len(inputs[key]) > LIMIT:
            raise ValueError("input exceeds finite replay bound")
    if any(sha(data) != record["files"][name] for name, data in inputs.items()):
        raise ValueError("input differs from pinned artifact")
    result = verify(inputs)
    corrupt_matrix = dict(inputs)
    corrupt_matrix["L.sms"] = inputs["L.sms"].replace(b"1 1 1\n", b"1 1 2\n", 1)
    corrupt_program = dict(inputs)
    corrupt_program["L.slp"] = inputs["L.slp"].replace(b"i0+i3", b"i0-i3", 1)
    controls = []
    for corrupted in (corrupt_matrix, corrupt_program):
        try:
            verify(corrupted)
        except ValueError:
            controls.append(True)
        else:
            raise ValueError("negative identity control survived")
    return {"schema": "vos-rank48-replay-v1", "status": "passed", "upstream_revision": record["revision"],
            "inputs_sha256": record["files"], "pin_sha256": sha((root / PIN).read_bytes()),
            "checker_sha256": {name: sha((root / name).read_bytes()) for name in SOURCES},
            "negative_controls_rejected": controls, "result": result,
            "scope": "Exact rational ordinary-basis identity and linear operation count; no target or Rocq acceptance."}


def check_report(root: Path) -> None:
    record = pin(root)
    report = json.loads((root / REPORT).read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    if (not isinstance(report, dict)
            or set(report) != {"schema", "status", "upstream_revision", "inputs_sha256", "pin_sha256",
                               "checker_sha256", "negative_controls_rejected", "result", "scope"}
            or report.get("schema") != "vos-rank48-replay-v1" or report.get("status") != "passed"
            or report.get("upstream_revision") != record["revision"]
            or report.get("inputs_sha256") != record["files"]
            or report.get("pin_sha256") != sha((root / PIN).read_bytes())
            or report.get("checker_sha256") != {name: sha((root / name).read_bytes()) for name in SOURCES}
            or report.get("negative_controls_rejected") != [True, True]
            or report.get("result") != {
                "bilinear_products": 48, "coefficients_checked": 4096, "linear_operations": 204,
                "operations": {part: {"additions_subtractions": additions,
                                      "nonunit_scalings": halvings, "unary_negations": 0}
                               for part, additions, halvings in (("L", 55, 2), ("R", 55, 2), ("P", 90, 0))}}
            or report.get("scope") != "Exact rational ordinary-basis identity and linear operation count; no target or Rocq acceptance."):
        raise ValueError("rank48 receipt is missing, malformed or stale; independently replay its pinned inputs")
