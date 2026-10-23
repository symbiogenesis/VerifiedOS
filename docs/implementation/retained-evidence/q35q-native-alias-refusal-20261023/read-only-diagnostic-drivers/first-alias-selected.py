import pathlib,json,hashlib
lane=pathlib.Path('/root/build/lane-checklist-20261023-c');raw=lane/'census-14/native-census.json';out=lane/'adapter-5/first-alias-diagnostic.json'
receipt=json.loads((lane/'adapter-5/receipt.json').read_text());expected=receipt['raw_before'][str(raw)]
statkey=lambda s:{'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns}
before=statkey(raw.stat())
if before!=expected['stat']:raise ValueError('raw inode/stat differs from last immutable cut')
scan_events=[]
def unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('duplicate JSON key')
        result[k]=v
    return result
decoder=json.JSONDecoder(object_pairs_hook=unique)
def find(pattern,start=0):
    tail=b'';scanned=0
    with raw.open('rb') as f:
        f.seek(start)
        while True:
            offset=f.tell();block=f.read(1024*1024)
            if not block:raise ValueError('native marker missing '+repr(pattern))
            scanned+=len(block);data=tail+block;i=data.find(pattern)
            if i>=0:
                found=offset-len(tail)+i;scan_events.append({'pattern':pattern.decode(),'start':start,'found':found,'scanned_bytes':scanned});return found
            tail=data[-len(pattern):]
def decode_at(offset,cap=32*1024*1024):
    data=b''
    with raw.open('rb') as f:
        f.seek(offset)
        while len(data)<cap:
            block=f.read(65536)
            if not block:raise ValueError('native JSON end')
            data+=block
            try:text=data.decode('utf-8');value,end=decoder.raw_decode(text)
            except (json.JSONDecodeError,UnicodeDecodeError):continue
            consumed=len(text[:end].encode('utf-8'));return value,offset+consumed,consumed
    raise ValueError('single-row diagnostic cap32MiB reached')
def row(identifier,start=0):
    pattern=b'{"id":'+json.dumps(identifier,separators=(',',':')).encode()
    offset=find(pattern,start);value,end,size=decode_at(offset)
    if value['id']!=identifier:raise ValueError('wrong exact native ID')
    return value,{'id':identifier,'offset':offset,'decoded_bytes':size}
marker=b'"declarations":[';position=find(marker)+len(marker);count=0;failure=None;declaration_read=0
while failure is None:
    with raw.open('rb') as f:
        f.seek(position);one=f.read(1)
    if one==b',':position+=1
    elif one==b']':break
    value,position,size=decode_at(position);count+=1;declaration_read+=size
    if declaration_read>64*1024*1024:raise ValueError('declaration-prefix diagnostic cap64MiB reached')
    if value.get('classification')!='alias':continue
    alias=value['alias'];reference=value['native_reference'];link=value['implementation_connection']
    checks={'alias_present':alias is not None,'exported_reference_matches':alias is not None and alias['exported_reference']==reference,'target_matches_private_implementation':alias is not None and alias['target_reference']==link['implementation_reference'],'private_and_exported_canonical_equal':alias is not None and alias['target_reference']['canonical']==reference['canonical']}
    if all(checks.values()):continue
    failure={k:value[k] for k in ('id','field_id','kind','label','exported_name','classification')}
    failure.update(predicate_checks=checks,native_reference=reference,alias=alias,source_reference=link['source_reference'],implementation_reference=link['implementation_reference'],source_field=link['source_field'],instantiated_field=link['instantiated_field'],steps=link['steps'],enclosing_descent_ids=link['enclosing_descent_ids'])
    value=None
if failure is None:raise ValueError('no failing direct alias found')
field,field_location=row(failure['field_id']);module,module_location=row(field['parent_module_id'])
failure['field']={k:field[k] for k in ('id','parent_module_id','namespace','label','kind')}
failure['module']={k:module[k] for k in ('id','native_path','parent_field_id','implementation','query')}
anchor_id=module['implementation']['resolver_id'];descent_location=None
if failure['enclosing_descent_ids']:
    descent,descent_location=row(failure['enclosing_descent_ids'][-1]);anchor_id=descent['instantiated_module']['implementation']['resolver_id']
    failure['owner_descent']={'id':descent['id'],'owner_module_id':descent['owner_module_id'],'parent_descent_id':descent['parent_descent_id'],'source_field':descent['source_field'],'instantiated_field':descent['instantiated_field'],'source_implementation':descent['source_module']['implementation'],'instantiated_implementation':descent['instantiated_module']['implementation']}
    descent=None
resolver_start=find(b'"resolvers":[')+len(b'"resolvers":[')
resolver,resolver_location=row(failure['alias']['resolver_id'],resolver_start)
anchor,anchor_location=(resolver,resolver_location) if anchor_id==resolver['id'] else row(anchor_id,resolver_start)
keys={'private_user':failure['implementation_reference']['user'],'private_canonical':failure['implementation_reference']['canonical'],'exported_user':failure['native_reference']['user'],'exported_canonical':failure['native_reference']['canonical']}
def effects(r):
    result=[]
    for role,key in keys.items():
        found=[item for item in r['kernel_effects'] if item['input']==key]
        if len(found)!=1:raise ValueError('missing or ambiguous exact kernel key '+role)
        result.append({'key_role':role,**found[0]})
    return result
result={'schema':'verifiedos-native-first-alias-diagnostic/1','scope':'read-only selected declaration/module/descent rows and one or two native resolver rows; no full artifact parse/query/acceptance','raw_source':str(raw),'raw_sha256_from_last_immutable_cut':expected['sha256'],'raw_blake2b_256_from_last_immutable_cut':expected['blake2b_256'],'raw_stat_before':before,'declarations_examined':count,'declaration_prefix_decoded_bytes':declaration_read,'per_row_cap_bytes':32*1024*1024,'declaration_prefix_cap_bytes':64*1024*1024,'row_locations':[field_location,module_location,resolver_location,anchor_location]+([descent_location] if descent_location else []),'byte_scan_events':scan_events,'first_failure':failure,'selected_resolver':{k:resolver[k] for k in ('id','owner_module_id','role','root','inline_keys')},'anchor_resolver':{k:anchor[k] for k in ('id','owner_module_id','role','root','inline_keys')},'resolver_same_id':resolver['id']==anchor['id'],'resolver_full_effects_equivalent':all(resolver[k]==anchor[k] for k in ('root','module_effects','kernel_effects','inline_keys')),'selected_resolver_population':{'module_effects':len(resolver['module_effects']),'kernel_effects':len(resolver['kernel_effects'])},'exact_kernel_effects':effects(resolver),'anchor_exact_kernel_effects':effects(anchor),'raw_stat_after':statkey(raw.stat())}
if result['raw_stat_after']!=before:raise ValueError('raw identity changed during diagnostic')
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'output':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'declared_name':failure['exported_name'],'declarations_examined':count,'declaration_prefix_decoded_bytes':declaration_read,'checks':failure['predicate_checks'],'private_reference':failure['implementation_reference'],'exported_reference':failure['native_reference'],'selected_resolver':result['selected_resolver'],'anchor_resolver':result['anchor_resolver'],'resolver_same_id':result['resolver_same_id'],'resolver_full_effects_equivalent':result['resolver_full_effects_equivalent'],'effects':result['exact_kernel_effects']},indent=2))
