# SPDX-License-Identifier: Apache-2.0
"""Host concurrency preserves manual handoffs and supersedes redundant automatic work."""

import ast
import re

from tests.harness import TOOLS, Case, ensure

INDEPENDENT_CASES = True
WORKFLOW = TOOLS.parent / ".github/workflows/host-gates.yml"


def _value(node: ast.expr, fields: dict[str, str | int]) -> str | int | bool:
    """Interpret the expression's limited vocabulary without executing its code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)):
        return node.value
    if isinstance(node, ast.Attribute):
        return fields[ast.unparse(node)]
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq):
        left, right = _value(node.left, fields), _value(node.comparators[0], fields)
        return left.casefold() == right.casefold() if isinstance(left, str) and isinstance(right, str) else left == right
    if isinstance(node, ast.BoolOp):
        result = _value(node.values[0], fields)
        for operand in node.values[1:]:
            if (isinstance(node.op, ast.And) and not result) or (isinstance(node.op, ast.Or) and result):
                return result
            result = _value(operand, fields)
        return result
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "format" and node.args and not node.keywords):
        template = _value(node.args[0], fields)
        if isinstance(template, str):
            return template.format(*(_value(arg, fields) for arg in node.args[1:]))
    raise ValueError(f"unsupported concurrency expression: {ast.dump(node)}")


def _group(event: str, *, revision: str = "", sha: str = "a" * 40,
           run_id: int = 1, pull_request: int = 1) -> str:
    contents = WORKFLOW.read_text(encoding="utf-8")
    group = re.search(r"(?m)^concurrency:\n(?:  #.*\n)*  group: (.+)$", contents)
    ensure(group is not None, "Host CI declares one workflow concurrency group")
    template = group[1] if group is not None else ""
    fields: dict[str, str | int] = {
        "github.workflow": "host-gates", "github.event_name": event,
        "github.run_id": run_id, "github.sha": sha,
        "github.event.pull_request.number": pull_request, "inputs.revision": revision,
    }

    def render(match: re.Match[str]) -> str:
        # This authored expression uses strings, equality, format, && and ||.
        # Parse the workflow itself, preserving the operand-returning semantics
        # of && and || rather than recreating its grouping policy in Python.
        expression = match[1].strip().replace("&&", " and ").replace("||", " or ")
        return str(_value(ast.parse(expression, mode="eval").body, fields))

    return re.sub(r"\$\{\{ (.*?) \}\}", render, template)


def _manual() -> None:
    for revision in ("", "b" * 40):
        first = _group("workflow_dispatch", revision=revision, run_id=100)
        second = _group("workflow_dispatch", revision=revision, run_id=101)
        ensure(first != second, "two explicit dispatches of the same revision cannot cancel each other")
        ensure(first == _group("workflow_dispatch", revision=revision, run_id=100),
               "a manual run retains its own group")
        ensure(first != _group("push", sha=revision or "a" * 40, run_id=100),
               "an automatic push cannot cancel a manual handoff for the same revision")


def _pushes() -> None:
    first = _group("push", run_id=100)
    ensure(first == _group("push", run_id=101), "duplicate pushes of one SHA share a group")
    ensure(first != _group("push", sha="b" * 40, run_id=101),
           "distinct main revisions cannot cancel each other's validation")


def _pull_requests() -> None:
    first = _group("pull_request", pull_request=42, run_id=100)
    ensure(first == _group("pull_request", pull_request=42, sha="b" * 40, run_id=101),
           "a new commit supersedes the previous run of the same pull request")
    ensure(first != _group("pull_request", pull_request=43, run_id=101),
           "unrelated pull requests cannot cancel each other's validation")
    ensure(first != _group("push", run_id=100), "pull requests and main pushes keep separate groups")


def _cancellation() -> None:
    contents = WORKFLOW.read_text(encoding="utf-8")
    block = contents.split("\nconcurrency:\n", 1)[1].split("\nenv:\n", 1)[0]
    ensure(re.search(r"(?m)^  cancel-in-progress: true$", block) is not None,
           "shared automatic groups still cancel redundant work")


def cases() -> list[Case]:
    return [Case("manual handoffs retain separate concurrency groups", _manual),
            Case("push deduplication preserves distinct revisions", _pushes),
            Case("pull requests supersede only their own runs", _pull_requests),
            Case("automatic supersession remains enabled", _cancellation)]
