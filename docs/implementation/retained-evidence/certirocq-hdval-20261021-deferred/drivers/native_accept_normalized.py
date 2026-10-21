import hashlib,json,os,shutil,subprocess,sys,tarfile,time
from pathlib import Path
WORK=Path('/root/build/lane-certirocq-hdval-adopt-20261020')
BASE=Path('/root/build/lane-deps-matrix-20261019/certirocq')
REPO=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS')
TEMP=Path('/mnt/c/Users/symbi/AppData/Local/Temp/verifiedos-certirocq-adopt-20261020-35a60dac42ab4682aad206bde2dee954')
OPAM=BASE/'bin/opam';SWITCH='verifiedos-certirocq-0.9.1-ocaml-4.14.4'
sys.path.insert(0,str(REPO/'tools'))
from vos import compiler_component as cc
STEPS=[];ROOT=WORK/'candidate-root'; env=os.environ.copy();env.update(OPAMROOT=str(ROOT),OPAMJOBS='4',OPAMKEEPBUILDDIR='true',MAKEFLAGS='-j4',NODE_TOOLCHAIN_ROOT='/root/build/lane-deps-tooling-20261019/toolchains');env.pop('OPAMYES',None);env.pop('OPAMNO',None);env.pop('OPAMSWITCH',None);env['PATH']=str(OPAM.parent)+os.pathsep+env['PATH']
def sha(p,kind='sha256'):return hashlib.file_digest(p.open('rb'),kind).hexdigest()
def save(name,x):(WORK/name).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def run(name,args,environment=None,cwd=WORK):
 print('START',name,flush=True);before=time.monotonic();log=WORK/'logs'/(name+'.log')
 with log.open('w') as stream:done=subprocess.run([str(x) for x in args],cwd=cwd,env=environment or env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
 STEPS.append(dict(name=name,argv=[str(x) for x in args],exit_code=done.returncode,seconds=time.monotonic()-before,log=str(log),log_sha256=sha(log)));save('acceptance-steps.json',STEPS);print('END',name,done.returncode,flush=True)
 if done.returncode:raise RuntimeError(name+' '+log.read_text()[-6000:])
print('Waiting for candidate closure',flush=True)
while not (WORK/'candidate-build.json').exists():time.sleep(5)
assert json.loads((WORK/'candidate-build.json').read_text())['success']
expected=(WORK/'candidate.canonical.input.lock').read_text();actual=(WORK/'candidate.full.lock').read_text();assert cc.matches_oracle_snapshot(actual,expected),'candidate import dropped the header patch'
for entry in cc.installed(actual):
 name=entry.split('.',1)[0];assert cc.package_recipe(actual,name)==cc.package_recipe(expected,name),'other package metadata changed: '+name
run('persist-source-pin',[OPAM,'switch','import','--switch='+SWITCH,WORK/'candidate.pinned.input.lock','-y','-j4'])
run('final-invariant',[OPAM,'switch','set-invariant','--switch='+SWITCH,'ocaml-base-compiler.4.14.4','-y'])
run('final-export',[OPAM,'switch','export','--switch='+SWITCH,'--full','--freeze',WORK/'candidate.final.lock'])
final=(WORK/'candidate.final.lock').read_text();assert cc.matches_oracle_snapshot(final,expected);assert 'pinned: ["rocq-certirocq.0.9.1+9.1"]' in final
# Prove the selected patch targets only the declared four original source files.
archive_sha='9ef925f78e399c6d8a6bf8f78023157786eccc59ea4673c06a09317cb391310e95d29b8d47e0524d99b09753c7436fcf05954ec74c247dff959fc7193ea87d5f'
archives=[p for p in (ROOT/'download-cache').rglob('*') if p.is_file() and p.name==archive_sha]
assert len(archives)==1,archives
archive=archives[0];assert sha(archive,'sha512')==archive_sha
source=WORK/'source-boundary';source.mkdir(exist_ok=False)
with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
source=next(source.iterdir()); originals={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
patch=TEMP/'upstream-167.patch';assert sha(patch)=='f350152fd710608b912e9584ae6ef2a005fb8f7d2fc8b7b1e4b15911c9de109b'
run('exact-patch',[shutil.which('patch'),'-p1','--fuzz=0','--batch','--input',patch],cwd=source)
changed={n for n,h in originals.items() if sha(source/n)!=h}
assert changed=={'bootstrap/certirocqc/certirocqc_wrapper.c','bootstrap/certirocqc/print.c','bootstrap/certirocqchk/certirocqchk_wrapper.c','bootstrap/certirocqchk/print.c'},changed
built=ROOT/SWITCH/'.opam-switch/build/rocq-certirocq.0.9.1+9.1'
assert built.is_dir()
source_roster={}
for name in originals:
 if name.endswith(('.v','.ml','.mli','.c','.h','.S')):
  assert (built/name).is_file(),name
  assert sha(built/name)==sha(source/name),'unexpected authored source change: '+name
  source_roster[name]=sha(built/name)
bootstraps={str(p.relative_to(built)):sha(p) for p in (built/'bootstrap').glob('*/*.cmxs')}
assert len(bootstraps)==2,bootstraps
save('source-boundary.json',dict(archive_sha512=archive_sha,patch_sha256=sha(patch),changed=sorted(changed),source_roster=source_roster,bootstrap_plugin_sha256=bootstraps,success=True))
run('candidate-consumers',['/usr/bin/python3',TEMP/'native_consumers.py','--label','candidate','--root',ROOT,'--reference',WORK/'consumers-baseline'])
# Replay the actual successful export in a second empty private root.
replay=WORK/'replay-root';assert not replay.exists();re=env|{'OPAMROOT':str(replay)}
run('replay-init',[OPAM,'init','--bare','--no-setup','--no-opamrc','-y','default','https://opam.ocaml.org'],re)
run('replay-repository',[OPAM,'repository','add','rocq-released','https://rocq-prover.org/opam/released','--dont-select','-y'],re)
shutil.copytree(ROOT/'download-cache',replay/'download-cache',dirs_exist_ok=True)
run('replay-create',[OPAM,'switch','create',SWITCH,'--empty','--no-switch','--repos=rocq-released,default','-y'],re)
run('replay-import',[OPAM,'switch','import','--switch='+SWITCH,WORK/'candidate.final.lock','-y','-j4'],re)
run('replay-invariant',[OPAM,'switch','set-invariant','--switch='+SWITCH,'ocaml-base-compiler.4.14.4','-y'],re)
run('replay-export',[OPAM,'switch','export','--switch='+SWITCH,'--full','--freeze',WORK/'replay.final.lock'],re)
assert (WORK/'replay.final.lock').read_bytes()==(WORK/'candidate.final.lock').read_bytes(),'full frozen re-export differs'
run('replay-consumers',['/usr/bin/python3',TEMP/'native_consumers.py','--label','replay','--root',replay,'--reference',WORK/'consumers-baseline'],re)
# Complete-vector qualification of the patched producer; this is a focused consumer check.
run('component-vector',['/usr/bin/python3','-B',REPO/'tools/wasm-oracle/compare_component.py','--compiler','/root/build/lane-deps-upstream-20261019/contained/compiler/ccomp','--compiler-config','/root/build/lane-deps-integration-20261019/component-compcert.ini','--model-snapshot','/root/build/lane-deps-integration-20261019/model-snapshot','--out',WORK/'component-vector','--oracle-snapshot',WORK/'candidate.final.lock'])
# Baseline export unchanged after all read-only accesses.
be=env|{'OPAMROOT':str(BASE/'opam-root'),'OPAMNO':'1'}
run('baseline-final-export',[OPAM,'switch','export','--switch='+SWITCH,WORK/'baseline.final.lock'],be)
assert (WORK/'baseline.final.lock').read_bytes()==(WORK/'baseline.lock').read_bytes()
save('acceptance.json',dict(success=True,candidate_full_sha256=sha(WORK/'candidate.final.lock'),replay_full_sha256=sha(WORK/'replay.final.lock'),baseline_unchanged=True,source_boundary_sha256=sha(WORK/'source-boundary.json'),steps=STEPS))
print('ALL NATIVE ACCEPTANCE PASSED',flush=True)