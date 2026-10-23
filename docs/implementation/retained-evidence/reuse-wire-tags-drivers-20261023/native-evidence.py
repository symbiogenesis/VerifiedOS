from pathlib import Path
import re,json,subprocess,tempfile,time,hashlib,os,shutil
root=Path('/root/build/lane-reuse-wire-20261023-tags');repo=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS/.worktrees/reuse-wire-20261023-tags');switch=Path('/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1');sail=Path('/root/.opam/verifiedos-sail-0.20.3-ocaml-5.4.1');cwd=tempfile.mkdtemp(prefix='vos-tags-evidence-');rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inv(s):return {str(p.relative_to(s)):sha(p) for p in sorted(s.rglob('*')) if p.is_file() and ('/lib/' in str(p) or '/bin/' in str(p))}
(root/'sail-installed-before.json').write_text(json.dumps(inv(sail),indent=2)+'\n')
row=json.loads((root/'probe-build.json').read_text())[-1];flags=row['argv'][2:-1]
def run(name,args):
 t=time.time();r=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=180);p=root/(name+'.log');p.write_text(r.stdout+r.stderr);rows.append({'name':name,'argv':args,'cwd':cwd,'exit':r.returncode,'seconds':time.time()-t,'log':p.name,'sha256':sha(p)});print(name,r.returncode,r.stderr[:400]);return r
names=['read_mem_','read_mem_ifetch_','read_mem_exclusive_','write_mem_','write_mem_exclusive_','__ReadRAM_Meta','__WriteRAM_Meta','addr_to_tag_addr','write_ram','read_ram']
text='Require bindings_types bindings TagInterpreter TagControls.\nSet Printing All.\nSet Printing Universes.\nSet Printing Depth 1000000.\nSet Printing Width 1000000.\n'
for n in ['bindings_types.Defs.read_tag_bool','bindings_types.Defs.write_tag_bool']+['bindings.'+x for x in names]:text+='Check @'+n+'.\nPrint '+n+'.\n'
p=root/'emitted/BindingReading.v';p.write_text(text);run('binding-reading',[str(switch/'bin/rocq'),'c']+flags+[str(p)])
text='Require TagControls.\n';queried=[]
for fn,prefix in [('TagInterpreter.v','TagControls.T.'),('TagControls.v','TagControls.')]:
 for n in re.findall(r'^\s*(?:Lemma|Theorem|Example)\s+(\w+)',(repo/'tools/sail-tag-outcomes'/fn).read_text(),re.M):
  queried.append(prefix+n);text+='Print Assumptions '+prefix+n+'.\n'
p=root/'emitted/AssumptionReading.v';p.write_text(text);run('assumptions',[str(switch/'bin/rocq'),'c']+flags+[str(p)]);(root/'assumption-targets.json').write_text(json.dumps(queried,indent=2)+'\n')
# Check only the two authored objects; dependencies are admitted, not claimed checked.
baseflags=flags[:flags.index('-w')];checkflags=[x for x in baseflags if x!='-q'];run('authored-kernel',[str(switch/'bin/rocqchk'),'-silent','-o']+checkflags+['-norec','TagInterpreter','-norec','TagControls'])
# Independent non-Rocq paired regeneration of the unchanged minimal Sail bytes.
env=os.environ.copy();env.pop('SAIL_PLUGIN_DIR',None);env['PATH']=str(sail/'bin')+':'+env['PATH']
for n in ['nonrocq-before','nonrocq-after']:
 out=root/n;out.mkdir(exist_ok=True);work=Path(tempfile.mkdtemp(prefix='vos-tags-c-'));args=[str(sail/'bin/sail'),'--c','-o','bindings',str(root/'bindings.sail')];t=time.time();r=subprocess.run(args,cwd=work,env=env,capture_output=True,text=True,timeout=90);(root/(n+'.log')).write_text(r.stdout+r.stderr)
 for p in work.glob('bindings*'):
  if p.is_file():shutil.copy2(p,out/p.name)
 rows.append({'name':n,'argv':args,'cwd':str(work),'exit':r.returncode,'seconds':time.time()-t,'outputs':{p.name:sha(p) for p in out.iterdir() if p.is_file()}});print(n,r.returncode,rows[-1]['outputs'],r.stderr[-200:])
(root/'native-evidence.json').write_text(json.dumps(rows,indent=2)+'\n')
after=inv(switch);before=json.loads((root/'installed-before.json').read_text());changed=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)];safter=inv(sail);sbefore=json.loads((root/'sail-installed-before.json').read_text());schanged=[k for k in sbefore.keys()|safter.keys() if sbefore.get(k)!=safter.get(k)];(root/'installed-after.json').write_text(json.dumps(after,indent=2)+'\n');(root/'sail-installed-after.json').write_text(json.dumps(safter,indent=2)+'\n');(root/'installed-comparison.json').write_text(json.dumps({'proof_paths':len(before),'proof_changed':changed,'sail_paths':len(sbefore),'sail_changed':schanged,'sail_scope':'before native evidence queries and paired C regeneration; earlier emissions are outside this before/after interval','unchanged':not(changed or schanged)},indent=2)+'\n');assert not(changed or schanged)