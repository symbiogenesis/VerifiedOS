# SPDX-License-Identifier: Apache-2.0
"""Shared host-test fixture helpers for `sail-tag-outcomes` unit controls."""


def kernel_summary(axioms: list[str], indices: list[str] | None = None) -> str:
    """Render a synthetic `rocqchk -silent -o` context summary block."""
    ax_block = (
        "* Axioms: <none>"
        if not axioms
        else "* Axioms:\n" + "\n".join(f"    {ax}" for ax in axioms)
    )
    idx_block = (
        "* Inductives relying on indices not mattering: <none>"
        if indices is None or len(indices) == 0
        else "* Inductives relying on indices not mattering:\n"
        + "\n".join(f"    {ind}" for ind in indices)
    )
    return "\n".join([
        "",
        "CONTEXT SUMMARY",
        "===============",
        "",
        "* Theory: Set is predicative",
        "* Theory: Rewrite rules are not allowed",
        ax_block,
        "* Constants/Inductives relying on type-in-type: <none>",
        "* Constants/Inductives relying on unsafe (co)fixpoints: <none>",
        "* Inductives whose positivity is assumed: <none>",
        idx_block,
        "",
    ])
