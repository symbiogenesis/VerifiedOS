# SPDX-License-Identifier: Apache-2.0
"""The corpus parse, held to the promises every rule stands on.

Every check reads documents through `vos.corpus`, so a fence-pairing or offset
defect here changes what all eighteen groups see with no local symptom. These
cases pin the parse at its own altitude: `_read` for the per-document machinery,
`load` over sandbox trees for the index-membership rules, and the refusals that
must stay refusals. The parse-level cases go through `_read` deliberately: it is
the unit under test, and reaching it through `load` would need a git tree per
string.
"""

import subprocess
import tempfile
from pathlib import Path

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos.corpus import HEADING_RE, Document, slug


def _doc(text: str, name: str = "docs/x.md") -> Document:
    """One document parsed from a string, byte-for-byte as written."""
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "x.md"
        path.write_text(text, encoding="utf-8", newline="")
        return corpus_mod._read(path, name)


def _git(root: Path, *args: str, payload: bytes | None = None) -> str:
    """git in a sandbox, with stdin passed as bytes: a text-mode pipe would
    CRLF-translate the payload on this host, and `update-index --index-info`
    then reads every path with a trailing CR and ignores it."""
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          input=payload, check=False, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} exited {done.returncode}: "
                           f"{done.stderr.decode('utf-8', errors='replace').strip()}")
    return done.stdout.decode("utf-8", errors="replace")


def _fence_toggles() -> None:
    doc = _doc("a\n```\nb\n```\nc\n")
    ensure(doc.fenced == [False, True, True, True, False],
           f"a fence spans its markers and the lines between: {doc.fenced!r}")


def _fence_indented_marker_toggles() -> None:
    # FENCE_RE admits leading whitespace, so an indented ``` toggles exactly as a
    # flush one does; an indented code block's markers therefore pair, and a
    # change here would silently re-fence every document that carries one
    doc = _doc("a\n    ```\nb\n```\nc\n")
    ensure(doc.fenced == [False, True, True, True, False],
           f"an indented ``` marker must toggle: {doc.fenced!r}")


def _fence_unclosed_runs_to_eof() -> None:
    doc = _doc("a\n```\nb\nc\n")
    ensure(doc.fenced == [False, True, True, True],
           f"an unclosed fence displays to the end of the file: {doc.fenced!r}")


def _slug_shape() -> None:
    got = slug("Build & Run `check.py` <em>Now</em>")
    ensure(got == "build-run-checkpy-now",
           f"tags and backticks vanish, punctuation vanishes, spaces hyphenate: {got!r}")
    ensure(slug("A  B") == "a-b", "a whitespace run hyphenates once")


def _targets_and_numbered() -> None:
    text = '# Title\n\n## 5. Things\n\nBody. <a id="r-05-001"></a>\n'
    with sandbox_tree({"docs/x.md": text}) as root:
        corpus = corpus_mod.load(root)
        doc = corpus.by_name["docs/x.md"]
        ensure("5-things" in doc.targets, "a heading's slug is a link target")
        ensure("r-05-001" in doc.targets, "a declared anchor is a link target")
        ensure("5" in corpus.numbered, "a numbered heading feeds the shared numbering")


def _line_of_bisect() -> None:
    doc = _doc("ab\r\ncd\ne")
    ensure(doc.lines == ["ab", "cd", "e"], f"CR is stripped from lines: {doc.lines!r}")
    ensure(doc.starts == [0, 4, 7], f"offsets count the CRLF terminator: {doc.starts!r}")
    # every offset resolves to the line containing it, terminators included
    ensure([doc.line_of(o) for o in (0, 1, 3, 4, 6, 7)] == [0, 0, 0, 1, 1, 2],
           "line_of must bisect offsets to their containing line")
    ensure(doc.at(7) == 3, "at() is the 1-based line a person visits")


def _unfenced_walk() -> None:
    doc = _doc("# One\n```\n# Two\n```\n# Three\n")
    got = [(i, m.group(1)) for i, m in doc.unfenced("# ", HEADING_RE)]
    ensure(got == [(0, "One"), (4, "Three")],
           f"unfenced yields each undisplayed match with its line index: {got!r}")


def _merge_conflict_one_document() -> None:
    with sandbox_tree({"docs/a.md": '# A\n\n<a id="one"></a>\n'}) as root:
        listing = _git(root, "ls-files", "--stage")
        mode, sha, _rest = listing.split(maxsplit=2)
        # a real unmerged state: the stage-0 entry out, one entry per stage 1..3
        info = ("0 " + "0" * 40 + "\tdocs/a.md\n"
                + "".join(f"{mode} {sha} {n}\tdocs/a.md\n" for n in (1, 2, 3)))
        _git(root, "update-index", "--index-info", payload=info.encode("utf-8"))
        staged = _git(root, "ls-files", "--stage")
        ensure(staged.count("docs/a.md") == 3,
               f"precondition: the index must list the path once per stage:\n{staged}")

        corpus = corpus_mod.load(root)
        ensure([d.name for d in corpus.docs] == ["docs/a.md"],
               f"an unmerged path is one document, not one per stage: "
               f"{[d.name for d in corpus.docs]!r}")
        ensure(corpus.declared_twice == [],
               f"one document read once declares its anchor once: "
               f"{corpus.declared_twice!r}")


def _deleted_but_indexed_dropped() -> None:
    with sandbox_tree({"docs/a.md": "# A\n", "docs/b.md": "# B\n"}) as root:
        (root / "docs" / "b.md").unlink()
        corpus = corpus_mod.load(root)
        ensure("docs/b.md" not in corpus.by_name,
               "a deleted-but-indexed document is dropped, not read")
        ensure("docs/b.md" not in corpus.tracked,
               "the tracked list drops it too, so no rule opens a ghost")
        ensure("docs/a.md" in corpus.by_name, "its neighbours stay in the corpus")


def _non_utf8_names_the_document() -> None:
    with sandbox_tree({"docs/a.md": "# A\n"}) as root:
        (root / "docs" / "bad.md").write_bytes(b"# \xff\n")
        _git(root, "add", "-A")
        try:
            corpus_mod.load(root)
        except RuntimeError as err:
            ensure("docs/bad.md is not valid UTF-8" in str(err),
                   f"the error must name the document, not just offsets: {err}")
            return
        raise AssertionError("a non-UTF-8 tracked document must stop the load")


def _find_root_refuses_outside_a_checkout() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        try:
            corpus_mod.find_root(Path(td))
        except SystemExit as err:
            ensure("no repository root above" in str(err),
                   f"the refusal names what was expected: {err}")
            return
        raise AssertionError("find_root outside a checkout must refuse, not answer")


def cases() -> list[Case]:
    return [
        Case("fence-toggles", _fence_toggles),
        Case("fence-indented-marker-toggles", _fence_indented_marker_toggles),
        Case("fence-unclosed-runs-to-eof", _fence_unclosed_runs_to_eof),
        Case("slug-shape", _slug_shape),
        Case("targets-and-numbered", _targets_and_numbered),
        Case("line-of-bisect", _line_of_bisect),
        Case("unfenced-walk", _unfenced_walk),
        Case("merge-conflict-one-document", _merge_conflict_one_document),
        Case("deleted-but-indexed-dropped", _deleted_but_indexed_dropped),
        Case("non-utf8-names-the-document", _non_utf8_names_the_document),
        Case("find-root-refusal", _find_root_refuses_outside_a_checkout),
    ]
