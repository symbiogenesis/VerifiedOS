import argparse,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
REPO=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS')
WORK=Path('/root/build/lane-certirocq-hdval-adopt-20261020')
BASE=Path('/root/build/lane-deps-matrix-20261019/certirocq')
OPAM=BASE/'bin/opam'
SWITCH='verifiedos-certirocq-0.9.1-ocaml-4.14.4'
NODE=Path('/root/build/lane-deps-tooling-20261019/toolchains/node-v26.12.0-linux-arm64/bin/node')
sys.path.insert(0,str(REPO/'tools'))
from vos import proofaudit

def sha(path):
 return hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
def save(path,data):
 path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
p=argparse.ArgumentParser(); p.add_argument('--label',required=True); p.add_argument('--root',required=True,type=Path); p.add_argument('--reference',type=Path); a=p.parse_args()
out=WORK/('consumers-'+a.label); out.mkdir(exist_ok=False)
env=os.environ.copy(); env.update(OPAMROOT=str(a.root),OPAMSWITCH=SWITCH,OPAMNO='1'); env.pop('OPAMYES',None)
steps=[]
def run(name,cmd,cwd=out,expected=0):
 start=time.monotonic(); print('START',name,flush=True)
 done=subprocess.run([str(x) for x in cmd],cwd=cwd,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 for kind in ('stdout','stderr'): (out/(name+'.'+kind)).write_text(getattr(done,kind))
 steps.append(dict(name=name,argv=[str(x) for x in cmd],cwd=str(cwd),exit_code=done.returncode,expected=expected,seconds=time.monotonic()-start,stdout_sha256=sha(out/(name+'.stdout')),stderr_sha256=sha(out/(name+'.stderr'))));save(out/'steps.json',steps)
 if done.returncode!=expected: raise RuntimeError(name+': '+done.stderr[-4000:]+done.stdout[-2000:])
 print('END',name,flush=True);return done
if a.reference:run('whole-source-boundary',['/usr/bin/python3',Path(__file__).with_name('native_source_all.py'),'--root',a.root,'--out',out/'source-boundary-all.json'])
prefix=Path(run('prefix',[OPAM,'var','prefix','--switch='+SWITCH]).stdout.strip())
coqc=prefix/'bin/coqc'; checker=prefix/'bin/coqchk'
assert sha(NODE)=='eb9c23a331c876ff7eeb7fd08b5c215da294bc18dc3a066d526254357f0f6942'
version=run('versions',[OPAM,'exec','--switch='+SWITCH,'--',coqc,'--version']).stdout
assert 'version 9.1.1' in version and 'OCaml 4.14.4' in version
sources={'demo.v':REPO/'tools/wasm-oracle/demo.v','EndpointIPC.v':REPO/'proofs/EndpointIPC.v','ipc_oracle.v':REPO/'tools/wasm-oracle/ipc_oracle.v','run_demo.mjs':REPO/'tools/wasm-oracle/run_demo.mjs'}
source_ids={str(v.relative_to(REPO)):sha(v) for v in sources.values()}
if a.reference:
 baseline_identity=json.loads((a.reference/'result.json').read_text());assert baseline_identity['success']
 assert source_ids==baseline_identity['source_sha256'],'consumer source bytes differ from baseline'
 assert sha(REPO/'tools/vos/proofaudit.py')==baseline_identity['audit_helper_sha256'],'assumption audit helper changed from baseline'
pos=out/'positive'; neg=out/'negative';pos.mkdir();neg.mkdir()
for name,source in sources.items():shutil.copyfile(source,pos/name)
for name in ('EndpointIPC.v','ipc_oracle.v','run_demo.mjs'):shutil.copyfile(pos/name,neg/name)
t=(neg/'ipc_oracle.v').read_text();assert t.count('(upto 31).')==1;(neg/'ipc_oracle.v').write_text(t.replace('(upto 31).','(upto 32).'))
def compile(name,stage,stem):return run(name,[OPAM,'exec','--switch='+SWITCH,'--',coqc,stem+'.v'],cwd=stage)
for stem in ('demo','EndpointIPC','ipc_oracle'):
 result=compile('positive-'+stem,pos,stem)
 if stem=='ipc_oracle':assert re.search(r'=\s*84\s*: nat',result.stdout) and re.search(r'=\s*true\s*: bool',result.stdout)
for stem in ('demo.oracle_demo','ipc_oracle.ipc_oracle'):
 result=run('wasm-'+stem,[NODE,'--stack-size=10000000','run_demo.mjs',stem+'.wasm'],cwd=pos);assert result.stdout.strip()=='true'
(pos/'DemoKernel.v').write_text('Require demo.\nGoal demo.oracle_demo = true. Proof. reflexivity. Qed.\n')
compile('demo-kernel',pos,'DemoKernel')
for stem in ('EndpointIPC','ipc_oracle'):
 result=compile('negative-'+stem,neg,stem)
 if stem=='ipc_oracle':assert re.search(r'=\s*false\s*: bool',result.stdout)
result=run('wasm-negative',[NODE,'--stack-size=10000000','run_demo.mjs','ipc_oracle.ipc_oracle.wasm'],cwd=neg,expected=1);assert result.stdout.strip()=='false'
def kernel_context91(summary):
 lines=[line.rstrip() for line in summary.splitlines() if line.strip()]
 if lines[:1]==['[WARNING] Running as root is not recommended']:lines=lines[1:]
 assert tuple(lines[:2])==proofaudit.KERNEL_CONTEXT
 sections=[]
 for line in lines[2:]:
  if line.startswith('* ') and ':' in line:
   key,_,value=line[2:].partition(':');sections.append([key,value.strip(),[]])
  elif line[:1].isspace() and sections and not sections[-1][1]:sections[-1][2].append(line.strip())
  else:raise RuntimeError('unrecognized kernel context line: '+line)
 assert [row[0] for row in sections]==['Theory','Theory','Axioms',*proofaudit.KERNEL_UNSAFE]
 assert tuple(row[1] for row in sections[:2])==proofaudit.KERNEL_THEORY
 assert all(row[1]=='<none>' and not row[2] for row in sections[3:])
 _,value,names=sections[2];assert value in ('','<none>') and ((value=='<none>')!=bool(names))
 assert len(names)==len(set(names)) and all(proofaudit.QUALIFIED.fullmatch(n) for n in names)
 sections[2][2]=sorted(names)
 return sections
all_symbols={}
for stem in ('demo','EndpointIPC','ipc_oracle'):
 query=pos/(stem+'Inventory.v');query.write_text(proofaudit.inventory_query(stem))
 result=compile('inventory-'+stem,pos,query.stem)
 symbols=proofaudit.inventory(result.stdout,stem);assert symbols
 query=pos/(stem+'Assumptions.v');query.write_text(proofaudit.assumption_query(stem,symbols))
 result=compile('assumptions-'+stem,pos,query.stem)
 proofaudit.assumptions(result.stdout,symbols)
 all_symbols[stem]=symbols
save(out/'symbols.json',all_symbols)
products={str(p.relative_to(out)):sha(p) for stage in (pos,neg) for p in sorted(stage.iterdir()) if p.suffix in ('.vo','.wasm')}
k=run('recursive-kernel',[OPAM,'exec','--switch='+SWITCH,'--',checker,'-silent','-o','-Q','.','','demo','EndpointIPC','ipc_oracle'],cwd=pos)
assert products=={str(p.relative_to(out)):sha(p) for stage in (pos,neg) for p in sorted(stage.iterdir()) if p.suffix in ('.vo','.wasm')},'consumer artifacts changed during recursive check'
# Rocq9.1 reports these sections; preserve original output and compare exact summary.
summary=k.stderr.strip();assert 'CONTEXT SUMMARY' in summary
context=kernel_context91(summary);save(out/'kernel-context.json',context)
if a.reference:
 reference=json.loads((a.reference/'symbols.json').read_text());assert all_symbols==reference,'consumer symbols/types/assumptions changed'
 assert context==kernel_context91((a.reference/'recursive-kernel.stderr').read_text()),'recursive kernel environment summary changed'
assert source_ids=={str(v.relative_to(REPO)):sha(v) for v in sources.values()}
identity=dict(artifact_sha256=products,root=str(a.root),prefix=str(prefix),switch=SWITCH,source_sha256=source_ids,tool_sha256={str(x):sha(x) for x in (coqc,checker,NODE,OPAM)},audit_helper_sha256=sha(REPO/'tools/vos/proofaudit.py'),symbols_per_module={k:len(v) for k,v in all_symbols.items()},exact_reference=str(a.reference) if a.reference else None,success=True,steps=steps)
save(out/'result.json',identity);print('CONSUMERS PASSED',a.label,flush=True)