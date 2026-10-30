# SPDX-License-Identifier: Apache-2.0
"""Small transport fixtures; no native-sized census or performance run executes."""

import gzip
import hashlib
import json
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case

_BENCHMARK = runpy.run_path(str(Path(__file__).resolve().parents[1] / "ci/census_benchmark.py"))


class CensusBenchmarkTests(unittest.TestCase):
    def test_retained_inputs_bind_complete_raw_bytes_and_native_readings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vos-census-transport-fixture-") as temporary:
            root = Path(temporary)
            bundle = root / "bundle"
            bundle.mkdir()
            raw = b'{"small_fixture":true}\n'
            query = "Print Module Fixture.\n"
            envelope = {"schema": "verifiedos-native-census-output/1", "census_schema": "verifiedos-sail-support-census/1",
                        "path": "/retained/provider/native-census.json", "bytes": len(raw),
                        "blake2b_256": hashlib.blake2b(raw, digest_size=32).hexdigest()}
            files = {"provider/native-census.json.gz": gzip.compress(raw, mtime=0),
                     "provider/receipt.json": json.dumps({"search_targets": ["Fixture"], "exit": 0, "native_exit": 0,
                         "query_completed": True, "metadata_validated": True, "native_output_validation": {"envelope": envelope}}).encode(),
                     "provider/native-query.stdout.log": json.dumps(envelope).encode(),
                     "provider/native-query.stderr.log": b"", "provider/native-search-00.stdout.log": b"Fixture.x: Prop\n",
                     "provider/native-search-00.stderr.log": b"", "provider/Search00.v": b"Search Fixture.\n",
                     "readings/reading-targets.json": b'[["module","Fixture"]]',
                     "readings/receipt.json": json.dumps({"commands": [{"kind": "module", "target": "Fixture", "exit": 0,
                         "source_sha256_after": hashlib.sha256(query.encode()).hexdigest()}]}).encode(),
                     "readings/Reading000.v": query.encode(), "readings/Reading000.stderr.log": b"",
                     "readings/Reading000.stdout.log": b"Module Fixture := Struct End\n"}
            records: dict[str, dict[str, object]] = {}
            for name, content in files.items():
                path = bundle / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                expanded = raw if name.endswith(".gz") else content
                records[name] = {"path": name, "encoding": "gzip" if name.endswith(".gz") else "identity",
                                 "bytes": len(expanded), "sha256": hashlib.sha256(expanded).hexdigest()}
                if name.endswith(".gz"):
                    records[name].update(stored_bytes=len(content), stored_sha256=hashlib.sha256(content).hexdigest())
            manifest = bundle / "manifest.json"
            manifest.write_text(json.dumps({"files": records}), encoding="utf-8")
            specification = {"manifest": "bundle/manifest.json", "raw": "provider/native-census.json.gz",
                             "provider": "provider", "readings": "readings"}
            scratch = root / "expanded"
            scratch.mkdir()
            prepared = _BENCHMARK["prepare_dataset"](root, specification, ["Fixture"], scratch)
            self.assertEqual(Path(prepared["raw"]).read_bytes(), raw)
            self.assertEqual(prepared["roots"], ["Fixture"])
            self.assertEqual(prepared["readings"], {"module:Fixture": "Module Fixture := Struct End\n"})
            self.assertEqual(len(prepared["input_hashes"]), len(files) + 1)
            # Authenticated stored bytes still require every gzip trailer and the
            # original expanded identity; a matching manifest cannot hide damage.
            corrupted = files["provider/native-census.json.gz"][:-1] + b"\xff"
            (bundle / "provider/native-census.json.gz").write_bytes(corrupted)
            records["provider/native-census.json.gz"]["stored_sha256"] = hashlib.sha256(corrupted).hexdigest()
            manifest.write_text(json.dumps({"files": records}), encoding="utf-8")
            second = root / "corrupt-expanded"
            second.mkdir()
            with self.assertRaises((ValueError, OSError, EOFError)):
                _BENCHMARK["prepare_dataset"](root, specification, ["Fixture"], second)

    def test_benchmark_helpers_keep_diagnostic_order_and_refuse_duplicates_and_escape(self) -> None:
        self.assertNotEqual(_BENCHMARK["value_digest"]({"first": "a", "second": "b"}),
                            _BENCHMARK["value_digest"]({"second": "b", "first": "a"}))
        with self.assertRaisesRegex(ValueError, "duplicate native JSON key"):
            json.loads('{"key":0,"key":1}', object_pairs_hook=_BENCHMARK["unique"])
        with (tempfile.TemporaryDirectory(prefix="vos-census-path-fixture-") as temporary,
              self.assertRaisesRegex(ValueError, "escapes")):
            _BENCHMARK["relative"](Path(temporary), "../elsewhere")
        with patch.dict("os.environ", {"GITHUB_ACTIONS": "false"}), patch("sys.argv", ["census_benchmark.py", "--output", "unused"]):
            with self.assertRaises(SystemExit) as refusal:
                _BENCHMARK["main"]()
            self.assertEqual(refusal.exception.code, 2)


def cases() -> list[Case]:
    tests = CensusBenchmarkTests()
    return [Case("retained-census-transport-binds-raw-native-reading-identities", tests.test_retained_inputs_bind_complete_raw_bytes_and_native_readings),
            Case("census-comparison-keeps-order-and-refuses-duplicate-escape-local-run", tests.test_benchmark_helpers_keep_diagnostic_order_and_refuse_duplicates_and_escape)]
