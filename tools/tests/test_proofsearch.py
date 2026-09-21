# SPDX-License-Identifier: Apache-2.0
"""Source navigation contracts, including freshness and misleading lexical text."""

import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator
from vos import proofcites, proofsearch
from vos.cli import proof_search

from tests.harness import TOOLS, Case, ensure, sandbox_tree


def _call(root: Path, args: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with (patch.object(proof_search, "find_root", return_value=root),
          redirect_stdout(stdout), redirect_stderr(stderr)):
        try:
            code = proof_search.main(args)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, stdout.getvalue(), stderr.getvalue()


def _names(report: proofsearch.Report) -> list[str]:
    return [match["name"] for match in report["matches"]]


def _ranking_and_exclusion() -> None:
    files = {
        "proofs/Z.v": "Lemma alpha_z : True. Proof. exact I. Qed.\n",
        "proofs/A.v": ("Lemma statement : alpha. Proof. exact I. Qed.\n"
                       "Lemma script : True. Proof. apply alpha. Qed.\n"
                       "Lemma alpha_a : True. Proof. exact I. Qed.\n"
                       "Lemma alpha_b : True. Proof. exact I. Qed.\n"),
    }
    with sandbox_tree(files) as root:
        result = proofsearch.search(root, "alpha")
        ensure(_names(result) == ["alpha_a", "alpha_b", "alpha_z", "statement", "script"],
               f"name, statement, body and source-order ranking: {result}")
        ensure(result == proofsearch.search(root, "alpha"), "identical reads must rank identically")
        result = proofsearch.search(root, "ALPHA", exclude=("proofs/A.v",))
        ensure(_names(result) == ["alpha_z"] and result["sources_read"] == 1,
               "the excluded target must never supply an example")


def _comments_strings_and_locations() -> None:
    source = ('(* Lemma invented : False. Proof. auto. Qed. (* nested *) *)\n'
              'Definition text := "Qed. Lemma fake : True. (* not a comment *) '
              '""quoted""".\n'
              'Lemma actual : True.\n'
              'Proof. (* auto *) idtac "auto. Qed."; exact I.\nQed.\n')
    with sandbox_tree({"proofs/A.v": source}) as root:
        ensure(not proofsearch.search(root, "invented fake")["matches"],
               "comments and string contents must not create declarations")
        ensure(not proofsearch.search(root, tactics=("auto",))["matches"],
               "tactic filters must ignore comments and strings")
        result = proofsearch.search(root, tactics=("exact",))
        hit = result["matches"][0]
        ensure(_names(result) == ["actual"] and hit["status"] == "complete",
               "the real closing command must survive string punctuation")
        ensure(hit["line"] == 3 and hit["end_line"] == 5,
               f"masking must preserve source lines: {hit}")
        ensure(hit["excerpt"] == source[source.index("Lemma actual"):].rstrip(),
               "excerpts must retain original comments and strings")


def _statuses_and_direct_bodies() -> None:
    source = ("Lemma closed : True. Proof. exact I. Qed.\n"
              "Definition transparent : True. Proof. exact I. Defined.\n"
              "Lemma placeholder : True. Admitted.\n"
              "Lemma abandoned : True. Proof. Abort.\n"
              "Lemma interrupted : True. Proof. idtac.\n"
              "Definition direct := 1.\n"
              "Definition binder (n := 0) : True. Proof. exact I. Defined.\n"
              "#[local] Polymorphic Lemma modified : True. Proof. exact I. Qed.\n"
              "Lemma tail : True. Proof. exact I")
    with sandbox_tree({"proofs/A.v": "(* R-01-001 *)\n" + source}) as root:
        result = proofsearch.search(root, requirements=("R-01-001",), limit=50)
        statuses = {hit["name"]: hit["status"] for hit in result["matches"]}
        ensure(statuses == {"closed": "complete", "transparent": "complete",
                            "placeholder": "admitted", "abandoned": "aborted",
                            "interrupted": "incomplete", "direct": "definition",
                            "binder": "complete", "modified": "complete", "tail": "incomplete"},
               f"statuses distinguish lexical endings without certifying them: {statuses}")
        interrupted = next(hit for hit in result["matches"] if hit["name"] == "interrupted")
        ensure("Definition direct" not in interrupted["excerpt"],
               "an unfinished script must stop before the next declaration")


def _attributes_and_unfinished_strings() -> None:
    source = ('#[deprecated(since="a] Lemma fabricated : True. Qed.")]\n'
              'Lemma actual : True. Proof. exact I. Qed.\n'
              'Definition unfinished := "preserve this final string"')
    with sandbox_tree({"proofs/A.v": source}) as root:
        ensure(not proofsearch.search(root, "fabricated")["matches"],
               "attribute strings must not produce declaration names or query terms")
        ensure(_names(proofsearch.search(root, "actual")) == ["actual"],
               "an attribute containing brackets in a string must preserve its declaration")
        hit = proofsearch.search(root, "unfinished")["matches"][0]
        ensure(hit["status"] == "incomplete" and hit["excerpt"].endswith('final string"'),
               "an unfinished declaration must retain its final string in the raw excerpt")


def _citations_and_filters() -> None:
    source = (f"(* R-01-001a R-02-002\n{proofcites.DERIVED_BEGIN}\n"
              f"R-03-003\n{proofcites.DERIVED_END}\n*)\n"
              "Lemma pair : True. Proof. intros; exact I. Qed.\n"
              "Lemma one : True. Proof. exact I. Qed.\n")
    with sandbox_tree({"proofs/A.v": source}) as root:
        result = proofsearch.search(root, tactics=("intros", "exact"),
                                    requirements=("R-01-001a", "R-02-002"))
        ensure(_names(result) == ["pair"], "every tactic and requirement filter must match")
        ensure(result["matches"][0]["requirements"] == ["R-01-001a", "R-02-002"],
               "generated requirement manifests must not add authored citations")
        ensure(not proofsearch.search(root, requirements=("R-03-003",))["matches"],
               "derived references must never satisfy a requirement filter")
        ensure(not proofsearch.search(root, tactics=("intro",))["matches"],
               "tactic words must be complete tokens")


def _fresh_reads_and_hashes() -> None:
    with sandbox_tree({"proofs/A.v": "Definition alpha := 1.\r\n"}) as root:
        path = root / "proofs/A.v"
        first = proofsearch.search(root, "alpha")["matches"][0]
        ensure(first["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest(),
               "hash the original bytes including CRLF")
        path.write_text("Definition beta := 2.\n", encoding="utf-8", newline="")
        ensure(not proofsearch.search(root, "alpha")["matches"], "edited sources must be reread")
        second = proofsearch.search(root, "beta")["matches"][0]
        ensure(second["source_sha256"] != first["source_sha256"], "content edits must change hashes")
        added = root / "proofs/New.v"
        added.write_text("Definition gamma := 3.\n", encoding="utf-8", newline="")
        ensure(_names(proofsearch.search(root, "gamma")) == ["gamma"],
               "new untracked local proof sources belong to navigation")
        added.unlink()
        ensure(not proofsearch.search(root, "gamma")["matches"], "deleted sources must disappear")


def _bounded_output_and_schema() -> None:
    source = "".join(f"Lemma long_{n} : True. Proof. (* {'x' * 400} *) exact I. Qed.\n"
                     for n in range(3))
    schema = json.loads((TOOLS / "proof-search.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    with sandbox_tree({"proofs/A.v": source}) as root:
        status, stdout, stderr = _call(root, ["long", "--limit", "2", "--max-chars", "256", "--json"])
        ensure(status == 0 and not stderr, f"JSON command failed: {stderr}")
        result = json.loads(stdout)
        validator.validate(result)
        ensure(result["advisory_only"] and result["version"] == 1,
               "machine output must carry its trust boundary and schema version")
        ensure(result["total_matches"] == 3 and result["truncated"] and len(result["matches"]) == 2,
               "result bounds must report omitted matches")
        ensure(all(len(hit["excerpt"]) == 256 and hit["excerpt_truncated"]
                   for hit in result["matches"]), "excerpt bounds must be explicit")
        status, stdout, stderr = _call(root, ["absent", "--json"])
        validator.validate(json.loads(stdout))
        ensure(status == 0 and not stderr, "zero matches is successful navigation")
        status, stdout, stderr = _call(root, ["long", "--limit", "1", "--max-chars", "256"])
        ensure(status == 0 and proofsearch.ADVISORY in stdout and
               "[excerpt truncated]" in stdout and "[result list truncated]" in stdout,
               "human output must retain the warning and bounds")


def _input_errors() -> None:
    with sandbox_tree({"proofs/A.v": "Definition value := 0."}) as root:
        invalid = [[], ["---"], ["value", "--limit", "0"], ["value", "--limit", "51"],
                   ["value", "--max-chars", "255"], ["value", "--max-chars", "16001"],
                   ["--tactic", "exact I"], ["--requirement", "R-1-001"],
                   ["value", "--exclude", "../A.v"], ["value", "--exclude", "proofs/nested/A.v"]]
        for args in invalid:
            status, stdout, stderr = _call(root, args)
            ensure(status == 2 and not stdout and stderr,
                   f"malformed selectors require a usage diagnostic: {args}, {status}, {stderr}")
        status, stdout, stderr = _call(root, ["--help"])
        ensure(status == 0 and "--tactic" in stdout and not stderr, "help must need no search")


def _source_errors() -> None:
    malformed = ["Lemma bad : True. (* unclosed", 'Definition bad := "unclosed',
                 "Definition bad := 0. *)", f"(* {proofcites.DERIVED_BEGIN} *)"]
    with sandbox_tree({"proofs/A.v": "Definition good := 1."}) as root:
        broken = root / "proofs/B.v"
        for source in malformed:
            broken.write_text(source, encoding="utf-8", newline="")
            status, stdout, stderr = _call(root, ["good", "--json"])
            ensure(status == 1 and not stdout and "proofs/B.v" in stderr,
                   f"malformed source must invalidate the whole search: {stderr}")
        broken.write_bytes(b"\xff")
        status, stdout, stderr = _call(root, ["good", "--json"])
        ensure(status == 1 and not stdout and "proofs/B.v" in stderr,
               "undecodable source must not silently disappear")
        broken.unlink()
        with patch.object(Path, "read_bytes", side_effect=PermissionError("fixture denial")):
            status, stdout, stderr = _call(root, ["good", "--json"])
        ensure(status == 1 and not stdout and "fixture denial" in stderr,
               "unreadable source must produce a diagnostic, never partial output")


def _corpus_boundaries() -> None:
    with sandbox_tree({"proofs/A.v": "Definition good := 1.",
                       "proofs/nested/B.v": "Definition hidden := 2."}) as root:
        status, stdout, stderr = _call(root, ["good", "--json"])
        ensure(status == 1 and not stdout and "directly in proofs/" in stderr,
               "nested sources must be rejected instead of silently omitted")
    with sandbox_tree({"proofs/A.v": "Definition good := 1."}) as root:
        # Mock only the link metadata so this control runs without Windows symlink privileges.
        with patch.object(Path, "is_symlink", side_effect=[False, True]):
            status, stdout, stderr = _call(root, ["good", "--json"])
        ensure(status == 1 and not stdout and "linked paths" in stderr,
               "linked files must be refused before they are read")


def cases() -> list[Case]:
    return [
        Case("ranking-and-exclusion", _ranking_and_exclusion),
        Case("comments-strings-locations", _comments_strings_and_locations),
        Case("lexical-statuses", _statuses_and_direct_bodies),
        Case("attributes-and-unfinished-strings", _attributes_and_unfinished_strings),
        Case("authored-citations-and-filters", _citations_and_filters),
        Case("fresh-reads-and-byte-hashes", _fresh_reads_and_hashes),
        Case("bounded-output-and-json-schema", _bounded_output_and_schema),
        Case("input-errors", _input_errors),
        Case("source-errors", _source_errors),
        Case("corpus-boundaries", _corpus_boundaries),
    ]
