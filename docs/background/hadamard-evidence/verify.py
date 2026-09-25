#!/usr/bin/env python3
"""Recheck the twelve finite Hadamard matrices named in manifest.json."""

import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
REPORT = HERE / "verification.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_rows(data: bytes, order: int) -> int:
    """Check H H^T = order I using exact sign and Hamming comparisons."""
    packed_rows: list[int] = []
    reader = csv.reader(io.StringIO(data.decode("ascii")), strict=True)
    for row_number, row in enumerate(reader, start=1):
        if row_number > order or len(row) != order:
            raise ValueError(f"wrong dimensions at row {row_number}")
        packed = 0
        for column, cell in enumerate(row, start=1):
            if cell not in ("1", "-1"):
                raise ValueError(f"non-sign entry at row {row_number}, column {column}")
            if cell == "1":
                packed |= 1 << (column - 1)
        for earlier, old in enumerate(packed_rows, start=1):
            if (packed ^ old).bit_count() != order // 2:
                raise ValueError(f"nonorthogonal rows {earlier} and {row_number}")
        packed_rows.append(packed)
    if len(packed_rows) != order:
        raise ValueError(f"wrong row count: {len(packed_rows)} instead of {order}")
    return order * (order - 1) // 2


def check_controls() -> None:
    positive = b"1,1,1,1\n1,-1,1,-1\n1,1,-1,-1\n1,-1,-1,1\n"
    if check_rows(positive, 4) != 6:
        raise AssertionError("positive control failed")
    negative = positive.replace(b"1,-1,1,-1\n", b"-1,-1,1,-1\n")
    try:
        check_rows(negative, 4)
    except ValueError:
        return
    raise AssertionError("one-bit-corrupt negative control accepted")


def load_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    revision = manifest["source_revision"]
    entries = manifest["files"]
    if not entries:
        raise ValueError("empty manifest")
    orders: set[int] = set()
    for entry in entries:
        order = entry["order"]
        if not isinstance(order, int) or order <= 0 or order % 4:
            raise ValueError(f"invalid Hadamard order: {order!r}")
        if order in orders or entry["name"] != f"hadamard_{order}.csv.gz":
            raise ValueError(f"duplicate order or wrong file name: {order}")
        orders.add(order)
        if f"/{revision}/matrices/{entry['name']}" not in entry["download_url"]:
            raise ValueError(f"URL does not name the pinned file: {order}")
        for digest_key in ("sha256_gzip", "sha256_csv"):
            digest = entry[digest_key]
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError(f"invalid {digest_key}: {order}")
    return manifest


def read_matrix(entry: dict, input_dir: Path, download: bool) -> bytes:
    path = input_dir / entry["name"]
    if download:
        with urlopen(entry["download_url"], timeout=60) as response:
            compressed = response.read()
    else:
        compressed = path.read_bytes()
    if sha256(compressed) != entry["sha256_gzip"]:
        raise ValueError(f"compressed SHA-256 mismatch: {entry['name']}")
    if download:
        input_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(compressed)
    return compressed


def verify(manifest: dict, input_dir: Path, download: bool) -> dict:
    check_controls()
    results = []
    for entry in manifest["files"]:
        compressed = read_matrix(entry, input_dir, download)
        data = gzip.decompress(compressed)
        if sha256(data) != entry["sha256_csv"]:
            raise ValueError(f"decoded SHA-256 mismatch: {entry['name']}")
        pairs = check_rows(data, entry["order"])
        results.append(
            {
                "order": entry["order"],
                "checked_distinct_row_pairs": pairs,
                "sha256_gzip": sha256(compressed),
                "sha256_csv": sha256(data),
                "verdict": "PASS",
            }
        )
        print(f"order {entry['order']}: PASS ({pairs} distinct row pairs)", flush=True)
    return {
        "source_revision": manifest["source_revision"],
        "method": "Exact square dimensions, +/-1 alphabet, and Hamming distance n/2 for every distinct row pair; diagonal norms follow from the sign alphabet.",
        "controls": "Order-4 positive and one-bit-corrupt negative controls passed.",
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path, help="directory for the 12 .csv.gz files")
    parser.add_argument("--download", action="store_true", help="fetch pinned URLs into the input directory")
    parser.add_argument("--write-report", action="store_true", help="regenerate tracked verification.json")
    args = parser.parse_args()
    report = verify(load_manifest(), args.input_dir, args.download)
    if args.write_report:
        with REPORT.open("w", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(report, indent=2) + "\n")
        print(f"wrote {REPORT}")
    elif report != json.loads(REPORT.read_text(encoding="utf-8")):
        raise ValueError("verification.json differs from the exact rerun")
    else:
        print(f"verified all {len(report['results'])} matrices and the tracked report")


if __name__ == "__main__":
    main()
