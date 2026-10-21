import hashlib,json,shutil,subprocess,time
from pathlib import Path
W=Path('/root/build/lane-certirocq-hdval-adopt-20261020');out=W/'header-controls-qualified';out.mkdir(exist_ok=False)
src=W/'candidate-root/verifiedos-certirocq-0.9.1-ocaml-4.14.4/.opam-switch/sources/rocq-certirocq.0.9.1+9.1'
headers=Path('/root/.opam/verifiedos-certirocq-0.9.1-ocaml-5.4.1/lib/ocaml')
patch=Path('/mnt/c/Users/symbi/AppData/Local/Temp/verifiedos-certirocq-adopt-20261020-35a60dac42ab4682aad206bde2dee954/upstream-167.patch')
assert hashlib.sha256(patch.read_bytes()).hexdigest()=='f350152fd710608b912e9584ae6ef2a005fb8f7d2fc8b7b1e4b15911c9de109b'
original=out/'original';original.mkdir()
for part in ('runtime','bootstrap/certirocqc','bootstrap/certirocqchk'):shutil.copytree(src/part,original/part)
patched=out/'patched';shutil.copytree(original,patched)
p=subprocess.run(['patch','-p1','--batch','--fuzz=0','--input',str(patch)],cwd=patched,capture_output=True,text=True);(out/'patch.log').write_text(p.stdout+p.stderr);assert p.returncode==0
rows=[]
for edition in ('original','patched'):
 tree=out/edition
 for relative in ('bootstrap/certirocqc/certirocqc_wrapper.c','bootstrap/certirocqc/print.c','bootstrap/certirocqchk/certirocqchk_wrapper.c','bootstrap/certirocqchk/print.c'):
  source=tree/relative;cmd=[shutil.which('clang-11') or shutil.which('clang') or shutil.which('gcc'),'-fsyntax-only','-w','-Wno-everything','-I',str(source.parent),'-I',str(tree/'runtime'),'-I',str(headers),str(source)]
  before=time.monotonic();r=subprocess.run(cmd,cwd=source.parent,capture_output=True,text=True);log=out/(edition+'-'+relative.replace('/','_')+'.log');log.write_text(r.stdout+r.stderr)
  rows.append(dict(edition=edition,source=relative,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),argv=cmd,exit_code=r.returncode,seconds=time.monotonic()-before,log=str(log),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
  assert (r.returncode==0) is (edition=='patched'),log.read_text()[-4000:]
  if edition=='original':assert 'Hd_val' in r.stderr
manifest={str(p.relative_to(headers)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((headers/'caml').glob('*.h'))}
(out/'result.json').write_text(json.dumps(dict(success=True,ocaml_headers='5.4.1',scope='C syntax only; no OCaml5.4 producer qualification',header_sha256=manifest,steps=rows),indent=2)+'\n');print('all four original bridge units fail Hd_val; all four patched bridge units compile with OCaml5.4.1 headers')