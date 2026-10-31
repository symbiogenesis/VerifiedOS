# SPDX-License-Identifier: Apache-2.0
"""Python 3.14 parser suggestions retain usage refusal and valid dispatch."""

import argparse
from collections.abc import Callable
from contextlib import redirect_stderr
from io import StringIO

from tests.harness import Case, ensure
from vos.cli import dispatch, model


def _usage_refusal(run: Callable[[], int], suggestion: str) -> None:
    diagnostic = StringIO()
    with redirect_stderr(diagnostic):
        try:
            run()
        except SystemExit as error:
            ensure(error.code == 2, "a suggestion must preserve argparse's usage exit code")
        else:
            raise AssertionError("misspelled input reached a command handler")
    message = diagnostic.getvalue()
    ensure("invalid choice" in message and f"maybe you meant '{suggestion}'" in message,
           f"usage refusal must retain its primary diagnostic and suggest a choice: {message}")


def _unexpected_handler(args: argparse.Namespace) -> int:
    raise AssertionError(f"invalid input reached its handler: {args}")


def _command_typo() -> None:
    _usage_refusal(lambda: dispatch(
        "Inspect artifacts.", {"inspect": (_unexpected_handler, "inspect artifacts")},
        ["inspec"]), "inspect")


def _nested_command_typo() -> None:
    _usage_refusal(lambda: model.main(["bundel"]), "bundle")


def _format_flag(name: str, parser: argparse.ArgumentParser) -> None:
    del name
    parser.add_argument("--format", choices=("summary", "detailed"), default="summary")


def _child_choice_typo() -> None:
    _usage_refusal(lambda: dispatch(
        "Inspect artifacts.", {"inspect": (_unexpected_handler, "inspect artifacts")},
        ["inspect", "--format", "sumary"], flags=_format_flag), "summary")


def _valid_input_keeps_dispatch() -> None:
    observed: list[str] = []

    def handler(args: argparse.Namespace) -> int:
        observed.append(args.format)
        return 7

    status = dispatch("Inspect artifacts.", {"inspect": (handler, "inspect artifacts")},
                      ["inspect", "--format", "detailed"], flags=_format_flag)
    ensure(status == 7 and observed == ["detailed"],
           "valid choices must preserve their namespace and handler's return value")


def cases() -> list[Case]:
    return [
        Case("command-typo-keeps-usage-refusal", _command_typo),
        Case("nested-command-typo-suggests-command", _nested_command_typo),
        Case("child-choice-typo-suggests-value", _child_choice_typo),
        Case("valid-input-keeps-dispatch", _valid_input_keeps_dispatch),
    ]
