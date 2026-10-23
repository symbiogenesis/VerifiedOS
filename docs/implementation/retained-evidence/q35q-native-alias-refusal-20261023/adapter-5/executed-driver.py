"""Original bounded diagnostic replay driver; no native acceptance beyond its recorded scope."""
import argparse,datetime,gc,hashlib,json,os,re,resource,runpy,shutil,signal,subprocess,sys,tempfile,time,traceback
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--intent',type=Path,required=True)
args=parser.parse_args()
root=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS/.worktrees/checklist-20261023-c')
lane=Path('/root/build/lane-checklist-20261023-c')
switch=Path('/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1')
original=lane/'census-14'
prior_readings=lane/'adapter-1'
out=lane/'adapter-5'
control_out=lane/'controls-5'

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

intent=json.loads(args.intent.read_text())
if intent['driver_sha256']!=sha(Path(__file__)):
    raise ValueError('scratch driver differs from prelaunch intent')
if intent['candidate']!=5 or intent['prior_active_seconds']!=1797.084094779 or intent['maximum_additional_active_seconds']!=1792.484066608:
    raise ValueError('fifth-candidate owner budget differs')
for path,expected_hash in intent['source_sha256'].items():
    if sha(Path(path))!=expected_hash:raise ValueError('source differs from prelaunch intent '+path)
out.mkdir(exist_ok=False)
sys.path.insert(0,str(root/'tools'))
helper=runpy.run_path(str(root/'tools/rocq-census/qualify.py'))
adapter=runpy.run_path(str(root/'tools/rocq-census/census.py'))
route=runpy.run_path(str(root/'tools/ci/sail_support_route.py'))
spec=route['control_spec'](root)
recipe=json.loads((root/'tools/opam/sail-support-qualification.json').read_text())
expected=['CensusControls']+['SailStdpp.'+name for name in recipe['support_modules']]
started=time.monotonic()
allowance=min(intent['maximum_additional_active_seconds'],3600-intent['prior_active_seconds'])
receipt={'schema':'verifiedos-native-census-focused-replay/1','candidate':5,'owner_revision':'9c6e9d604c5229beea7b3d4ae01ec58b18f0e6a2','revision':intent['revision'],'scope':'original native controls, exact30 full metadata graph replay, and separate3root adapter controls; no support-wide assumption/kernel gate','started_utc':datetime.datetime.now(datetime.UTC).isoformat(),'verdict':'pending','source_sha256':intent['source_sha256'],'driver_sha256_before':intent['driver_sha256'],'intent_sha256':sha(args.intent),'commands':[],'cuts':[],'budget':{'candidate':5,'maximum_candidates':5,'prior_active_seconds':intent['prior_active_seconds'],'maximum_additional_active_seconds':allowance,'maximum_cumulative_active_seconds':3600,'deadline_utc':(datetime.datetime.now(datetime.UTC)+datetime.timedelta(seconds=allowance)).isoformat()}}
metadata=classified=None
control_classified=None
raw_identities={}
readings_hashes={}
current_census_calls=0
reading_calls=0
capturing_control_positive=False


def memory():
    data=Path('/proc/self/status').read_text()
    rss=re.search(r'^VmRSS:\s+(\d+)',data,re.M)
    return {'rss_kib':int(rss.group(1)) if rss else None,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


def elapsed():return time.monotonic()-started


def remaining():return allowance-elapsed()


def progress(phase,**extra):
    row={'phase':phase,'utc':datetime.datetime.now(datetime.UTC).isoformat(),'elapsed_seconds':elapsed(),**memory(),**extra}
    receipt['phase']=phase
    with (out/'phase-events.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    checkpoint={**row,'verdict':receipt['verdict'],'budget':receipt['budget'],'commands':len(receipt['commands'])}
    (out/'checkpoint.json').write_text(json.dumps(checkpoint,indent=2)+'\n')
    print(json.dumps(row),flush=True)


def assert_budget():
    if remaining()<=20:raise TimeoutError('fifth-candidate active budget exhausted; final evidence window reserved')


def deadline(*unused):raise TimeoutError('fifth-candidate active budget exhausted; final evidence window reserved')


def snapshot_json(label,value):
    path=out/(label+'.json');path.write_text(json.dumps(value,indent=2)+'\n')
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)}


def native_maps(loaded):
    return {'installed':helper['population'](switch/'lib/coq'),'native_api':helper['api_population'](switch/'lib'),'loaded':helper['query_inputs'](loaded)}


def cut(label,loaded,expected_maps=None):
    assert_budget()
    maps=native_maps(loaded)
    receipt['cuts'].append({'label':label,'loaded':str(loaded),'identity':snapshot_json(label+'-maps',maps)})
    if expected_maps is not None and maps!=expected_maps:raise ValueError('native input population/bytes changed at '+label)
    return maps


def base_env(plugin_root=None):
    env=os.environ.copy()
    env['PATH']=str(switch/'bin')+os.pathsep+env.get('PATH','')
    for key in ('VOS_CENSUS_MODE','VOS_CENSUS_TARGETS','VOS_CENSUS_RESOLVE','VOS_CENSUS_RESOLVE_FILE','VOS_CENSUS_OUTPUT_FILE','VOS_CENSUS_PROGRESS_FILE'):
        env.pop(key,None)
    if plugin_root is not None:env['OCAMLPATH']=str(plugin_root)+os.pathsep+str(switch/'lib')+os.pathsep+env.get('OCAMLPATH','')
    return env


def native_common(loaded):
    return [str(switch/'bin/rocq'),'c','-boot','-R',str(switch/'lib/coq/theories'),'Corelib','-Q',str(switch/'lib/coq/user-contrib/Stdlib'),'Stdlib','-Q',str(loaded/'stdpp'),'stdpp','-R',str(loaded/'support'),'SailStdpp','-Q',str(loaded/'controls'),'','-q','-w','+default,-abstract-large-number','-set','Default Goal Selector=!','-disallow-sprop']


def command(label,argv,work,env,timeout):
    assert_budget()
    limit=min(timeout,remaining()-20)
    source_hashes={arg:sha(Path(arg)) for arg in argv if Path(arg).suffix in {'.v','.ml','.py'} and Path(arg).is_file()}
    record={'label':label,'argv':argv,'cwd':work,'timeout_seconds':limit,'source_sha256_before':source_hashes,'status':'pending','output_file_environment':env.get('VOS_CENSUS_OUTPUT_FILE')}
    receipt['commands'].append(record)
    path=out/f'command-{len(receipt["commands"]):03d}.json'
    path.write_text(json.dumps(record,indent=2)+'\n')
    progress('native-command',label=label)
    begin=time.monotonic()
    stdout=out/(label+'.stdout.log');stderr=out/(label+'.stderr.log')
    with stdout.open('wb') as output,stderr.open('wb') as errors:
        process=subprocess.Popen(argv,cwd=work,env=env,stdout=output,stderr=errors,start_new_session=True)
        record.update(pid=process.pid,process_group=process.pid,status='running')
        path.write_text(json.dumps(record,indent=2)+'\n')
        try:
            process.wait(timeout=limit)
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            record.update(status='refused',exit=process.returncode,elapsed_seconds=time.monotonic()-begin)
            path.write_text(json.dumps(record,indent=2)+'\n')
            raise
    record.update(status='complete',exit=process.returncode,elapsed_seconds=time.monotonic()-begin,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),source_sha256_after={p:sha(Path(p)) for p in source_hashes})
    path.write_text(json.dumps(record,indent=2)+'\n')
    if record['source_sha256_after']!=source_hashes:raise ValueError('executed source changed '+label)
    return process.returncode,stdout.read_text(),stderr.read_text()


def strict_load_output(loaded,targets):
    raw=loaded/'native-census.json'
    before=helper['output_identity'](raw)
    envelope=json.loads((loaded/'native-query.stdout.log').read_bytes(),object_pairs_hook=helper['unique_object'])
    if set(envelope)!={'schema','census_schema','path','bytes','blake2b_256'} or envelope['schema']!='verifiedos-native-census-output/1' or envelope['census_schema']!='verifiedos-sail-support-census/1' or envelope['path']!=str(raw) or type(envelope['bytes']) is not int or envelope['bytes']!=before['bytes'] or envelope['blake2b_256']!=before['blake2b_256']:
        raise ValueError('native output envelope/identity differs '+str(loaded))
    progress('strict-duplicate-free-parse',dataset=str(loaded),bytes=before['bytes'])
    with raw.open(encoding='utf-8') as stream:
        if helper['output_stat'](os.fstat(stream.fileno()))!=before['stat']:raise ValueError('native file replaced before parse')
        value=json.load(stream,object_pairs_hook=helper['unique_object'])
        if helper['output_stat'](os.fstat(stream.fileno()))!=before['stat']:raise ValueError('native file replaced during parse')
    if helper['output_identity'](raw)!=before:raise ValueError('native file changed across parse')
    if value.get('requested_roots')!=targets or [row['requested'] for row in value.get('roots',[])]!=targets:raise ValueError('exact native roots differ')
    requests=json.loads((loaded/'resolution-requests.json').read_bytes(),object_pairs_hook=helper['unique_object'])
    if value.get('resolution_requests')!=requests:raise ValueError('native request echo differs')
    raw_identities[str(raw)]=before
    return value


def count_graph(value):
    return {k:len(value[k]) for k in ('roots','contexts','modules','fields','declarations','abbreviations','module_descents','resolvers','resolution_requests','resolutions')}


def observed_call(name,original_call):
    def call(*positional,**keywords):
        progress('adapter-'+name+'-begin')
        begin=time.monotonic()
        try:return original_call(*positional,**keywords)
        finally:progress('adapter-'+name+'-end',call_elapsed_seconds=time.monotonic()-begin)
    return call


def install_observers():
    namespace=adapter['census'].__globals__
    for name in ('validate_schema','_native_semantics','_domains'):
        namespace[name]=observed_call(name,namespace[name])
    original_reading=namespace['_reading']
    def reading(*positional,**keywords):
        global reading_calls
        reading_calls+=1
        if reading_calls==1:progress('adapter-readings-and-graph-begin',census_call=current_census_calls)
        return original_reading(*positional,**keywords)
    namespace['_reading']=reading
    original_census=namespace['census']
    def census(*positional,**keywords):
        global current_census_calls,reading_calls,control_classified
        current_census_calls+=1;reading_calls=0
        progress('adapter-census-begin',census_call=current_census_calls)
        try:
            accepted=original_census(*positional,**keywords)
            if capturing_control_positive and control_classified is None:control_classified=accepted
            return accepted
        finally:progress('adapter-census-end',census_call=current_census_calls,reading_calls=reading_calls)
    namespace['census']=census
    adapter['census']=census


signal.signal(signal.SIGALRM,deadline)
signal.setitimer(signal.ITIMER_REAL,allowance-20)
original_maps=None;control_maps=None
try:
    progress('intent')
    shutil.copyfile(args.intent,out/'prelaunch-intent.json')
    shutil.copyfile(Path(__file__),out/'executed-driver.py')
    source_snapshots=[]
    for index,(path,h) in enumerate(intent['source_sha256'].items()):
        if sha(Path(path))!=h:raise ValueError('source changed before exact snapshot')
        target=out/'executed-source-inputs'/f'{index:02d}'/Path(path).name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        if sha(target)!=h:raise ValueError('source snapshot differs')
        source_snapshots.append({'source':path,'path':str(target),'sha256':h})
    receipt['source_snapshots']=source_snapshots
    original_maps=cut('initial-original',original)
    frozen=json.loads((original/'receipt.json').read_text())
    if original_maps['installed']!=frozen['installed_after'] or original_maps['native_api']!=frozen['native_api_after'] or original_maps['loaded']!=frozen['loaded_after']:raise ValueError('candidate14 native inputs drifted')
    native_sources=out/'native-controls';native_sources.mkdir()
    tiny_started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='vos-census-fifth-controls-') as work:
        receipt['tiny_native_cwd']=work
        for label,entry in spec['refusals'].items():
            query=native_sources/entry['source'];shutil.copyfile(root/'tools/rocq-census'/entry['source'],query)
            env=base_env(original);env.update(entry.get('environment',{}))
            code,stdout,stderr=command('native-'+label+'-refusal',[*native_common(original),'-o',str(query.with_suffix('.vo')),str(query)],work,env,max(1,60-(time.monotonic()-tiny_started)))
            if code==0 or entry['diagnostic'] not in stdout+stderr:raise ValueError('native '+label+' refusal differs from exact manifest')
        hidden=spec['hidden_assumptions'];query=native_sources/hidden['source'];shutil.copyfile(root/'tools/rocq-census'/hidden['source'],query)
        code,stdout,stderr=command('native-hidden-assumptions',[*native_common(original),'-o',str(query.with_suffix('.vo')),str(query)],work,base_env(),max(1,60-(time.monotonic()-tiny_started)))
        if code or stderr:raise ValueError('hidden-assumption native query failed or produced diagnostics')
        symbols=[{'name':entry['name'],'type':'control','claims':[],'assumptions':[]} for entry in hidden['symbols']]
        adapter['proofaudit'].assumptions(stdout,symbols)
        receipt['observed_hidden_assumptions']=symbols
        snapshot_json('observed-hidden-assumptions',symbols)
        progress('hidden-assumptions-observed',observed_names={s['name']:[a.split(' : ',1)[0] for a in s['assumptions']] for s in symbols})
        route['hidden_assumption_audit'](stdout,hidden['symbols'])
    cut('after-tiny-controls-original',original,original_maps)
    receipt['native_refusals']='passed';receipt['hidden_assumptions']='matched-exact-manifest'
    progress('retained78-reading-preflight')
    targets=json.loads((prior_readings/'reading-targets.json').read_text())
    original_reading_receipt=json.loads((prior_readings/'receipt.json').read_text())
    readings={}
    for index,(kind,target) in enumerate(targets):
        stem=prior_readings/f'Reading{index:03d}'
        query=stem.with_suffix('.v');stdout=stem.with_suffix('.stdout.log');stderr=stem.with_suffix('.stderr.log')
        recorded=original_reading_receipt['commands'][index]
        if recorded['kind']!=kind or recorded['target']!=target or recorded['exit']!=0 or recorded['source_sha256_after']!=sha(query) or stderr.read_bytes():raise ValueError('retained raw reading provenance differs')
        adapter['_reading'](stdout.read_text(),kind,target)
        readings[kind+':'+target]=stdout.read_text()
        for path in (query,stdout,stderr):readings_hashes[str(path)]=sha(path)
    receipt['full30_reading_targets']=len(targets)
    install_observers()
    metadata=strict_load_output(original,expected)
    receipt['full30_native_counts']=count_graph(metadata)
    searches={target:(original/f'native-search-{index:02d}.stdout.log').read_text() for index,target in enumerate(expected)}
    progress('full30-graph-replay')
    classified=adapter['census'](metadata,searches,readings,expected_modules=expected)
    receipt['full30_root_verdicts']={name:{'owned_symbols':len(value['symbols']),'alias_audits':len(value['alias_audits']),'interfaces':len(value['interfaces']),'aliases':len(value['aliases'])} for name,value in classified.items()}
    receipt['full30_graph_replay']='passed'
    metadata=classified=searches=readings=None;gc.collect()
    progress('full30-graph-released')
    cut('after-full30-original',original,original_maps)
    progress('separate3root-native-emission')
    helper_command=[sys.executable,str(root/'tools/rocq-census/qualify.py'),'--switch-root',str(switch),'--support-source',str(lane/'component29/source/coq-sail-0.20.3/src-stdpp'),'--stdpp-source','/root/build/fanout-retained/b9f62c68c7b9eb395be0/checklist-20261023-a/lane/stdpp','--component-receipt',str(lane/'component29/receipt.json'),'--out',str(control_out),'--targets',','.join(spec['targets']),'--census','--search','--query-timeout-seconds',str(max(1,min(600,int(remaining()-70))))]
    with tempfile.TemporaryDirectory(prefix='vos-census-fifth-helper-') as work:
        code,stdout,stderr=command('control-native-helper',helper_command,work,base_env(),remaining()-30)
    if code or stderr:raise ValueError('separate native control emission refused')
    helper_receipt=json.loads((control_out/'receipt.json').read_text())
    receipt['control_native_receipt']={'path':str(control_out/'receipt.json'),'sha256':sha(control_out/'receipt.json'),'verdict':helper_receipt.get('verdict')}
    if helper_receipt.get('verdict')!='native-census-provenance-only':raise ValueError('control native provenance did not complete')
    control_maps=cut('before-control-readings',control_out)
    metadata=strict_load_output(control_out,spec['targets'])
    receipt['control_native_counts']=count_graph(metadata)
    # Unqualified planning projection only. Whole schema/census/controls below remain mandatory.
    planned=[]
    for module in metadata['modules']:
        query=module['query'];kind,target=query['kind'],query['target']
        if kind not in ('module','module-type') or not isinstance(target,str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*",target) is None:raise ValueError('unsafe or unsupported native reading plan')
        if (kind,target) not in planned:planned.append((kind,target))
    snapshot_json('unqualified-control-reading-plan',planned)
    readings={}
    with tempfile.TemporaryDirectory(prefix='vos-census-fifth-readings-') as work:
        receipt['control_reading_native_cwd']=work
        for index,(kind,target) in enumerate(planned):
            query=out/f'ControlReading{index:03d}.v'
            query.write_text(''.join(f'Require {name}.\n' for name in spec['targets'])+'Set Printing All.\nSet Printing Universes.\nSet Printing Depth 1000000.\nSet Printing Width 1000000.\n'+f'Print Module {"Type " if kind=="module-type" else ""}{target}.\n')
            code,stdout,stderr=command(f'control-reading-{index:03d}',[*native_common(control_out),'-o',str(query.with_suffix('.vo')),str(query)],work,base_env(),180)
            if code or stderr:raise ValueError('native control reading failed '+target)
            readings[kind+':'+target]=stdout
    cut('after-control-readings',control_out,control_maps)
    searches={target:(control_out/f'native-search-{index:02d}.stdout.log').read_text() for index,target in enumerate(spec['targets'])}
    capturing_control_positive=True
    progress('full-native-adapter-controls')
    report=adapter['qualify_controls'](metadata,searches,readings)
    if control_classified is None:raise ValueError('control positive census was not observed')
    route['control_census_join'](control_classified,spec)
    receipt['control_report']=snapshot_json('control-adapter-verdicts',report)
    if len(report['refusals'])!=12:raise ValueError('exact twelve adapter refusal population differs')
    receipt['verdict']='focused-native-graph-and-controls-pass'
except BaseException as error:
    receipt['verdict']='refused';receipt['refusal']={'type':type(error).__name__,'message':str(error)}
    (out/'exception.log').write_text(traceback.format_exc())
    print(json.dumps({'first_refusal':receipt['refusal']}),flush=True)
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    metadata=classified=control_classified=None;gc.collect()
    receipt['driver_sha256_after']=sha(Path(__file__))
    receipt['sources_sha256_after']={p:sha(Path(p)) for p in intent['source_sha256']}
    receipt['sources_unchanged']=receipt['sources_sha256_after']==intent['source_sha256']
    receipt['driver_unchanged']=receipt['driver_sha256_after']==intent['driver_sha256']
    receipt['raw_after']={p:helper['output_identity'](Path(p)) for p in raw_identities}
    receipt['raw_unchanged']=receipt['raw_after']==raw_identities
    receipt['raw_before']=raw_identities
    receipt['readings_sha256']=readings_hashes
    receipt['readings_unchanged']=all(sha(Path(p))==h for p,h in readings_hashes.items())
    if original_maps is not None:
        final=native_maps(original);receipt['cuts'].append({'label':'final-original','identity':snapshot_json('final-original-maps',final)})
        receipt['original_native_inputs_unchanged']=final==original_maps
    if control_maps is not None:
        final=native_maps(control_out);receipt['cuts'].append({'label':'final-control','identity':snapshot_json('final-control-maps',final)})
        receipt['control_native_inputs_unchanged']=final==control_maps
    if not all(receipt.get(k,True) for k in ('sources_unchanged','driver_unchanged','raw_unchanged','readings_unchanged','original_native_inputs_unchanged','control_native_inputs_unchanged')):receipt['verdict']='identity-refused'
    receipt['elapsed_seconds']=elapsed();receipt['budget']['cumulative_active_seconds']=intent['prior_active_seconds']+elapsed()
    receipt['budget']['remaining_cumulative_seconds']=3600-receipt['budget']['cumulative_active_seconds']
    receipt['memory_final']=memory()
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    progress('finished',verdict=receipt['verdict'],refusal=receipt.get('refusal'))
    print(json.dumps({k:receipt.get(k) for k in ('verdict','refusal','elapsed_seconds','budget','observed_hidden_assumptions','full30_graph_replay','control_report','memory_final')}),flush=True)
    sys.exit(0 if receipt['verdict']=='focused-native-graph-and-controls-pass' else 1)
