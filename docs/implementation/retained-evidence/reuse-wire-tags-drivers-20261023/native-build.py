from pathlib import Path
import hashlib,json,shutil,subprocess,tempfile,time,os
root=Path('/root/build/lane-reuse-wire-20261023-tags');repo=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS/.worktrees/reuse-wire-20261023-tags');switch=Path('/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1');old=Path('/root/build/fanout-retained/b238b053f81a8e38e616/triple-20261023-domains/lane')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
shutil.copytree(old/'private/lib/coq/user-contrib/stdpp',root/'stdpp',dirs_exist_ok=True)
(root/'dependency-inventory.json').write_text(json.dumps({str(p.relative_to(root/'stdpp')):sha(p) for p in sorted((root/'stdpp').rglob('*')) if p.is_file()},indent=2)+'\n')
plugins=root/'plugins';plugins.mkdir(exist_ok=True);shutil.copy2(old/'plugins/sail_plugin_coq.cmxs',plugins/'sail_plugin_coq.cmxs');assert sha(plugins/'sail_plugin_coq.cmxs')=='bfd722d424936648c244a2a2d42f4eca6d76a0b45fdbf439043844d5a9c28eae'
q=json.loads((repo/'tools/opam/sail-support-qualification.json').read_text());cwd=tempfile.mkdtemp(prefix='vos-tags-native-');stamp=time.time();rows=[]
flags=['-q','-boot','-R',str(switch/'lib/coq/theories'),'Corelib','-Q',str(switch/'lib/coq/user-contrib/Stdlib'),'Stdlib','-Q',str(root/'stdpp'),'stdpp']
for lane in ['baseline','candidate']:
 d=root/lane;maps=flags+['-R',str(d),'SailStdpp'];selected=[d/(m+'.v') for m in q['support_modules']]
 argv=[str(switch/'bin/rocq'),'dep','-sort']+maps+list(map(str,selected));r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True);(root/(lane+'-deps.log')).write_text(r.stdout+r.stderr);assert r.returncode==0
 order=[Path(x) for x in r.stdout.split() if Path(x) in selected];assert set(order)==set(selected) and len(order)==len(selected)
 for p in order:
  assert p.parent==d and p in selected
  argv=[str(switch/'bin/rocq'),'c']+maps+q['strict_flags'][1:]+[str(p)];t=time.time();r=subprocess.run(argv,cwd=cwd,capture_output=True,text=True);log=root/(lane+'-'+p.stem+'.log');log.write_text(r.stdout+r.stderr);rows.append({'lane':lane,'module':p.stem,'argv':argv,'cwd':cwd,'exit':r.returncode,'seconds':time.time()-t,'log':log.name,'sha256':sha(log)})
  if r.returncode or r.stderr:print('REFUSAL',lane,p.name,r.returncode,r.stderr[:1200]);break
 else:print(lane,'strict closure PASS',len(order))
 if rows[-1]['exit']:break
(root/'support-build.json').write_text(json.dumps(rows,indent=2)+'\n')
ck=json.loads((root/'checkpoint.json').read_text());ck['attempts'].append({'ordinal':2,'source_patch_sha256':sha(root/'canonical-tag-outcomes.patch'),'strategy':'Rebind missing bitvector dependencies to private preserved Q35o dependency objects; explicit selected closure only.','command':'selected 29-module strict baseline and candidate compile','exit':rows[-1]['exit'],'elapsed_seconds':time.time()-stamp,'diagnostic':rows[-1]['log']});(root/'checkpoint.json').write_text(json.dumps(ck,indent=2)+'\n')
# Actual emission: same unchanged retained reproducer and qualified private syntax plugin.
p=root/'bindings.sail';shutil.copy2(repo/'docs/implementation/retained-evidence/close3-q35p-20261013/bindings.sail.txt',p)
sail=Path('/root/.opam/verifiedos-sail-0.20.3-ocaml-5.4.1/bin/sail');env=os.environ.copy();env['SAIL_PLUGIN_DIR']=str(plugins);env['PATH']=str(sail.parent)+':'+env['PATH']
for lane in ['emitted','repeat']:
 d=root/lane;d.mkdir(exist_ok=True)
 argv=[str(sail),'-coq','-coq_lib_style','stdpp','-coq_alt_modules','SailStdpp.Base,SailStdpp.ConcurrencyInterfaceTypes,SailStdpp.ConcurrencyInterface,SailStdpp.ConcurrencyInterfaceBuiltins','-o',str(d/'bindings'),str(p)]
 t=time.time();r=subprocess.run(argv,cwd=cwd,env=env,capture_output=True,text=True);(root/(lane+'-emit.log')).write_text(r.stdout+r.stderr);print('EMIT',lane,r.returncode,r.stderr[:1200]);rows.append({'lane':lane,'argv':argv,'cwd':cwd,'exit':r.returncode,'seconds':time.time()-t})
(root/'emission.json').write_text(json.dumps(rows[-2:],indent=2)+'\n')