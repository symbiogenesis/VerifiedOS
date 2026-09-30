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
    literals = {acvp.REVISION, *acvp.pinned().values()}
    sources = [*CAMPAIGNS.glob("*.py"), *(TOOLS / "vos").rglob("*.py"), *(TOOLS / "tests").glob("*.py")]
    owner = (TOOLS / "vos" / "acvp.py").resolve()
    ensure(any(path.name == "mlkem_vectors.py" for path in sources), "campaigns not scanned")
    restated = sorted(f"{path.relative_to(ROOT).as_posix()}: {literal[:8]}"
                      for path in sources if path.resolve() != owner
                      for literal in literals if literal in path.read_text(encoding="utf-8"))
    ensure(not restated, f"ACVP identities restated outside acvp.py: {restated}")


def consumers_read_the_owner() -> None:
    ensure(b.REVISION == acvp.REVISION and b.BASE == acvp.BASE and b.NOTICE_SHA == acvp.NOTICE_SHA,
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


def cases() -> list[Case]:
    return [Case("pinned identities are well formed", identities_are_well_formed),
            Case("no consumer restates an ACVP pin", no_consumer_restates_a_pin),
            Case("consumers take their identities from the owner", consumers_read_the_owner),
            Case("unpinned paths are refused before any download", unpinned_paths_are_refused),
            Case("downloads publish only verified bytes", downloads_publish_only_verified_bytes),
            Case("campaigns refuse a corrupt or unverified cache", campaigns_refuse_a_corrupt_cache)]
