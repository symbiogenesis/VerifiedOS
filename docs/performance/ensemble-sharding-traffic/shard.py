#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit traffic.json whole: the per-step ensemble link traffic of a sharded model.

Usage: shard.py <static-<quant>.json> <revision>

This is an extension of the inference-demand instrument and not a second harness. It
reads a tracked `static-<quant>.json`, which is [static.py](../inference-demand/static.py)'s
output byte for byte, and derives link traffic from that file's own geometry. It loads no
weight file, runs no model, and takes no time: every figure it emits is arithmetic over the
tensor bytes of a file whose digest [manifest.json](../inference-demand/manifest.json)
records, over the register's rate and over this report's declared parameters.

Predicate: the geometry is `n_layers` and `token_embd.ne` of the named static file, whose
own predicate is the sum of the size field over every gguf_ex_read_1 tensor line llama-gguf
prints; the traffic is the exchange arithmetic of the sharding shape the `shapes` block
declares, at the declared parameters, at R-18-004a(vii)'s five tokens per second; and the
revision is the argument the invocation supplies, which is the revision the figure is taken
at under R-17-008a.

Nothing here is a measurement of a device. The bytes are target bytes for the partition,
carried across from a host reading of a file; no host time enters any figure.
"""
import json
import sys

# R-18-004a(vii): at least five tokens per second sustained over a declared context of at
# least 8,192 tokens. The floor's rate and the floor's context, not this report's.
FLOOR_TOKEN_RATE = 5
FLOOR_CONTEXT = 8192

# R-18-004b: at least 8 GB/s of sustained second-class read granted to the M-class island,
# and at least 20 GB/s of sustained aggregate read plus write across all islands. Decimal
# gigabytes, which is inference-demand section 8's declared convention and not the
# register's; the register fixes no base for its unit.
GRANT_FLOOR_BYTES_PER_S = 8_000_000_000
AGGREGATE_FLOOR_BYTES_PER_S = 20_000_000_000

# Declared parameters of this report. No entry of the register fixes any of them, and each
# is declared rather than chosen: see the report's section 2 for what owes each.
ACTIVATION_WIDTHS = [2, 4]
FRAME_PAYLOADS = [256, 512, 1024, 2048, 4096, 8192, 16384]
MEMBER_COUNTS = [2, 4, 8]
DEFAULT_ACTIVATION_WIDTH = 4
DEFAULT_FRAME_PAYLOAD = 2048

# The KV geometry inference-demand section 5 derives from this model's own head counts:
# one key and one value vector per layer per token, n_head_kv 8 by n_embd_head 128, so
# 73,728 elements per token over 36 layers, 147,456 bytes at f16 and 78,336 at q8_0.
KV_BYTES_PER_TOKEN = {"f16": 147456, "q8_0": 78336}

PREDICATE = (
    "the per-step link traffic of one decode step of a dense model sharded over the members "
    "named, derived from the geometry of the named static-<quant>.json (hidden width "
    "token_embd.ne[0], layer count n_layers, matrix bytes block_bytes less the per-layer f32 "
    "norms, head bytes token_embd.weight read whole because the head is tied) at this "
    "report's declared activation width, frame payload, topology and collective algorithm, "
    "at R-18-004a(vii)'s five tokens per second and 8,192-token context; every byte is a "
    "target byte for the partition and no figure is a device measurement or a host time"
)


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def layer_partition(n_layers: int, members: int) -> list[int]:
    """Contiguous layers over members, the remainder on the first members.

    The member holding the largest block is the slowest shard, which is the member
    R-15-171a's bank-grant term is read on.
    """
    base, rem = divmod(n_layers, members)
    return [base + (1 if i < rem else 0) for i in range(members)]


def ring(members: int) -> dict[str, int]:
    """The declared topology: a cycle of point-to-point links, one endpoint pair per hop.

    R-02-003a joins members pairwise and carries each link's two endpoints in every
    member's attested devicetree; it declares no link count per member and no topology, so
    this is a parameter of this report. A cycle is the topology that costs each member two
    endpoints at every member count, where a fully connected topology costs each member
    members-1 endpoints, and an endpoint is a block with its own absence-contract rows
    (R-15-228c, rows A-18 through A-21) rather than a port. At two members the cycle
    degenerates to one full-duplex link and one endpoint per member.
    """
    if members == 2:
        return {"links": 1, "endpoints_per_member": 1}
    return {"links": members, "endpoints_per_member": 2}


def layerwise(geom: dict[str, int], members: int, act: int) -> dict[str, object]:
    """Pipeline sharding: contiguous layers per member, the activation crossing each stage.

    One decode step drives the hidden vector across the members-1 internal stage boundaries
    and then back to the member holding token_embd, which is the tied head (the file carries
    no output.weight), so the step is `members` serial exchanges around the cycle and each
    link carries exactly one of them. The next token's input lookup is on that same member,
    so the sampled token id crosses no link.
    """
    s = geom["hidden"] * act
    top = ring(members)
    return {
        "serial_exchanges_per_step": members,
        "serial_exchanges_per_step_formula": "M",
        "bytes_per_exchange": s,
        "transmissions_per_serial_position": 1,
        "bytes_per_link_per_direction_per_step": s,
        "bytes_per_link_per_step": s * (2 if members == 2 else 1),
        "ensemble_bytes_per_step": s * members,
        "pattern": {
            "repeat": 1,
            "repeat_meaning": "the whole decode step is one pass around the cycle",
            "serial_positions_per_repeat": members,
            "transmission": "at serial position i, member i sends to member (i+1) mod M "
                            "on link i; at position M-1 that is the return to the member "
                            "holding the tied head",
            "bytes_per_transmission": s,
        },
        **top,
    }


def tensorwise(geom: dict[str, int], members: int, act: int) -> dict[str, object]:
    """Tensor sharding: every layer's heads and FFN columns split, two all-reduces per layer.

    Each member holds a slice of every layer, so the partial sums after the attention output
    projection and after the FFN down projection must be summed across members: two
    all-reduces of the hidden vector per layer, 2L per decode step, and they are serial
    because layer n+1's input is layer n's output.

    The collective algorithm is a declared parameter, the register naming none. At two
    members it is reduce-and-broadcast: each member sends its whole partial and both sum
    locally, one serial exchange of S bytes per direction. Above two it is the ring
    reduce-scatter plus all-gather over the declared cycle: 2(M-1) serial hops per
    all-reduce, each member sending one chunk of S/M to its successor. R-02-003a forbids a
    member forwarding a frame, so each hop is a fresh frame under the receiving member's own
    schedule and is charged as one.
    """
    s = geom["hidden"] * act
    all_reduces = 2 * geom["layers"]
    top = ring(members)
    if members == 2:
        hops, chunk = 1, s
    else:
        hops, chunk = 2 * (members - 1), s // members
    serial = all_reduces * hops
    per_link_dir = serial * chunk
    return {
        "serial_exchanges_per_step": serial,
        "serial_exchanges_per_step_formula": "2L for M=2, 2L*2(M-1) for M>2",
        "bytes_per_exchange": chunk,
        "transmissions_per_serial_position": members if members > 2 else 2,
        "bytes_per_link_per_direction_per_step": per_link_dir,
        "bytes_per_link_per_step": per_link_dir * (2 if members == 2 else 1),
        "ensemble_bytes_per_step": per_link_dir * top["links"] * (2 if members == 2 else 1),
        "all_reduces_per_step": all_reduces,
        "serial_hops_per_all_reduce": hops,
        "pattern": {
            "repeat": all_reduces,
            "repeat_meaning": "all-reduces per decode step, two per layer over L layers",
            "serial_positions_per_repeat": hops,
            "transmission": "at every serial position every member sends one chunk to "
                            "member (m+1) mod M on link m, all M concurrently"
                            if members > 2 else
                            "at the one serial position both members send the whole partial "
                            "across the single full-duplex link",
            "bytes_per_transmission": chunk,
        },
        **top,
    }


def residency(geom: dict[str, int], shape: str, members: int) -> list[dict[str, object]]:
    """Per-member second-class read per token, against R-18-004b's grant floor.

    Layer-wise: the member's own layers, plus on the member holding token_embd the tied head
    read whole, the output norm and one embedding row for the input lookup. Tensor-wise:
    every member holds the same fraction of every layer's matrices, the per-layer norms and
    the output norm replicated (they are 21,504 bytes a layer, not worth a collective), the
    head column-sharded by vocabulary, and the embedding replicated so the input lookup
    needs no exchange, which is a declared placement and not an entry's.

    The layer figure is the file's mean layer, block_bytes over n_layers. This file's layers
    are not uniform: Q4_K_M assigns q6_K to some layers' down projections and attention value
    matrices and q4_K to others, so layer 0 is larger than the mean. The exact per-layer
    partition needs a re-read of the tensor listing and the report says so.
    """
    rows = []
    if shape == "layer-wise":
        part = layer_partition(geom["layers"], members)
        for i, n in enumerate(part):
            w = n * geom["mean_layer_bytes"]
            if i == 0:
                w += geom["head_bytes"] + geom["output_norm_bytes"] + geom["row_bytes"]
            rows.append({"member": i, "layers": n, "weight_bytes_per_token": w,
                         "kv_share": n / geom["layers"]})
    else:
        per = (geom["matrix_bytes"] // members + geom["layer_norm_bytes"]
               + geom["output_norm_bytes"] + geom["head_bytes"] // members
               + geom["row_bytes"])
        for i in range(members):
            rows.append({"member": i, "layers": geom["layers"],
                         "weight_bytes_per_token": per, "kv_share": 1 / members})
    for r in rows:
        w = int(r["weight_bytes_per_token"])
        r["weight_stream_bytes_per_s"] = w * FLOOR_TOKEN_RATE
        for fmt, kv in KV_BYTES_PER_TOKEN.items():
            k = int(round(kv * float(r["kv_share"]))) * FLOOR_CONTEXT
            r[f"kv_bytes_per_token_{fmt}"] = k
            d = (w + k) * FLOOR_TOKEN_RATE
            r[f"demand_bytes_per_s_{fmt}"] = d
            r[f"grant_floors_{fmt}"] = round(d / GRANT_FLOOR_BYTES_PER_S, 3)
            r[f"aggregate_share_{fmt}"] = round(d / AGGREGATE_FLOOR_BYTES_PER_S, 4)
        r["weight_stream_grant_floors"] = round(
            r["weight_stream_bytes_per_s"] / GRANT_FLOOR_BYTES_PER_S, 3)
    return rows


def main(static_path: str, revision: str) -> None:
    st = json.load(open(static_path, encoding="utf-8"))
    layer_norm_bytes = st["by_type"]["f32"]["bytes"] - st["non_block_non_embd_bytes"]
    geom = {
        "hidden": st["token_embd"]["ne"][0],
        "vocabulary": st["token_embd"]["ne"][1],
        "layers": st["n_layers"],
        "block_bytes": st["block_bytes"],
        "layer_norm_bytes": layer_norm_bytes,
        "matrix_bytes": st["block_bytes"] - layer_norm_bytes,
        "mean_layer_bytes": st["block_bytes"] // st["n_layers"],
        "head_bytes": st["head_bytes"],
        "head_tied": st["output_head_tied"],
        "output_norm_bytes": st["non_block_non_embd_bytes"],
        "row_bytes": st["embedding_row_bytes"],
        "weight_bytes_read_per_token_one_machine": st["weight_bytes_read_per_token"],
        "layer0_tensor_bytes_sum": sum(st["layer0_tensor_bytes"].values()),
    }
    geom["mean_layer_bytes_exact"] = (
        geom["mean_layer_bytes"] * geom["layers"] == geom["block_bytes"])
    geom["layer0_excess_over_mean"] = (
        geom["layer0_tensor_bytes_sum"] - geom["mean_layer_bytes"])

    shapes = []
    for shape, fn in (("layer-wise", layerwise), ("tensor-wise", tensorwise)):
        for m in MEMBER_COUNTS:
            for act in ACTIVATION_WIDTHS:
                t = dict(fn(geom, m, act))
                t["shape"] = shape
                t["members"] = m
                t["activation_width_bytes"] = act
                exch = int(t["bytes_per_exchange"])
                serial = int(t["serial_exchanges_per_step"])
                t["serial_exchanges_per_s"] = serial * FLOOR_TOKEN_RATE
                # R-11-017a gives a chain across a link its slot period plus its guard band
                # as the per-hop term. The serial exchanges of one step must fit the decode
                # period, so this is the largest slot period plus guard band the shape
                # admits at the floor's rate, before any compute is charged into the period.
                t["admissible_slot_plus_guard_s"] = 1 / (FLOOR_TOKEN_RATE * serial)
                t["frames"] = {}
                for p in FRAME_PAYLOADS:
                    per_exch = ceil_div(exch, p)
                    # Each link carries one exchange per serial position it takes part in.
                    # Layer-wise the step is one pass around the cycle, so a link carries
                    # exactly one exchange; tensor-wise every link takes part in every
                    # serial position.
                    per_link_dir = per_exch if shape == "layer-wise" else serial * per_exch
                    # The member's crypto core encrypts and tags every frame it sends and
                    # verifies every frame it receives (R-12-015d, R-15-228e). Under the
                    # declared cycle a member transmits on one outbound direction and
                    # receives on one inbound direction, whether those are two endpoints or
                    # the two directions of one full-duplex link at two members, so the
                    # charge is twice the per-direction frame count and not twice that again.
                    ops = 2 * per_link_dir
                    t["frames"][str(p)] = {
                        "frames_per_exchange": per_exch,
                        "frames_per_link_per_direction_per_step": per_link_dir,
                        "crypto_operations_per_member_per_step": ops,
                        "crypto_operations_per_member_per_s": ops * FLOOR_TOKEN_RATE,
                        "link_frames_per_s_per_direction": per_link_dir * FLOOR_TOKEN_RATE,
                    }
                t["per_member_second_class_read"] = residency(geom, shape, m)
                shapes.append(t)

    result = {
        "predicate": PREDICATE,
        "revision": revision,
        "source": {
            "static_file": static_path.replace("\\", "/").rsplit("/", 1)[-1],
            "model_file": st["file"],
            "quant": st["quant"],
            "static_predicate": st["predicate"],
        },
        "geometry": geom,
        "declared_parameters": {
            "member_counts": MEMBER_COUNTS,
            "activation_width_bytes": ACTIVATION_WIDTHS,
            "default_activation_width_bytes": DEFAULT_ACTIVATION_WIDTH,
            "frame_payload_bytes": FRAME_PAYLOADS,
            "default_frame_payload_bytes": DEFAULT_FRAME_PAYLOAD,
            "topology": "a cycle of point-to-point links, two endpoints per member above "
                        "two members and one at two members",
            "collective": "reduce-and-broadcast at two members, ring reduce-scatter plus "
                          "all-gather above two",
            "embedding_placement": "replicated under tensor-wise sharding, resident on the "
                                   "first member under layer-wise sharding",
            "owed_by": {
                "frame_payload_bytes": "Q23b, the ensemble link contract (R-15-228d fixes "
                                       "the frame size as a per-link composition constant "
                                       "and no landed artifact declares one)",
                "activation_width_bytes": "no entry declares the dtype or width of a "
                                          "shard-to-shard activation exchange",
                "topology": "R-02-003a carries each link's two endpoints in the attested "
                            "devicetree and declares no count per member",
                "collective": "no entry declares a collective algorithm; R-15-171a's "
                              "declared ring exchanges are R-15-223a's ring-buffer IPC "
                              "layout and not a ring topology",
            },
        },
        "floors": {
            "token_rate_per_s": FLOOR_TOKEN_RATE,
            "context_tokens": FLOOR_CONTEXT,
            "m_class_grant_bytes_per_s": GRANT_FLOOR_BYTES_PER_S,
            "aggregate_bytes_per_s": AGGREGATE_FLOOR_BYTES_PER_S,
            "owner": "R-18-004a(vii) for the rate and the context, R-18-004b for both "
                     "bandwidth floors, decimal gigabytes on inference-demand section 8's "
                     "declared convention",
        },
        "one_machine_reference": {
            "weight_bytes_per_token": st["weight_bytes_read_per_token"],
            "weight_stream_bytes_per_s": st["weight_bytes_read_per_token"] * FLOOR_TOKEN_RATE,
            "grant_floors": round(
                st["weight_bytes_read_per_token"] * FLOOR_TOKEN_RATE
                / GRANT_FLOOR_BYTES_PER_S, 3),
            "owner": "inference-demand section 8, restated here as the comparison the "
                     "sharded rows are read against and not as a new figure",
        },
        "undeclared_terms": {
            "encode_decode_per_frame": "R-15-228e makes it one entry in the endpoint's "
                                       "device row of the timing-annotated model; that "
                                       "model's table carries 27 core operation classes and "
                                       "no device row, and qualified is false in the shipped "
                                       "configuration, R-17-041 holding the magnitudes as an "
                                       "unauthored crown-jewel specification",
            "crypto_core_throughput": "R-12-015d bounds the link's line rate above by the "
                                      "crypto core's authenticated-encryption throughput as "
                                      "a composition constant; no artifact in this tree "
                                      "declares a value",
            "bank_grant": "R-15-247p makes the token rate a composition-time constant of the "
                          "bank grant; M6.8 has not run and R-15-108's exploration has no "
                          "cell",
            "slot_period_and_guard_band": "R-11-017a's fourth output, owed by Q23d over "
                                          "Q23b's constants",
        },
        "shapes": shapes,
    }
    json.dump(result, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
