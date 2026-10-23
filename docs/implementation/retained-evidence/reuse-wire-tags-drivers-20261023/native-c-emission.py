from pathlib import Path
import os,subprocess,tempfile,time,json,hashlib
root=Path('/root/build/lane-reuse-wire-20261023-tags');sail=Path('/root/.opam/verifiedos-sail-0.20.3-ocaml-5.4.1');rows=[];env=os.environ.copy();env.pop('SAIL_PLUGIN_DIR',None);env['PATH']=str(sail/'bin')+':'+env['PATH']
for name in ['nonrocq-before','nonrocq-after']:
 work=Path(tempfile.mkdtemp(prefix='vos-tags-c-'));argv=[str(sail/'bin/sail'),'-c','-o','bindings',str(root/'bindings.sail')];t=time.time();r=subprocess.run(argv,cwd=work,env=env,capture_output=True,text=True,timeout=90);(root/(name+'.log')).write_text(r.stdout+r.stderr);out=root/name
 for p in work.glob('bindings*'):
  if p.is_file():(out/p.name).write_bytes(p.read_bytes())
 rows.append({'name':name,'argv':argv,'cwd':str(work),'exit':r.returncode,'seconds':time.time()-t,'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}});print(name,r.returncode,rows[-1]['outputs'],r.stderr[-300:])
(root/'nonrocq-pair.json').write_text(json.dumps(rows,indent=2)+'\n')
print('Controls log bytes', (root/'TagControls-strict.log').stat().st_size)