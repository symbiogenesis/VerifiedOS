from pathlib import Path
import hashlib,json,os,platform,shutil,subprocess
W=Path('/root/build/lane-certirocq-hdval-adopt-20261020'); tools={}
for name in ('clang','make','patch','python3'):
 path=Path(shutil.which(name)).resolve();r=subprocess.run([str(path),'--version'],cwd=Path.cwd(),stdin=subprocess.DEVNULL,capture_output=True,text=True)
 assert r.returncode==0;tools[name]=dict(path=str(path),sha256=hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),version=r.stdout+r.stderr)
record=dict(platform=dict(system=platform.system(),release=platform.release(),machine=platform.machine()),tools=tools,opam_jobs=4,makeflags='-j4',scope='Native build tool identity; no benchmark executed')
(W/'native-host.json').write_text(json.dumps(record,indent=2)+'\n');print('Recorded native build tool identities')