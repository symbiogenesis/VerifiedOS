#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regenerate Q12's static record and comparison from captured instrument output.

Run with --check to compare without writing. The original Q4a parser owns tensor
arithmetic; its budget record owns the floor conventions. No timed rate is used.
"""
import argparse
import hashlib
import json
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def last_number(log: str, pattern: str) -> float:
    values = re.findall(pattern, log)
    if not values:
        raise ValueError(f"missing loader observation: {pattern}")
    return float(values[-1])


def outputs() -> dict[Path, str]:
    packet_path = ROOT / "ternary-observations.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    loader_logs = packet.get("loader_logs")
    if not isinstance(loader_logs, dict) or set(loader_logs) != {"f16", "q8_0"}:
        raise ValueError("loader observations must contain exactly f16 and q8_0")
    download = packet["download"]
    listed = packet["publisher_listing"]
    if not (download["verified"] and download["bytes"] == listed["size"]
            and download["sha256"] == listed["lfs"]["oid"]):
        raise ValueError("the captured full-file digest/size does not match the publisher")
    static = runpy.run_path(str(ROOT / "static.py"))["summarize"](
        packet["tensor_listing"].splitlines(), download["model"])
    if static["tensor_count"] != int(last_number(packet["tensor_listing"], r"gguf_ex_read_1: n_tensors: (\d+)")):
        raise ValueError("incomplete tensor listing")
    base = json.loads((ROOT / "static-Q4_K_M.json").read_text(encoding="utf-8"))
    old_budget = json.loads((ROOT / "budget.json").read_text(encoding="utf-8"))
    terms = old_budget["terms"]
    density = static["total_bytes"] * 8 / static["n_params_from_ne"]
    base_density = base["total_bytes"] * 8 / base["n_params_from_ne"]
    rows = []
    for cache in ("f16", "q8_0"):
        log = loader_logs[cache]
        ctx = int(last_number(log, r"n_ctx\s+= (\d+)"))
        if ctx != terms["context_tokens"]:
            raise ValueError("loader context differs from the comparison context")
        layers = int(last_number(log, r"n_layer\s+= (\d+)"))
        heads = int(last_number(log, r"n_head_kv\s+= (\d+)"))
        key = int(last_number(log, r"n_embd_head_k\s+= (\d+)"))
        value = int(last_number(log, r"n_embd_head_v\s+= (\d+)"))
        elements = layers * heads * (key + value)
        kv_token = elements * 2 if cache == "f16" else elements // 32 * 34
        if cache == "q8_0" and elements % 32:
            raise ValueError("KV geometry is not a whole number of q8_0 blocks")
        kv_mib = last_number(log, r"CPU KV buffer size =\s+([0-9.]+) MiB")
        if kv_mib * 2**20 != kv_token * ctx:
            raise ValueError("KV arithmetic disagrees with the allocated buffer")
        compute_mib = last_number(log, r"CPU compute buffer size =\s+([0-9.]+) MiB")
        output_mib = last_number(log, r"CPU\s+output buffer size =\s+([0-9.]+) MiB")
        mapped_mib = last_number(log, r"CPU_Mapped model buffer size =\s+([0-9.]+) MiB")
        vocab = static["token_embd"]["ne"][1]
        output_bytes = vocab * 4
        if abs(output_mib * 2**20 - output_bytes) > 0.005 * 2**20:
            raise ValueError("output row geometry disagrees with the rounded loader observation")
        weight = static["weight_bytes_read_per_token"]
        demand = terms["rate_tokens_per_second"] * (weight + kv_token * ctx)
        resident = static["total_bytes"] + kv_token * ctx + compute_mib * 2**20 + output_bytes
        rows.append({
            "cache": cache, "context": ctx, "kv_bytes_per_token": kv_token,
            "kv_bytes_at_context": kv_token * ctx, "compute_mib_logged": compute_mib,
            "output_mib_logged": output_mib, "output_row_bytes": output_bytes,
            "model_mapped_mib_logged": mapped_mib,
            "graph_nodes": int(last_number(log, r"graph nodes\s+= (\d+)")),
            "weight_bytes_read_per_token": weight, "demand_bytes_per_second": demand,
            "weights_only_bytes_per_second": terms["rate_tokens_per_second"] * weight,
            "grant_floor_multiple": demand / terms["m_class_grant_floor_bytes_per_second"],
            "aggregate_floor_fraction": demand / terms["aggregate_floor_bytes_per_second"],
            "resident_bytes_from_logged_compute": resident,
            "resident_rounding_half_width_bytes": 0.005 * 2**20,
            "payload_floor_multiple": resident / terms["usable_second_class_payload_bytes_floor"],
        })
    budget = {
        "scope": "static demand; target timing and quality are not measured",
        "observations_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        "terms": terms, "bits_per_parameter_unrounded": density,
        "baseline_bits_per_parameter_unrounded": base_density,
        "baseline_to_ternary_density_multiple": base_density / density,
        "arithmetic": "same Q4a budget: rate * (weight stream + KV at context); resident = tensor bytes + KV + logged compute MiB * 2^20 + one f32 vocabulary row",
        "precision": "compute MiB is printed to two decimals; resident carries its half-unit rounding interval, not a claim of exact allocated bytes",
        "measured": rows,
    }
    table = "\n".join(
        f"| {r['cache']} | {r['kv_bytes_per_token']:,} | {r['kv_bytes_at_context']:,} | {r['compute_mib_logged']:.2f} | {r['output_mib_logged']:.2f} | {r['demand_bytes_per_second']/1e9:.3f} | {r['grant_floor_multiple']:.3f} | {r['aggregate_floor_fraction']:.3f} | {r['resident_bytes_from_logged_compute']/1e9:.3f} | {r['payload_floor_multiple']:.3f} |"
        for r in rows)
    comparison = []
    for r in old_budget["measured"]:
        if r["quant"] == "Q4_K_M":
            comparison.append(f"| Q4a Q4_K_M | {r['cache']} | {r['demand_bytes_per_second_at_5_tokens_per_second']/1e9:.3f} | {r['resident_bytes']/1e9:.3f} |")
    for r in rows:
        comparison.append(f"| Q12 Q2_0_g64 | {r['cache']} | {r['demand_bytes_per_second']/1e9:.3f} | {r['resident_bytes_from_logged_compute']/1e9:.3f} |")
    comparison_table = "\n".join(comparison)
    report = f"""# Ternary static demand

Generated by [ternary.py](inference-demand/ternary.py) from the captured
[instrument output](inference-demand/ternary-observations.json).
Run `python docs/performance/inference-demand/ternary.py --check` to hold this
view and both JSON outputs against their owners.

## Identity and instrument boundary

Q12 measures the publisher's `prism-ml/Ternary-Bonsai-4B-gguf` conversion
`{download['model']}` at revision `{download['revision']}`.
Its {download['bytes']:,} downloaded bytes hash to `{download['sha256']}`,
equal to the publisher's tree listing before loading. The exact-revision
license and intended-use reading is in [THIRD-PARTY.md](../../THIRD-PARTY.md).
No weight or upstream executable is tracked here.

The instrument is the existing llama.cpp source pin
`{packet['instrument_commit']}`, rebuilt CPU-only with the recorded flags.
Its banner reports build 1 because the checkout is shallow; that is a local
build counter, not a different source revision or a new upstream release.
The publisher's 64-element-block file matches this pin's Q2_0 definition.
The older 128-element-block file does not; the shared type name alone is
insufficient evidence of compatible geometry.

`static.py` reads a textual tensor listing, not GGUF bytes. The invocation
`llama-gguf <file> r n` calls both readers; `gguf_ex_read_1` sets `no_alloc`
false and loads the tensor blob. The `n` argument disables its synthetic-data
check, not loading. The full-file digest also requires the complete file, and
the resident-buffer predicate requires a loader run. A ranged header fetch
therefore cannot satisfy this item's four predicates. All four ran here.

## Static predicates and results

1. Weight bytes sum every `gguf_ex_read_1` tensor-size line, with each size
   computed by the pinned reader. The file has {static['tensor_count']} tensors,
   {static['n_params_from_ne']:,} elements from tensor dimensions, and
   {static['total_bytes']:,} tensor bytes. File metadata is outside that sum.
2. Bytes read per generated token sum every block, normalization and tied-head
   tensor plus one input embedding row: {static['weight_bytes_read_per_token']:,}
   bytes. The row is {static['embedding_row_bytes']:,} bytes over a vocabulary
   of {static['token_embd']['ne'][1]:,}, read from the file rather than the model
   card. This is dense batch-one traffic, not a measured bandwidth.
3. KV bytes per token count the file's layers, KV heads and key/value widths,
   using two bytes per f16 element or 34 bytes per 32 q8_0 elements. The
   allocation at the declared context agrees with that arithmetic in each run.
4. Resident demand reads the loader's buffer-size lines at context 8,192,
   batch 2,048 and micro-batch 512, separately for f16 and q8_0 (flash attention).
   It charges one weight copy, KV, compute scratch and one f32 output row, as
   Q4a does. Compute is logged to two decimals in MiB; resident results carry
   that rounding uncertainty. No repack buffer was reported for this file.

The measured tensor density is {density:.6f} bits per parameter, compared with
Q4a's measured Q4_K_M density {base_density:.6f}. Their ratio is
{base_density/density:.6f}; it is not a ratio between nominal bit widths.
The narrower file also has a smaller vocabulary than Q4a's weight. This
comparison does not assume identical model quality or identical tensor count
implies identical parameter count.

## Same budget arithmetic as Q4a

Rate, context, decimal units and supply-floor conventions are read directly
from [Q4a's budget](inference-demand/budget.json). The detailed values and
rounding interval are in [ternary-budget.json](inference-demand/ternary-budget.json).

| Cache | KV bytes/token | KV bytes/context | Compute MiB | Output MiB | Read GB/s | Grant-floor multiple | Aggregate-floor fraction | Resident GB | Payload-floor multiple |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{table}

| Measured configuration | Cache | Read GB/s | Resident GB |
| --- | --- | --- | --- |
{comparison_table}

The weight-only stream is {rows[0]['weights_only_bytes_per_second']/1e9:.3f} GB/s
at the existing generation floor and fits the minimum M-class read grant.
Including the declared-context KV reads exceeds that grant floor in both
cache formats. Both resident comparisons lie below the whole second-class
payload floor, which does not establish a roster fit: other consumers still
need their shares. Cache and scratch placement remain the memory plan's
decision. Supply floors can be exceeded by a qualified composition; they are
not demand caps.

The bytes do not measure prompt processing, token generation throughput,
energy, target kernels, bank qualification or quality. Q1 owns the quality
threshold and its representative comparator; Q4b owns target evidence. A
ternary member would require the joint register, demonstration-set and
alternative-disposition act described in
[the prompt-processing contract](prompt-processing-term.md), which also
records the missing numerical prompt limit. No format amendment is taken here.
"""
    return {
        ROOT / "static-Q2_0_g64.json": json.dumps(static, indent=1) + "\n",
        ROOT / "ternary-budget.json": json.dumps(budget, indent=1) + "\n",
        ROOT.parent / "ternary-static-demand.md": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift = []
    for path, text in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                drift.append(str(path))
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
    if drift:
        raise SystemExit("derived ternary output differs: " + ", ".join(drift))
    print("ternary static outputs agree" if args.check else "ternary static outputs written")


if __name__ == "__main__":
    main()
