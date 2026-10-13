"""Check immutable diagnostic bytes and regenerate the truncated profile view."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def observation(profile, log):
    decoder = json.JSONDecoder()
    position = profile.index("[") + 1
    end = position
    events = []
    error = None
    while True:
        while position < len(profile) and (
            profile[position].isspace() or profile[position] == ","
        ):
            position += 1
        if position >= len(profile):
            break
        try:
            event, end = decoder.raw_decode(profile, position)
        except json.JSONDecodeError as failure:
            error = {"position": failure.pos, "reason": failure.msg}
            break
        events.append(event)
        position = end
    stack = []
    pairs = []
    for index, event in enumerate(events):
        if event.get("ph") == "B":
            stack.append((index, event))
        elif event.get("ph") == "E" and stack:
            begin_index, begin = stack.pop()
            if begin["name"] != event["name"]:
                raise ValueError("event stack mismatch")
            pairs.append({
                "name": begin["name"],
                "constant": begin.get("args", {}).get("name"),
                "seconds": (event["ts"] - begin["ts"]) / 1000000,
                "begin_index": begin_index,
                "end_index": index,
            })
    return {
        "schema": "q39-truncated-profile-observation/1",
        "valid_complete_json": False,
        "complete_event_count": len(events),
        "decoded_prefix_characters": end,
        "decoder_error": error,
        "last_complete_event": events[-1],
        "unclosed_prefix_events": [
            {"index": index, "event": event} for index, event in stack
        ],
        "longest_completed_constant_events": sorted(
            [row for row in pairs if row["name"] == "check_constant"],
            key=lambda row: row["seconds"], reverse=True,
        )[:5],
        "last_log_line": log.splitlines()[-1],
        "limitation": "The channel buffer was not flushed on default SIGINT "
        "termination; omitted buffered events may include later begins and ends. "
        "An unclosed prefix event is not proof of current checker activity. No "
        "root cause, infinite loop, completed Parser check or Q39 acceptance is "
        "established.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-observation", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_bytes())
    decoded = {}
    for row in manifest["files"]:
        stored = (root / row["path"]).read_bytes()
        data = gzip.decompress(stored) if row["encoding"] == "gzip" else stored
        if (
            len(stored) != row["stored_bytes"]
            or hashlib.sha256(stored).hexdigest() != row["stored_sha256"]
            or len(data) != row["decoded_bytes"]
            or hashlib.sha256(data).hexdigest() != row["decoded_sha256"]
        ):
            raise ValueError("retained-byte mismatch: " + row["path"])
        decoded[row["path"]] = data
    profile = decoded["profile-fragment.log.gz"].decode("utf-8")
    try:
        json.loads(profile)
    except json.JSONDecodeError:
        pass
    else:
        raise ValueError("expected historical profile truncation")
    generated = observation(profile, decoded["parser.log.gz"].decode("utf-8"))
    if generated != json.loads(decoded["observation.json"]):
        raise ValueError("derived profile observation differs")
    operation = json.loads(decoded["operation.json"])
    bindings = json.loads(decoded["bindings.json.gz"])
    digest = hashlib.sha256(json.dumps(bindings, sort_keys=True).encode()).hexdigest()
    for side in ("input_before", "input_after"):
        if operation[side]["manifest_sha256"] != digest:
            raise ValueError("input digest population differs: " + side)
        if operation[side]["paths"] != len(bindings) or operation[side]["mismatches"]:
            raise ValueError("historical input population mismatch: " + side)
    if operation["profile_sha256"] != manifest["files"][0]["decoded_sha256"]:
        raise ValueError("operation profile binding differs")
    if operation["log_sha256"] != manifest["files"][1]["decoded_sha256"]:
        raise ValueError("operation log binding differs")
    if args.show_observation:
        print(json.dumps(generated, indent=2, sort_keys=True))
    else:
        print("PASS: retained bytes, input population and derived truncated view")


if __name__ == "__main__":
    main()
