import base64,gzip,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
W=Path('/root/build/lane-certirocq-hdval-adopt-20261020');T=Path('/mnt/c/Users/symbi/AppData/Local/Temp/verifiedos-certirocq-adopt-20261020-35a60dac42ab4682aad206bde2dee954');R=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS')
sys.path.insert(0,str(R/'tools'));from vos import compiler_component as cc
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
state=json.loads((W/'deferred.json').read_text());assert state['status']=='deferred' and not state['success']
build=json.loads((W/'candidate-build.json').read_text());assert build['success'] and sha(W/'candidate.full.lock')==build['full_export_sha256']
actual=(W/'candidate.full.lock').read_text();baseline=(W/'baseline.full.lock').read_text();expected=(W/'candidate.canonical.input.lock').read_text()
assert cc.matches_oracle_snapshot(actual,expected);assert cc.installed(actual)==cc.installed(baseline)
for entry in cc.installed(actual):
 name=entry.split('.',1)[0];assert cc.package_recipe(actual,name)==cc.package_recipe(expected,name)
 if name!='rocq-certirocq':assert cc.package_recipe(actual,name)==cc.package_recipe(baseline,name)
assert (R/'tools/opam/certirocq.lock').read_bytes()==(W/'baseline.lock').read_bytes()
env=os.environ.copy();env.update(OPAMROOT='/root/build/lane-deps-matrix-20261019/certirocq/opam-root',OPAMNO='1');env.pop('OPAMYES',None)
checks=[]
for full in (False,True):
 out=W/('baseline.deferred.full.lock' if full else 'baseline.deferred.lock');cmd=['/root/build/lane-deps-matrix-20261019/certirocq/bin/opam','switch','export','--switch=verifiedos-certirocq-0.9.1-ocaml-4.14.4']+(['--full','--freeze'] if full else [])+[str(out)]
 p=subprocess.run(cmd,cwd=Path.cwd(),env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True);(W/'logs'/('baseline-deferred-full.log' if full else 'baseline-deferred.log')).write_text(p.stdout+p.stderr);assert p.returncode==0;assert out.read_bytes()==(W/('baseline.full.lock' if full else 'baseline.lock')).read_bytes();checks.append(dict(argv=cmd,exit_code=p.returncode,sha256=sha(out)))
(W/'deferred-preservation.json').write_text(json.dumps(dict(success=True,production_snapshot_unchanged=True,installed_versions_unchanged=True,other_frozen_recipes_unchanged=True,baseline_checks=checks),indent=2)+'\n')
D=T/'portable-deferred';D.mkdir(exist_ok=False);members=[]
def select(member,p):
 data=p.read_bytes();kind='file'
 if len(data)>65536:data=gzip.compress(data,compresslevel=9,mtime=0);member+='.gz';kind='gzip'
 dest=D/member;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);members.append(dict(kind=kind,member=member,source=str(dest).replace('/mnt/c/','C:/')))
for name in ('deferred.json','deferred-preservation.json','candidate-build.json','build-steps.json','selection.json','baseline.lock','baseline.full.lock','baseline.deferred.lock','baseline.deferred.full.lock','candidate.input.lock','candidate.canonical.input.lock','candidate.pinned.input.lock','candidate.full.lock','candidate.lock','native-host.json','retained-path-aliases.json','package-commands.json','header-probe-source-rosters.json','installed-provenance-controls.json','source-all-files-preliminary.json'):select(name,W/name)
select('header-controls/result.json',W/'header-controls-qualified/result.json')
for name in ('result.json','steps.json','symbols.json','kernel-context.json'):select('consumers-baseline/'+name,W/'consumers-baseline'/name)
for name in ('native_build.py','native_resume.py','native_accept_normalized.py','native_accept_recovery.py','native_consumers.py','native_source_all.py','native_headers_qualified.py','native_identity_controls.py','native_host.py','native_defer.py','native_package_deferred.py'):select('drivers/'+name,T/name)
raw=[]
for root in (W/'logs',W/'package-commands',W/'deferred-package-commands',W/'header-controls',W/'header-controls-qualified',W/'consumers-baseline'):
 for p in sorted(root.rglob('*')):
  if p.is_file() and (p.suffix in ('.stdout','.stderr','.log','.out','.info') or (root.name=='consumers-baseline' and p.suffix=='.v')):
   data=p.read_bytes();raw.append(dict(source=str(p),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),base64=base64.b64encode(data).decode('ascii')))
for p in sorted(W.glob('*driver*.log')):
 data=p.read_bytes();raw.append(dict(source=str(p),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),base64=base64.b64encode(data).decode('ascii')))
p=T/'raw-deferred-output.json';p.write_text(json.dumps(dict(schema='verifiedos-raw-command-capture-v1',encoding='base64',records=raw),indent=2)+'\n');select('raw-command-output.json',p)
notes=dict(verdict='Production adoption deferred at user request; no candidate consumer, clean-import or complete-vector acceptance is claimed.',build='The resumed complete package closure build passed in about 66 minutes and produced candidate.full.lock. Its source recipe and all installed versions match the bounded input. The later same-version pin rebuild was interrupted by WSL, resumed, then stopped at user request.',source_roster='The complete original-file roster is preliminary, captured while the later build was active. It is not a final post-install candidate or replay source audit.',baseline='The consumer results belong to the unpatched qualified baseline only. The retained consumer driver was subsequently strengthened with baseline source/helper hash comparisons and whole-file source checks; these candidate/replay steps have not run.',headers='Qualified syntax controls use upstream compiler selection and original warning settings. The earlier setup probe omitted -Wno-everything; its diagnostics are retained without a passing claim.',pending=['Finish pinned candidate installation and actual frozen export','Candidate source/consumer/kernel/exact-assumption acceptance','Independent empty-root import, consumers, byte-identical full export','Complete-vector comparison and controls','Production lock and recipe adoption'])
p=T/'deferred-notes.json';p.write_text(json.dumps(notes,indent=2)+'\n');select('attempt-notes.json',p)
(T/'retain-deferred-members.json').write_text(json.dumps(members,indent=2)+'\n');print('Prepared',len(members),'portable evidence members; raw command records',len(raw));print('Successful closure import seconds',[s['seconds'] for s in build['steps'] if 'import' in s['name']])