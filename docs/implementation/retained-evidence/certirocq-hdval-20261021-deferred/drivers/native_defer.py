from pathlib import Path
import hashlib,json,os,signal,subprocess,time
W=Path('/root/build/lane-certirocq-hdval-adopt-20261020')
def cmd(pid):
 try:return Path('/proc/'+str(pid)+'/cmdline').read_bytes()
 except FileNotFoundError:return b''
assert b'native_accept_recovery.py' in cmd(436)
os.kill(436,signal.SIGSTOP)
if b'candidate.pinned.input.lock' in cmd(437):os.kill(437,signal.SIGSTOP)
processes={}
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  pid=int(p.name);stat=(p/'stat').read_text().rsplit(')',1)[1].split();processes[pid]=dict(ppid=int(stat[1]),pgid=int(stat[2]),command=cmd(pid).replace(b'\0',b' ').decode(errors='replace'))
 except (FileNotFoundError,ProcessLookupError):pass
def owned(pid):
 seen=set()
 while pid in processes and pid not in seen:
  if pid==436:return True
  seen.add(pid);pid=processes[pid]['ppid']
 return False
owned_processes={p:r for p,r in processes.items() if owned(p)}
assert owned_processes and 436 in owned_processes
groups={r['pgid'] for r in owned_processes.values()}
assert all(p in owned_processes for p,r in processes.items() if r['pgid'] in groups)
# Keep currently open command outputs, including files opam may already have unlinked.
out=W/'deferred-package-commands';out.mkdir(exist_ok=False);rows=[]
for fd in Path('/proc/698/fd').iterdir():
 try:
  target=os.readlink(fd);base=target.removesuffix(' (deleted)');p=Path(base)
  if str(p).startswith(str(W/'candidate-root/log')+'/') and p.suffix in ('.out','.info'):
   data=fd.read_bytes();dest=out/p.name;dest.write_bytes(data);rows.append(dict(source=target,copy=str(dest),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
 except (FileNotFoundError,OSError):pass
for group in groups:
 try:os.killpg(group,signal.SIGTERM);os.killpg(group,signal.SIGCONT)
 except ProcessLookupError:pass
time.sleep(2)
for pid,expected in ((698,b'native_pinned_logs.py'),(699,b'native_replay_logs.py')):
 if expected in cmd(pid):os.kill(pid,signal.SIGTERM)
# A stopped attempt is not an acceptance result.
r=dict(status='deferred',reason='User requested finishing the session and deferring the long qualification on 2026-10-21.',success=False,completed_closure_build=json.loads((W/'candidate-build.json').read_text())['success'],candidate_full_export_sha256=hashlib.sha256((W/'candidate.full.lock').read_bytes()).hexdigest(),production_snapshot_changed=False,candidate_consumers_run=False,clean_replay_run=False,complete_vector_run=False,owned_processes=owned_processes,retained_package_logs=rows)
(W/'deferred.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print('Stopped owned qualification process tree; preserved',len(rows),'command logs')
print(subprocess.run(['pgrep','-af','native_accept|native_pinned_logs|native_replay_logs|rocqworker'],capture_output=True,text=True).stdout)