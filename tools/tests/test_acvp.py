# SPDX-License-Identifier: Apache-2.0
"""One owner pins the ACVP inputs, and every consumer fetches only verified bytes."""

import hashlib
import importlib.util
import io
import re
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import acvp
from vos import boot_crypto as b

ROOT = TOOLS.parent
CAMPAIGNS = ROOT / "proofs" / "campaigns"
FIXTURE = "FIXTURE-family"
BYTES = b'{"testGroups": []}\n'

# The documents that restate the pinned revision or README digest by hand, beside a
# licence reading or a reproduction recipe, with every Markdown file under CAMPAIGNS.
# The completion log is not among them: its entries are frozen evidence of the
# revision a landing used.
DOCUMENTS = ("THIRD-PARTY.md", "firmware/crypto/README.md")
# Upstreams whose commits share those documents' paragraphs with ACVP's. An id after one
# of these names states that upstream's commit; an id after ACVP states ACVP's. A name
# missing here lets its id read as ACVP's, which fails loudly rather than passing.
OTHERS = ("OpenSSL", "XKCP", "HACL", "libjade", "libcrux", "Fiat-Crypto", "fiat-crypto")
_NAME = re.compile("|".join(("ACVP", *map(re.escape, OTHERS))))
_ID = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,64}(?![0-9A-Za-z])")
# A paragraph's wrapped lines are one unit, except that each table row or list item
# starts its own.
_ITEM = re.compile(r"[ \t]*(?:\||[-*+] |\d+\. )")


def _units(text: str) -> list[tuple[int, str]]:
    """Each paragraph, table row and list item with the number of its first line."""
    units: list[tuple[int, str]] = []
    lines: list[str] = []
    first = 0
    for number, line in enumerate([*text.splitlines(), ""], start=1):
        if lines and (not line.strip() or _ITEM.match(line)):
            units.append((first, "\n".join(lines)))
            lines = []
        if line.strip():
            first = first if lines else number
            lines.append(line)
    return units


def acvp_ids(text: str) -> list[tuple[int, str]]:
    """Each object id or SHA-256 a document states for ACVP, with its line: one whose
    nearest preceding upstream name within its paragraph, table row or list item is
    ACVP. An id in a unit that names ACVP after it, or not at all, is read by nothing
    here."""
    found: list[tuple[int, str]] = []
    for first, unit in _units(text):
        names = [(match.start(), match.group()) for match in _NAME.finditer(unit)]
        for match in _ID.finditer(unit):
            preceding = [name for start, name in names if start < match.start()]
            if preceding and preceding[-1] == "ACVP":
                found.append((first + unit.count("\n", 0, match.start()), match.group()))
    return found


def misstated(stated: list[tuple[str, str]]) -> list[str]:
    """The stated ids that are not the owner's: a SHA-256 must be a pinned file's digest
    and any shorter id must abbreviate or equal the pinned revision."""
    digests = set(acvp.pinned().values())
    return sorted(f"{where}: {value}" for where, value in stated
                  if not (value in digests if len(value) == 64 else acvp.REVISION.startswith(value)))


def _campaign(name: str) -> ModuleType:
    """A campaign script as a module, the way boot_crypto loads the ML-DSA one."""
    spec = importlib.util.spec_from_file_location(f"acvp_test_{name}", CAMPAIGNS / f"{name}.py")
    if spec is None or spec.loader is None:
        raise AssertionError(f"missing campaign {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _refused(action: Callable[[], object], reason: str) -> None:
    try:
        action()
    except ValueError as error:
        ensure(reason in str(error), f"refused for another reason: {error}")
        return
    raise AssertionError(f"accepted: {reason}")


def _served(body: bytes, urls: list[str]) -> Callable[..., io.BytesIO]:
    """urlopen's stand-in: records the address asked for and answers with `body`."""
    def urlopen(url: str, timeout: float) -> io.BytesIO:
        ensure(timeout > 0, "download without a timeout")
        urls.append(url)
        return io.BytesIO(body)
    return urlopen


def identities_are_well_formed() -> None:
    ensure(re.fullmatch(r"[0-9a-f]{40}", acvp.REVISION) is not None, "revision is not a full commit")
    ensure(acvp.BASE.endswith(f"/usnistgov/ACVP-Server/{acvp.REVISION}/"),
           "base does not address the pinned revision")
    pinned = acvp.pinned()
    ensure(len(pinned) == len(acvp.VECTORS) + 1 and pinned[acvp.NOTICE] == acvp.NOTICE_SHA,
           "notice or a family missing from the pinned set")
    ensure(all(re.fullmatch(r"[0-9a-f]{64}", value) for value in pinned.values()),
           "a pinned digest is not a SHA-256")
    ensure(len(set(pinned.values())) == len(pinned), "two pinned files share a digest")
    for family in acvp.VECTORS:
        ensure(acvp.url(acvp.vector_path(family)).startswith(acvp.BASE), f"{family} address")


def no_consumer_restates_a_pin() -> None:
    """No Python consumer writes an ACVP identity, and none outside the tests builds an
    ACVP address, so every download is one acvp.url names and acvp.fetch verifies."""
    identities = {acvp.REVISION, *acvp.pinned().values()}
    addresses = {"githubusercontent.com/usnistgov", "gen-val/json-files", "acvp.BASE"}
    consumers = [*CAMPAIGNS.glob("*.py"), *(TOOLS / "vos").rglob("*.py")]
    sources = [*consumers, *(TOOLS / "tests").glob("*.py")]
    owner = (TOOLS / "vos" / "acvp.py").resolve()
    ensure(any(path.name == "mlkem_vectors.py" for path in consumers), "campaigns not scanned")
    ensure(any(path.name == "boot_crypto_target.py" for path in consumers), "boot comparison not scanned")
    restated = sorted(f"{path.relative_to(ROOT).as_posix()}: {literal[:32]}"
                      for path in sources if path.resolve() != owner
                      for text in [path.read_text(encoding="utf-8")]
                      for literal in (identities | addresses if path in consumers else identities)
                      if literal in text)
    ensure(not restated, f"ACVP identities or addresses written outside acvp.py: {restated}")


def documents_restate_the_owners_pin() -> None:
    """Every ACVP revision or digest the documents restate is the one acvp.py pins, so a
    revision advance or a re-measured file names each document site left behind."""
    paths = [*(ROOT / name for name in DOCUMENTS), *sorted(CAMPAIGNS.glob("*.md"))]
    stated = [(f"{path.relative_to(ROOT).as_posix()}:{line}", value) for path in paths
              for line, value in acvp_ids(path.read_text(encoding="utf-8"))]
    ensure(bool(stated), "no document restates an ACVP id; the reading has stopped matching")
    wrong = misstated(stated)
    ensure(not wrong, f"documents restate ACVP ids acvp.py does not pin: {wrong}")


def attribution_reads_each_unit() -> None:
    """The reading attributes wrapped, tabled and quoted ids and leaves other upstreams'
    ids alone, and the comparison refuses a stale revision or an unpinned digest."""
    other = "a" * 64
    text = ("The NIST ACVP source is revision\n`0123abcd`; OpenSSL at `67b5686b` is not it.\n\n"
            f"| Row | HACL* at `504c2987` |\n| NIST ACVP vectors | `{acvp.REVISION[:8]}` and the "
            f"README `{acvp.NOTICE_SHA}` |\n- an item naming nothing: `deadbeef0`\n\n"
            f"> Source: NIST ACVP-Server\n> Revision: {acvp.REVISION}\n> Digest: {other}\n")
    found = acvp_ids(text)
    ensure(found == [(2, "0123abcd"), (5, acvp.REVISION[:8]), (5, acvp.NOTICE_SHA),
                     (9, acvp.REVISION), (10, other)], f"attribution misread its units: {found}")
    ensure(misstated([(f"fixture:{line}", value) for line, value in found])
           == sorted(["fixture:2: 0123abcd", f"fixture:10: {other}"]),
           "a stale revision or unpinned digest was accepted, or a pinned one refused")


def consumers_read_the_owner() -> None:
    ensure(b.REVISION == acvp.REVISION and b.NOTICE_SHA == acvp.NOTICE_SHA,
           "boot comparison carries its own revision or notice")
    ensure(all(digest == acvp.VECTORS[family] for family, digest in b.SOURCES.values())
           and set(b.SOURCES) == {"slh", "mldsa"}, "boot comparison carries its own digests")
    ensure("tools/vos/acvp.py" in b.EVIDENCE_FILES, "boot evidence snapshot omits the owner")
    dsa = _campaign("mldsa_vectors")
    ensure(dsa.REVISION == acvp.REVISION and not hasattr(dsa, "README_SHA"),
           "ML-DSA campaign carries its own identities")


def unpinned_paths_are_refused() -> None:
    with tempfile.TemporaryDirectory() as name:
        target = Path(name) / "other.json"
        urls: list[str] = []
        with patch.object(urllib.request, "urlopen", _served(BYTES, urls)):
            _refused(lambda: acvp.fetch("gen-val/json-files/other/internalProjection.json", target),
                     "not a pinned ACVP file")
        _refused(lambda: acvp.vector_path("ML-KEM-keyGen-FIPS999"), "not a pinned ACVP family")
        ensure(not urls and not target.exists(), "an unpinned file was fetched")


def downloads_publish_only_verified_bytes() -> None:
    relative = f"gen-val/json-files/{FIXTURE}/internalProjection.json"
    with (tempfile.TemporaryDirectory() as name,
          patch.dict(acvp.VECTORS, {FIXTURE: hashlib.sha256(BYTES).hexdigest()})):
        target = Path(name) / "cache" / "fixture.json"
        urls: list[str] = []
        with patch.object(urllib.request, "urlopen", _served(BYTES[:-2], urls)):
            _refused(lambda: acvp.fetch(relative, target), "downloaded SHA256 does not match")
        ensure(not target.exists() and next(target.parent.iterdir(), None) is None,
               "a truncated download was left in the cache")
        with patch.object(urllib.request, "urlopen", _served(BYTES, urls)):
            ensure(acvp.fetch(relative, target) == BYTES, "verified bytes not returned")
        ensure(urls == [acvp.BASE + relative] * 2, f"fetched another address: {urls}")
        with patch.object(urllib.request, "urlopen", _served(b"unused", urls)):
            ensure(acvp.fetch(relative, target) == BYTES and len(urls) == 2,
                   "a verified cache was downloaded again")
        target.write_bytes(BYTES.replace(b"[]", b"[1]"))
        _refused(lambda: acvp.fetch(relative, target), "cached download SHA256 does not match")
        _refused(lambda: acvp.read(relative, target), "is not the pinned")


def campaigns_refuse_a_corrupt_cache() -> None:
    """Each campaign's fetch path refuses cached bytes that are not the pinned ones."""
    kem, dsa = _campaign("mlkem_vectors"), _campaign("mldsa_vectors")
    with tempfile.TemporaryDirectory() as name:
        build = Path(name)
        urls: list[str] = []
        family = "ML-KEM-keyGen-FIPS203"
        cached = build / "vectors" / acvp.vector_path(family)
        cached.parent.mkdir(parents=True)
        cached.write_bytes(BYTES)
        (build / "ML-DSA-keyGen-FIPS204.json").write_bytes(BYTES)
        with patch.object(urllib.request, "urlopen", _served(BYTES, urls)):
            _refused(lambda: kem.download(build, acvp.vector_path(family)),
                     "cached download SHA256 does not match")
            _refused(lambda: dsa.source(build, "keyGen"), "cached download SHA256 does not match")
            _refused(lambda: kem.download(build, acvp.NOTICE), "downloaded SHA256 does not match")
            _refused(lambda: dsa.source(build, "sigGen"), "downloaded SHA256 does not match")
        ensure(urls == [acvp.url(acvp.NOTICE), acvp.url(acvp.vector_path("ML-DSA-sigGen-FIPS204"))],
               f"campaigns fetched another address: {urls}")
        ensure(not (build / "vectors" / acvp.NOTICE).exists()
               and not (build / "ML-DSA-sigGen-FIPS204.json").exists(),
               "a campaign cached unverified bytes")


def boot_comparison_fetches_through_the_owner() -> None:
    """Both boot comparisons take their ACVP inputs from boot_crypto.official, which the
    owner governs: its digest decides, and a family it does not pin is never fetched."""
    digest = hashlib.sha256(BYTES).hexdigest()
    with (tempfile.TemporaryDirectory() as name,
          patch.object(acvp, "NOTICE_SHA", digest),
          patch.dict(acvp.VECTORS, {FIXTURE: digest})):
        work = Path(name)
        urls: list[str] = []
        carried = "0" * 64
        with (patch.dict(b.SOURCES, {"slh": (FIXTURE, carried), "mldsa": (FIXTURE, carried)}),
              patch.object(urllib.request, "urlopen", _served(BYTES, urls))):
            ensure(b.official(work, "NIST-NOTICE.md") == {"slh": BYTES, "mldsa": BYTES},
                   "the owner's verified bytes were not returned")
        ensure(urls == [acvp.url(acvp.NOTICE), *[acvp.url(acvp.vector_path(FIXTURE))] * 2],
               f"the boot comparison fetched another address: {urls}")
        ensure((work / "NIST-NOTICE.md").read_bytes() == BYTES, "the notice was not retained")
        (work / "slh.json").unlink()
        with (patch.dict(b.SOURCES, {"slh": ("FIXTURE-unpinned", digest)}),
              patch.object(urllib.request, "urlopen", _served(BYTES, urls))):
            _refused(lambda: b.official(work, "NIST-NOTICE.md"), "not a pinned ACVP family")
        ensure(len(urls) == 3 and not (work / "slh.json").exists(), "an unpinned family was fetched")


def cases() -> list[Case]:
    return [Case("pinned identities are well formed", identities_are_well_formed),
            Case("no consumer restates an ACVP pin", no_consumer_restates_a_pin),
            Case("documents restate only the owner's pin", documents_restate_the_owners_pin),
            Case("document attribution reads each unit", attribution_reads_each_unit),
            Case("consumers take their identities from the owner", consumers_read_the_owner),
            Case("unpinned paths are refused before any download", unpinned_paths_are_refused),
            Case("downloads publish only verified bytes", downloads_publish_only_verified_bytes),
            Case("campaigns refuse a corrupt or unverified cache", campaigns_refuse_a_corrupt_cache),
            Case("the boot comparison fetches through the owner",
                 boot_comparison_fetches_through_the_owner)]
