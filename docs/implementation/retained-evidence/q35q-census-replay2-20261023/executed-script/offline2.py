import datetime,gc,json,os,resource,runpy,signal,sys,time,traceback
from pathlib import Path
root=Path('/mnt/c/Users/symbi/source/repos/VerifiedOS/.worktrees/checklist-20261023-c')
lane=Path('/root/build/lane-checklist-20261023-c')
source=lane/'census-14'; previous=lane/'adapter-1'; out=lane/'adapter-2'
out.mkdir(exist_ok=False)
sys.path.insert(0,str(root/'tools'))
helper=runpy.run_path(str(root/'tools/rocq-census/qualify.py'))
adapter=runpy.run_path(str(root/'tools/rocq-census/census.py'))
recipe=json.loads((root/'tools/opam/sail-support-qualification.json').read_text())
expected=['CensusControls']+['SailStdpp.'+name for name in recipe['support_modules']]
prior=840.471316848; allowance=1800-prior
inputs=[root/p for p in ['tools/rocq-census/qualify.py','tools/rocq-census/census.py','tools/rocq-census/census-schema.json','tools/rocq-census/SCHEMA.md','tools/vos/proofaudit.py','tools/rocq-census/vos_rocq_census.ml','tools/rocq-census/control-spec.json']]+[source/'receipt.json',previous/'receipt.json',previous/'reading-targets.json']
receipt={'schema':'verifiedos-native-census-focused-replay/1','scope':'strict native metadata/raw-module graph replay only; no support assumption/kernel acceptance','revision':'13cc28affc8f895435380b3c235b11d2f0077fa4','started_utc':datetime.datetime.now(datetime.UTC).isoformat(),'expected_modules':expected,'phase':'intent','verdict':'pending','source_sha256':{str(p):helper['digest'](p) for p in inputs},'budget':{'candidate':2,'maximum_candidates':3,'maximum_active_minutes':30,'prior_active_seconds':prior,'maximum_remaining_active_seconds':allowance}}
start=time.monotonic(); receipt['budget']['deadline_utc']=(datetime.datetime.now(datetime.UTC)+datetime.timedelta(seconds=allowance)).isoformat()
metadata=result=None; before=maps=None
reading_hashes={}
def save(phase):
    receipt.update(phase=phase,elapsed_seconds=time.monotonic()-start,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out/'checkpoint.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(phase,flush=True)
def current_maps():
    switch=Path('/root/.opam/verifiedos-rocq-9.3.0-ocaml-5.4.1')
    return {'installed':helper['population'](switch/'lib/coq'),'native_api':helper['api_population'](switch/'lib'),'loaded':helper['query_inputs'](source)}
def deadline(*args):raise TimeoutError('remaining adapter/control active budget exhausted')
signal.signal(signal.SIGALRM,deadline)
signal.setitimer(signal.ITIMER_REAL,allowance-20)
try:
    save('small-reading-framing-preflight')
    targets=json.loads((previous/'reading-targets.json').read_text())
    original=json.loads((previous/'receipt.json').read_text())
    readings={}
    for index,(kind,target) in enumerate(targets):
        stem=previous/f'Reading{index:03d}'
        query=stem.with_suffix('.v'); stdout=stem.with_suffix('.stdout.log'); stderr=stem.with_suffix('.stderr.log')
        command=original['commands'][index]
        if command['kind']!=kind or command['target']!=target or command['exit']!=0 or command['source_sha256_after']!=helper['digest'](query) or stderr.read_bytes():raise ValueError('retained native reading provenance differs')
        text=stdout.read_text()
        adapter['_reading'](text,kind,target)
        readings[kind+':'+target]=text
        for path in (query,stdout,stderr):reading_hashes[str(path)]=helper['digest'](path)
    receipt['reading_targets']=len(targets);receipt['reading_sha256']=reading_hashes
    maps=current_maps(); frozen=json.loads((source/'receipt.json').read_text())
    if maps['installed']!=frozen['installed_after'] or maps['native_api']!=frozen['native_api_after'] or maps['loaded']!=frozen['loaded_after']:raise ValueError('protected native inputs changed since candidate14')
    receipt['maps_before']=maps
    save('strict-duplicate-free-parse')
    raw=source/'native-census.json'
    before=helper['output_identity'](raw)
    envelope=json.loads((source/'native-query.stdout.log').read_bytes(),object_pairs_hook=helper['unique_object'])
    if set(envelope)!={'schema','census_schema','path','bytes','blake2b_256'} or envelope['schema']!='verifiedos-native-census-output/1' or envelope['census_schema']!='verifiedos-sail-support-census/1' or envelope['path']!=str(raw) or envelope['bytes']!=before['bytes'] or envelope['blake2b_256']!=before['blake2b_256']:raise ValueError('native envelope differs from exact output identity')
    with raw.open(encoding='utf-8') as stream:
        if helper['output_stat'](os.fstat(stream.fileno()))!=before['stat']:raise ValueError('raw identity changed beforeparse')
        metadata=json.load(stream,object_pairs_hook=helper['unique_object'])
        if helper['output_stat'](os.fstat(stream.fileno()))!=before['stat']:raise ValueError('raw identity changed duringparse')
    if helper['output_identity'](raw)!=before:raise ValueError('raw metadata changed during strict parse')
    receipt['raw_identity']=before
    receipt['native_counts']={k:len(metadata[k]) for k in ('roots','contexts','modules','fields','declarations','abbreviations','module_descents','resolvers','resolution_requests','resolutions')}
    receipt['resolver_domain_counts']={'module_paths':len(metadata['resolvers'][0]['module_effects']),'kernel_names':len(metadata['resolvers'][0]['kernel_effects'])}
    searches={target:(source/f'native-search-{index:02d}.stdout.log').read_text() for index,target in enumerate(expected)}
    save('full-adapter-census')
    result=adapter['census'](metadata,searches,readings,expected_modules=expected)
    receipt['root_verdicts']={name:{'owned_symbols':len(value['symbols']),'alias_audits':len(value.get('alias_audits',[])),'interfaces':len(value['interfaces']),'aliases':len(value['aliases'])} for name,value in result.items()}
    receipt['verdict']='graph-replay-only-pass'
except BaseException as error:
    receipt['verdict']='refused';receipt['refusal']={'type':type(error).__name__,'message':str(error)}
    (out/'exception.log').write_text(traceback.format_exc())
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    metadata=result=None;gc.collect()
    receipt['released_max_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if before is not None:
        receipt['raw_identity_after']=helper['output_identity'](source/'native-census.json');receipt['raw_unchanged']=receipt['raw_identity_after']==before
    if maps is not None:
        after=current_maps();receipt['maps_after']=after;receipt['protected_unchanged']=after==maps
    receipt['source_sha256_after']={p:helper['digest'](Path(p)) for p in receipt['source_sha256']}
    receipt['sources_unchanged']=receipt['source_sha256_after']==receipt['source_sha256']
    receipt['readings_unchanged']=all(helper['digest'](Path(p))==h for p,h in reading_hashes.items())
    if receipt.get('raw_unchanged') is False or receipt.get('protected_unchanged') is False or not receipt['sources_unchanged'] or not receipt['readings_unchanged']:receipt['verdict']='identity-refused'
    save('finished')
    receipt['budget']['cumulative_active_seconds']=prior+receipt['elapsed_seconds']
    receipt['budget']['remaining_active_seconds']=1800-receipt['budget']['cumulative_active_seconds']
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:receipt.get(k) for k in ('verdict','refusal','native_counts','reading_targets','elapsed_seconds','budget','max_rss_kib','protected_unchanged','sources_unchanged','readings_unchanged')}),flush=True)
    sys.exit(0 if receipt['verdict']=='graph-replay-only-pass' else 1)
