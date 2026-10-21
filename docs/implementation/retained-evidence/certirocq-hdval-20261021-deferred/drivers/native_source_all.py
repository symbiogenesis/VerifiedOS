import argparse,hashlib,json,tarfile
from pathlib import Path
W=Path('/root/build/lane-certirocq-hdval-adopt-20261020')
p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
archive_sha='9ef925f78e399c6d8a6bf8f78023157786eccc59ea4673c06a09317cb391310e95d29b8d47e0524d99b09753c7436fcf05954ec74c247dff959fc7193ea87d5f'
archive=next((a.root/'download-cache').rglob(archive_sha)); assert hashlib.file_digest(archive.open('rb'),'sha512').hexdigest()==archive_sha
boundary=json.loads((W/'source-boundary.json').read_text());assert boundary['success']
expected=set(boundary['changed']);assert len(expected)==4
built=a.root/'verifiedos-certirocq-0.9.1-ocaml-4.14.4/.opam-switch/build/rocq-certirocq.0.9.1+9.1';rows={};different=[]
with tarfile.open(archive) as tar:
 for m in tar:
  name='/'.join(m.name.split('/')[1:])
  if not name:continue
  if m.isdir():continue
  assert m.isfile(),('unexpected archive member',name,m.type)
  orig=hashlib.sha256(tar.extractfile(m).read()).hexdigest();member=built/name;assert member.is_file() and not member.is_symlink(),('missing or linked original',name)
  now=hashlib.file_digest(member.open('rb'),'sha256').hexdigest();rows[name]=dict(archive_sha256=orig,build_sha256=now)
  if now!=orig:different.append(name)
  assert now==(boundary['source_roster'][name] if name in expected else orig),('unexpected source bytes',name)
assert set(different)==expected
r=dict(success=True,archive_sha512=archive_sha,source_boundary_sha256=hashlib.sha256((W/'source-boundary.json').read_bytes()).hexdigest(),root=str(a.root),files=rows,different=sorted(different))
a.out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print('ALL ORIGINAL SOURCE FILES MATCH',len(rows),'except exact four-file backport')