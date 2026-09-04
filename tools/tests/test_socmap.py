# SPDX-License-Identifier: Apache-2.0
"""The SoC address map's emitter, and the three claims it makes about its input.

K-88 already decides that the tracked package is the bytes this emitter writes, so
what is worth pinning here is not the bytes but what the emitter *reads*, which is
the half a byte comparison cannot see: a generator that quietly stopped finding half
the map would agree with a tracked artifact that had quietly lost half the map.

Three claims, one per group of cases below.

**Apertures are found by shape and never by a list of names.** That is the whole
reason this generator exists rather than a hand-written package: the model's own
whole-map check is a list somebody maintains, and a window it gains joins that list
only when a row is added (K-94 is what holds the omission loud). A generator carrying
a list of names would be the same defect one language over, so a window added to a
composition must arrive in the package with no edit here, and a window switched off
must leave it.

**A composition this emitter cannot read is refused rather than half-emitted.** A map
emitted from a partial reading is a package that compiles and states a machine nobody
composed, which is worse than no package: the fail-closed ground the generated group
already states, met at the generator rather than at the rule.

**The window whose extent the composition does not state is carried as a base and
never given a size.** The revocation sidecar's extent is the model's rather than the
composition's, and a size invented here would be exactly the unowned derived fact
this repository refuses.
"""

import json

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos import socmap

# A composition carrying the least this emitter reads: one region and one window.
_MINIMAL: dict[str, object] = {
    "memory": {
        "physaddr_bits": 36,
        "dtb_address": {"len": 64, "value": "0x1000"},
        "regions": [
            {"base": {"len": 64, "value": "0x2000000"},
             "size": {"len": 64, "value": "0x10000000"},
             "attributes": {"mem_type": "IOMemory", "executable": False,
                            "readable": True, "writable": True}},
        ],
    },
    "platform": {
        "uart": {"supported": True, "base": 41943040, "size": 4096},
    },
}


def _written(config: object) -> str:
    """What the emitter writes from one composition, in a tree of its own."""
    with sandbox_tree({socmap.COMPOSITION: json.dumps(config)}) as root:
        return socmap.emit(root)


def _refused(config: object, why: str) -> None:
    """The emitter must refuse this composition and refuse it as its own error."""
    try:
        _written(config)
    except socmap.MapError:
        return
    raise AssertionError(why)


def _a_window_added_to_a_composition_arrives_with_no_edit() -> None:
    # The defect this case exists for: a generator carrying `("clint", "uart", ...)`
    # emits exactly what its author remembered, and a twelfth window is silently
    # outside the map the SoC top decodes over.
    before = _written(_MINIMAL)
    ensure("VosApUart = 0" in before,
           f"the one declared window must be in the map; got:\n{before}")
    ensure("VosApertureCount = 1" in before,
           f"a one-window composition must emit one aperture; got:\n{before}")

    grown = json.loads(json.dumps(_MINIMAL))
    grown["platform"]["mailbox"] = {"supported": True, "base": 44040192, "size": 4096}
    after = _written(grown)
    ensure("VosApMailbox = 1" in after,
           f"a window the composition gained must arrive with no edit here; got:\n"
           f"{after}")
    ensure("VosApertureCount = 2" in after,
           f"the count must follow the composition; got:\n{after}")


def _a_window_switched_off_leaves_the_map() -> None:
    # The map this package states is the map the composed die has, so an unsupported
    # window is not one: emitting it would put an address in the decoder for a device
    # this composition does not have.
    off = json.loads(json.dumps(_MINIMAL))
    off["platform"]["blkdev"] = {"supported": False, "base": 42991616, "size": 4096}
    text = _written(off)
    ensure("VosApBlkdev" not in text,
           f"a window a composition switches off must not be in the map; got:\n{text}")
    ensure("VosApertureCount = 1" in text,
           f"and must not be counted either; got:\n{text}")


def _the_unsized_window_is_carried_as_a_base_alone() -> None:
    unsized = json.loads(json.dumps(_MINIMAL))
    unsized["platform"]["revocation"] = {"supported": True, "base": 35651584,
                                         "interval_base": 2147516416,
                                         "interval_size": 32768}
    text = _written(unsized)
    ensure("VosApRevocationBase = 64'h0000_0000_0220_0000" in text,
           f"the window whose extent the composition does not state must carry its "
           f"base; got:\n{text}")
    ensure("VosApRevocation =" not in text,
           f"and must not join the table, which a decoder walks as extents; got:\n"
           f"{text}")
    ensure("VosApertureCount = 1" in text,
           f"nor be counted among the sized windows; got:\n{text}")


def _a_composition_this_cannot_read_is_refused() -> None:
    shapes: dict[str, object] = {
        "no memory at all": {"platform": _MINIMAL["platform"]},
        "no regions": {"memory": {"physaddr_bits": 36,
                                  "dtb_address": {"len": 64, "value": "0x1000"},
                                  "regions": []},
                       "platform": _MINIMAL["platform"]},
        "no platform": {"memory": _MINIMAL["memory"]},
        "no window at all": {"memory": _MINIMAL["memory"], "platform": {}},
    }
    for why, config in shapes.items():
        _refused(config, f"the emitter accepted a composition with {why}")

    for missing in ("mem_type", "executable", "readable", "writable"):
        broken = json.loads(json.dumps(_MINIMAL))
        del broken["memory"]["regions"][0]["attributes"][missing]
        _refused(broken, f"the emitter accepted a region stating no {missing}")

    unread = json.loads(json.dumps(_MINIMAL))
    unread["memory"]["regions"][0]["attributes"]["mem_type"] = "Scratchpad"
    _refused(unread, "the emitter accepted a region of a kind it does not read")

    literal = json.loads(json.dumps(_MINIMAL))
    literal["memory"]["dtb_address"] = {"len": 64, "value": "the ROM region's base"}
    _refused(literal, "the emitter accepted an address that is not a numeral")


def _the_tracked_map_is_this_checkout_s_composition() -> None:
    # The one case over the real tree: the emitter reads a live composition rather than
    # only the shapes above, and the boot ROM lands in the ROM region's upper half.
    root = corpus_mod.find_root()
    text = socmap.emit(root)
    ensure("VosApBootRom" in text and "VosApUart" in text and "VosApBlkdev" in text,
           f"the three windows R1c-i declared must be in the map; got:\n{text}")
    ensure("VosApRevocationBase" in text,
           "the revocation window must be carried as a base alone")
    ensure(text == (root / socmap.ARTIFACT).read_text(encoding="utf-8", newline=""),
           f"the tracked {socmap.ARTIFACT} is not what this emitter writes; "
           f"regenerate it with `{socmap.REPAIR}`")


def cases() -> list[Case]:
    return [
        Case("a-window-added-to-a-composition-arrives-with-no-edit",
             _a_window_added_to_a_composition_arrives_with_no_edit),
        Case("a-window-switched-off-leaves-the-map",
             _a_window_switched_off_leaves_the_map),
        Case("the-unsized-window-is-carried-as-a-base-alone",
             _the_unsized_window_is_carried_as_a_base_alone),
        Case("a-composition-this-cannot-read-is-refused",
             _a_composition_this_cannot_read_is_refused),
        Case("the-tracked-map-is-this-checkouts-composition",
             _the_tracked_map_is_this_checkout_s_composition),
    ]
