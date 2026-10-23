import pathlib,json,hashlib
lane=pathlib.Path('/root/build/lane-checklist-20261023-c');raw=lane/'census-14/native-census.json'
d=json.loads((lane/'adapter-5/first-alias-diagnostic.json').read_text())
identifier=d['first_failure']['module']['implementation']['resolver_id']
def find(pattern,start=0):
    tail=b''
    with raw.open('rb') as f:
        f.seek(start)
        while True:
            p=f.tell();chunk=f.read(1024*1024)
            if not chunk:raise ValueError('native marker absent')
            b=tail+chunk;i=b.find(pattern)
            if i>=0:return p-len(tail)+i
            tail=b[-len(pattern):]
start=find(b'"resolvers":[')
position=find(b'{"id":'+json.dumps(identifier).encode(),start)
with raw.open('rb') as f:
    f.seek(position);data=b''
    while len(data)<32*1024*1024:
        data+=f.read(65536)
        try:resolver,end=json.JSONDecoder().raw_decode(data.decode('utf-8'))
        except (json.JSONDecodeError,UnicodeDecodeError):continue
        break
    else:raise ValueError('single native resolver32MiB cap')
if resolver['id']!=identifier:raise ValueError('native resolver mismatch')
keys={'private_canonical':d['first_failure']['implementation_reference']['canonical'],'exported_user':d['first_failure']['native_reference']['user'],'exported_canonical':d['first_failure']['native_reference']['canonical']}
effects=[]
for role,key in keys.items():
    rows=[x for x in resolver['kernel_effects'] if x['input']==key]
    if len(rows)!=1:raise ValueError('native key absent or duplicate')
    effects.append({'key_role':role,**rows[0]})
r={'schema':'verifiedos-native-public-alias-bridge-diagnostic/1','scope':'read-only one exact public flat-module resolver row; no replay/query/acceptance','raw_source':str(raw),'raw_sha256_from_unchanged_candidate5_cut':d['raw_sha256_from_last_immutable_cut'],'requested_module_id':d['first_failure']['module']['id'],'public_implementation_resolver_id':identifier,'row_offset':position,'row_decoded_characters':end,'resolver':{k:resolver[k] for k in ('id','owner_module_id','role','root','inline_keys')},'kernel_effect_count':len(resolver['kernel_effects']),'module_effect_count':len(resolver['module_effects']),'exact_kernel_effects':effects,'raw_stat_after':{'device':raw.stat().st_dev,'inode':raw.stat().st_ino,'size':raw.stat().st_size,'mtime_ns':raw.stat().st_mtime_ns}}
if r['raw_stat_after']!=d['raw_stat_before']:raise ValueError('raw identity changed')
p=lane/'adapter-5/public-alias-resolver-diagnostic.json';p.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'output':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'resolver':r['resolver'],'exact_kernel_effects':effects},indent=2))
