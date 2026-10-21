from pathlib import Path
import hashlib,json,sys
R=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS');sys.path.insert(0,str(R/'tools'))
from vos import compiler_component as cc
W=Path('/root/build/lane-certirocq-hdval-adopt-20261020');metadata=Path('/root/build/lane-deps-matrix-20261019/certirocq/opam-root/verifiedos-certirocq-0.9.1-ocaml-4.14.4/.opam-switch/packages/rocq-certirocq.0.9.1+9.1/opam');baseline=(W/'baseline.full.lock').read_text();patched=(W/'candidate.canonical.input.lock').read_text();installed=metadata.read_text()
checks=dict(versions_unchanged=cc.installed(baseline)==cc.installed(patched),original_matches_original=cc.matches_installed_oracle(installed,baseline,'0.9.1+9.1'),original_refused_under_approved_overlay=not cc.matches_installed_oracle(installed,patched,'0.9.1+9.1'))
assert all(checks.values()),checks
record=dict(checks=checks,success=True,installed_record=str(metadata),installed_record_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),helper_sha256=hashlib.sha256((R/'tools/vos/compiler_component.py').read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(baseline.encode()).hexdigest(),patched_recipe_sha256=hashlib.sha256(patched.encode()).hexdigest())
(W/'installed-provenance-controls.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(checks))