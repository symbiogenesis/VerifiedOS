#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sum the per-tensor byte figures llama-gguf prints for one GGUF file.

Predicate: every `gguf_ex_read_1: tensor[i]: name = N, size = S, ..., type = T, n_elts = E`
line of the tool's output, S being ggml_nbytes as the tool's own reader computes it, and
every `gguf_ex_read_1: tensor[i]: n_dims = D, ne = (a, b, c, d), name = N` line, whose
product is the tensor's element count (the tool's own n_elts is size / type_size, which for a
block-quantized type counts blocks rather than elements).
"""
import json
import re
import sys
from collections import defaultdict

LINE = re.compile(
    r"gguf_ex_read_1: tensor\[(\d+)\]: name = (\S+), size = (\d+), offset = (\d+), "
    r"type = (\S+), n_elts = (\d+)"
)
DIMS = re.compile(
    r"gguf_ex_read_1: tensor\[(\d+)\]: n_dims = (\d+), ne = \((\d+), (\d+), (\d+), (\d+)\), name = (\S+),"
)


def main(path: str) -> None:
    tensors: list[dict[str, object]] = []
    dims: dict[str, tuple[int, ...]] = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        m = LINE.match(s)
        if m:
            tensors.append(
                {
                    "name": m.group(2),
                    "bytes": int(m.group(3)),
                    "type": m.group(5),
                    "blocks_size_over_type_size": int(m.group(6)),
                }
            )
            continue
        d = DIMS.match(s)
        if d:
            dims[d.group(7)] = tuple(int(d.group(i)) for i in range(3, 7))
    for t in tensors:
        ne = dims[str(t["name"])]
        t["n_elts"] = ne[0] * ne[1] * ne[2] * ne[3]
        t["ne"] = list(ne)
    names = {str(t["name"]) for t in tensors}
    total = sum(int(t["bytes"]) for t in tensors)
    embd = next((t for t in tensors if t["name"] == "token_embd.weight"), None)
    out_w = next((t for t in tensors if t["name"] == "output.weight"), None)
    blk = sum(int(t["bytes"]) for t in tensors if str(t["name"]).startswith("blk."))
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: {"tensors": 0, "bytes": 0, "n_elts": 0})
    for t in tensors:
        d2 = by_type[str(t["type"])]
        d2["tensors"] += 1
        d2["bytes"] += int(t["bytes"])
        d2["n_elts"] += int(t["n_elts"])
    n_layers = len({n.split(".")[1] for n in names if n.startswith("blk.")})
    per_layer: dict[str, int] = {}
    for t in tensors:
        if str(t["name"]).startswith("blk.0."):
            per_layer[str(t["name"]).split(".", 2)[2]] = int(t["bytes"])
    n_params = sum(int(t["n_elts"]) for t in tensors)
    tied = out_w is None
    # Bytes read per generated token under dense decoding: every block tensor, the output
    # norm, and the language-model head. With a tied head the head is token_embd.weight read
    # whole; the input lookup adds one row, which is the matrix's bytes over n_vocab.
    other = sum(
        int(t["bytes"]) for t in tensors
        if not str(t["name"]).startswith("blk.") and t["name"] not in ("token_embd.weight", "output.weight")
    )
    head_bytes = (int(embd["bytes"]) if tied else int(out_w["bytes"])) if (embd or out_w) else 0
    per_token_excl_lookup = blk + other + head_bytes
    result = {
        "source": path,
        "tensor_count": len(tensors),
        "total_bytes": total,
        "n_params_from_ne": n_params,
        "n_layers": n_layers,
        "token_embd": embd,
        "output_weight": out_w,
        "output_head_tied": tied,
        "block_bytes": blk,
        "non_block_non_embd_bytes": other,
        "head_bytes": head_bytes,
        "weight_bytes_read_per_token_excluding_lookup_row": per_token_excl_lookup,
        "by_type": dict(by_type),
        "layer0_tensor_bytes": per_layer,
    }
    json.dump(result, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main(sys.argv[1])
