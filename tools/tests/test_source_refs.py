# SPDX-License-Identifier: Apache-2.0
"""Source links retain their comment boundary, index membership and declarations."""

import hashlib
import json
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from tests.harness import Case, ensure
from vos import sailbundle, source_refs
from vos.corpus import Corpus, from_text


@contextmanager
def _tree(files: dict[str, str], *, untracked: dict[str, str] | None = None) -> Generator[tuple[Path, Corpus]]:
    with tempfile.TemporaryDirectory(prefix="vos-source-refs-") as directory:
        root = Path(directory)
        for rel, text in {**files, **(untracked or {})}.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        docs = [from_text(text, rel) for rel, text in files.items() if rel.endswith(".md")]
        yield root, Corpus(root, docs, {}, sorted(files))


def _python_comments_and_docstrings() -> None:
    text = ('"""Module [target](target.py#Worker.run)."""\n'
            'fixture = "[string decoy](missing.py)"\n'
            '# [comment](target.py#Worker)\n'
            'class Local:\n'
            '    """Class [target](target.py#LIMIT)."""\n'
            '    async def method(self):\n'
            '        """A method.\n\n'
            '        [target](target.py#Worker.value)\n'
            '        ```md\n'
            '        [example](missing.py)\n'
            '        ```\n'
            '        """\n'
            '        return "[another string](missing.py)"\n'
            '# `[inline code](missing.py)`\n')
    refs = list(source_refs.references("main.py", text))
    ensure({ref.target for ref in refs} == {
        "target.py#Worker.run", "target.py#Worker", "target.py#LIMIT", "target.py#Worker.value"},
        f"only comments/docstrings outside Markdown code are references: {refs}")
    ensure({ref.line for ref in refs} == {1, 3, 5, 9}, f"source lines must survive projection: {refs}")
    unusual = ('def caf\u00e9(): """[unicode](target.py#Worker)"""\n'
               'def joined():\n'
               '    ("first "\n'
               '     "[second literal](target.py#LIMIT)")\n')
    refs = list(source_refs.references("main.py", unusual))
    ensure({ref.target for ref in refs} == {"target.py#Worker", "target.py#LIMIT"},
           f"Unicode AST columns and all concatenated docstring tokens must be read: {refs}")


def _comment_dialects_and_reference_links() -> None:
    cases = {
        "proof.v": 'Definition text := "[decoy](missing.py)".\n'
                   '(* Outer "*)" (* nested [target](target.py#Worker) *) remains. *)\n',
        "model.sail": "val identity : forall 'a, 'a -> 'a\n"
                      '// [target][worker]\n//\n// [worker]: target.py#Worker\n'
                      'let text = "[decoy](missing.py)"\n',
        "core.sv": "localparam int MASK = 64'hff;\n"
                   '// [target][worker]\n//\n// [worker]: target.py#Worker\n'
                   'string text = "[decoy](missing.py)";\n',
        "main.c": "char c = '/'; char *text = \"[decoy](missing.py)\";\n"
                  '/* A quote " inside a comment must not swallow its ending.\n'
                  ' * [target](target.py#Worker)\n */\n',
        "main.cpp": 'auto text = R"custom(quote " // [decoy](missing.py)\n'
                    '/* still data */)custom";\n'
                    '// [target](target.py#Worker)\n',
    }
    for rel, text in cases.items():
        refs = list(source_refs.references(rel, text))
        ensure(len(refs) == 1 and refs[0].target == "target.py#Worker",
               f"{rel} must read comment links and ignore string decoys: {refs}")
    continued = '// continued comment \\\n [target](target.py#Worker)\n'
    refs = list(source_refs.references("main.c", continued))
    ensure(len(refs) == 1 and refs[0].target == "target.py#Worker",
           f"C backslash-newline comments retain their continued prose: {refs}")
    for rel, text in (("main.c", "/* [decoy] */ int x; /* (missing.py) */"),
                      ("proof.v", "(* [decoy] *) Definition x := 0. (* (missing.py) *)")):
        ensure(not list(source_refs.references(rel, text)),
               f"{rel}: distinct comments cannot fabricate one Markdown link")
    for rel, text in (("proof.v", "(* unfinished"), ("model.sail", "/* unfinished")):
        try:
            list(source_refs.references(rel, text))
        except ValueError:
            pass
        else:
            raise AssertionError(f"{rel}: unfinished comment must refuse")


_PYTHON = ("raise RuntimeError('reference checking must never execute this file')\n"
           "LIMIT = 5\nclass Worker:\n    value: int\n    async def run(self): pass\n"
           "if True:\n    def conditional(): pass\n")


def _declaration_and_heading_renames() -> None:
    names = source_refs.python_names("(left, [right, *rest]) = values\n"
                                     "registry[missing] = 1\ninstance.attribute = 2\n")
    ensure(names == {"left", "right", "rest"},
           f"only assignment bindings introduce names, not store-target operands: {names}")
    files = {
        "src/main.py": '# [worker](../target.py#Worker.run)\n'
                       '# [field](../target.py#Worker.value)\n'
                       '# [constant](../target.py#LIMIT)\n'
                       '# [conditional](../target.py#conditional)\n'
                       '# [proof](../proof.v#result)\n'
                       '# [heading](../guide.md#heading) [anchor](../guide.md#fixed)\n',
        "target.py": _PYTHON,
        "proof.v": '(* Lemma ghost : True. *)\nLemma result : True. Proof. exact I. Qed.\n',
        "guide.md": '# Heading\n\n<a id="fixed"></a>\n',
    }
    with _tree(files) as (root, corpus):
        ensure(not source_refs.findings(root, corpus), "current declarations/headings must resolve")
        (root / "target.py").write_text(_PYTHON.replace("def run", "def renamed"), encoding="utf-8")
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 1 and "src/main.py:1" in faults[0] and "#Worker.run" in faults[0],
               f"a member rename must point to its stale comment: {faults}")
        (root / "proof.v").write_text("Lemma renamed : True. Proof. exact I. Qed.\n", encoding="utf-8")
        ensure(len(source_refs.findings(root, corpus)) == 2, "a theorem rename must also fail")
        (root / "target.py").unlink()
        faults = source_refs.findings(root, corpus)
        ensure(any("missing from the working tree" in fault for fault in faults),
               f"an indexed deletion must fail file references: {faults}")
    changed = {**files, "guide.md": "# Renamed\n"}
    with _tree(changed) as (root, corpus):
        ensure(len(source_refs.findings(root, corpus)) == 2, "heading and explicit anchor removal must fail")


def _membership_and_path_safety() -> None:
    targets = ["../untracked.txt", "../TARGET.py", "../../outside.txt", "/absolute.txt",
               "file:///outside.txt", "C:/outside.txt", "..%5Ctarget.py", "../target.py?query=yes",
               "../target.txt#unsupported", "../target.py#absent", "../proof.v#ghost"]
    files = {"src/main.py": "\n".join(f"# [target]({target})" for target in targets)
                             + "\n# [network](https://never-contact.invalid/a)\n",
             "target.py": _PYTHON, "target.txt": "plain text\n",
             "proof.v": "(* Definition ghost := 0. *)\nDefinition live := 0.\n"}
    with _tree(files, untracked={"untracked.txt": "exists but is not indexed"}) as (root, corpus):
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == len(targets), f"every unsafe or unresolved local target must fail: {faults}")
        ensure(not any("https://" in fault for fault in faults), "network links must not be fetched")
        ensure(all("src/main.py:" in fault for fault in faults), "each fault identifies its referring source")


def _historical_scope_and_unreadable_sources() -> None:
    files = {"live.py": '# [missing](absent.py)\n',
             "docs/implementation/retained-evidence/old.py": '# [historical](old-absent.py)\n'}
    with _tree(files) as (root, corpus):
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 1 and "live.py:1" in faults[0],
               f"historical snapshots are excluded while live references remain checked: {faults}")
        (root / "live.py").unlink()
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 1 and "live.py: cannot read source references" in faults[0],
               f"an indexed referring source cannot disappear silently: {faults}")
        (root / "live.py").write_bytes(b"\xff")
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 1 and "cannot read source references" in faults[0],
               f"undecodable indexed source must refuse: {faults}")


def _indexed_directories() -> None:
    files = {"src/main.py": '# [directory](../data/)\n# [root](../)\n',
             "data/retained.txt": "an indexed descendant\n"}
    with _tree(files) as (root, corpus):
        ensure(not source_refs.findings(root, corpus), "indexed directory and root references must resolve")
        (root / "empty").mkdir()
        (root / "src/main.py").write_text(
            '# [empty](../empty/)\n# [case](../DATA/)\n# [fragment](../data/#section)\n', encoding="utf-8")
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 3 and any("directory references cannot select a fragment" in fault for fault in faults),
               f"empty unindexed directories, wrong case and directory fragments must fail: {faults}")


def _sail_identity() -> None:
    declaration = "function target() = 0"
    text = declaration + "\n"
    bundle = {"version": 1, "embedding": "plain", "anchors": {}, "spans": {},
              "hashes": {"a.sail": {"md5": hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()}},
              "functions": {"target": {"function": {"source": {
                  "contents": declaration, "file": "a.sail", "loc": [1, 0, 0, 1, 0, len(declaration)]}}}},
              "mappings": {}, "vals": {}, "types": {}, "registers": {}, "lets": {}}
    files = {"main.py": '# [model](model/model/a.sail#target)\n',
             "model/model/a.sail": text, sailbundle.PROJECT_FILE: "fixture project",
             sailbundle.BUNDLE: json.dumps(bundle), sailbundle.SOURCE_IDENTITY: "pending"}
    with _tree(files) as (root, corpus):
        (root / sailbundle.SOURCE_IDENTITY).write_bytes(sailbundle.source_identity(
            root, ["a.sail"], (root / sailbundle.BUNDLE).read_bytes()))
        ensure(not source_refs.findings(root, corpus), "compiler-recorded current Sail names resolve")
        (root / "main.py").write_text('# [model](model/model/a.sail#renamed)\n', encoding="utf-8")
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 1 and "#renamed" in faults[0], f"unknown Sail declaration must fail: {faults}")
        (root / "model/model/a.sail").write_text(text + "// changed bytes\n", encoding="utf-8")
        faults = source_refs.findings(root, corpus)
        ensure(len(faults) == 1 and "recorded owner digest differs" in faults[0],
               f"stale compiler identity must not validate declarations: {faults}")


def cases() -> list[Case]:
    return [Case("Python source comments and docstrings", _python_comments_and_docstrings),
            Case("Gallina, Sail, C and RTL comment boundaries", _comment_dialects_and_reference_links),
            Case("Declaration, heading and file renames", _declaration_and_heading_renames),
            Case("Indexed membership and safe local paths", _membership_and_path_safety),
            Case("Historical scope and unreadable referring sources", _historical_scope_and_unreadable_sources),
            Case("Indexed directories and directory refusal controls", _indexed_directories),
            Case("Sail declarations require a current compiler identity", _sail_identity)]
