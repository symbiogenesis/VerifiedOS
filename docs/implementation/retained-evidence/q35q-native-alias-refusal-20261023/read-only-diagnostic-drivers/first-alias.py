import pathlib,json,hashlib,os
lane=pathlib.Path('/root/build/lane-checklist-20261023-c')
raw=lane/'census-14/native-census.json'
out=lane/'adapter-5/first-alias-diagnostic.json'
receipt=json.loads((lane/'adapter-5/receipt.json').read_text())
expected=receipt['raw_before'][str(raw)]
statkey=lambda s:{'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtime_ns':s.st_mtime_ns}
before=statkey(raw.stat())
if before!=expected['stat']:raise ValueError('raw inode/stat differs from last accepted identity cut')
decoder=json.JSONDecoder(object_pairs_hook=lambda pairs:dict(pairs))
class Reader:
    def __init__(self,f):self.f=f;self.buf='';self.offset=0;self.read_bytes=0
    def more(self):
        s=self.f.read(65536)
        if not s:raise ValueError('unexpected native JSON end')
        self.buf+=s;self.read_bytes+=len(s.encode('utf-8'))
        if self.read_bytes>64*1024*1024:raise ValueError('ordinary-prefix diagnostic cap64MiB reached')
    def consume(self,n):self.offset+=len(self.buf[:n].encode('utf-8'));self.buf=self.buf[n:]
    def token(self,wanted):
        while not self.buf:self.more()
        spaces=len(self.buf)-len(self.buf.lstrip());self.consume(spaces)
        while not self.buf:self.more()
        if not self.buf.startswith(wanted):raise ValueError('unexpected ordinary JSON token')
        self.consume(len(wanted))
    def value(self):
        while True:
            if not self.buf:self.more()
            spaces=len(self.buf)-len(self.buf.lstrip());self.consume(spaces)
            try:value,end=decoder.raw_decode(self.buf)
            except json.JSONDecodeError:self.more();continue
            self.consume(end);return value
    def array(self):
        self.token('[')
        first=True
        while True:
            while not self.buf:self.more()
            if self.buf.lstrip().startswith(']'):
                self.token(']');return
            if not first:self.token(',')
            first=False
            yield self.value()
fields={};modules={};failure=None;resolver_offset=None;topkeys=[]
with raw.open(encoding='utf-8') as stream:
    r=Reader(stream);r.token('{');first=True
    while True:
        if not first:r.token(',')
        first=False
        key=r.value();r.token(':');topkeys.append(key)
        if key=='resolvers':
            r.token('[');resolver_offset=r.offset;break
        if key in ('modules','fields','declarations'):
            for row in r.array():
                if key=='modules':
                    modules[row['id']]={'id':row['id'],'native_path':row['native_path'],'parent_field_id':row['parent_field_id'],'implementation':row['implementation'],'signature_resolver_id':row['signature'].get('resolver_id'),'query':row['query']}
                elif key=='fields':fields[row['id']]={k:row[k] for k in ('id','parent_module_id','namespace','label','kind')}
                elif failure is None and row['classification']=='alias':
                    alias=row['alias'];ref=row['native_reference'];link=row['implementation_connection']
                    checks={'alias_present':alias is not None,'exported_reference_matches':alias is not None and alias['exported_reference']==ref,'target_matches_private_implementation':alias is not None and alias['target_reference']==link['implementation_reference'],'private_and_exported_canonical_equal':alias is not None and alias['target_reference']['canonical']==ref['canonical']}
                    if not all(checks.values()):
                        failure={k:row[k] for k in ('id','field_id','kind','label','exported_name','classification')}
                        failure.update(predicate_checks=checks,native_reference=ref,alias=alias,source_reference=link['source_reference'],implementation_reference=link['implementation_reference'],source_field=link['source_field'],instantiated_field=link['instantiated_field'],steps=link['steps'],enclosing_descent_ids=link['enclosing_descent_ids'])
                row=None
        else:
            discarded=r.value();discarded=None
    ordinary_read_bytes=r.read_bytes
if failure is None:raise ValueError('no failing direct alias predicate found')
field=fields[failure['field_id']];module=modules[field['parent_module_id']]
failure['field']=field;failure['module']=module
wanted=failure['alias']['resolver_id']
pattern=b'{"id":'+json.dumps(wanted,separators=(',',':')).encode('utf-8')
scanned=0;tail=b'';found=None
with raw.open('rb') as stream:
    stream.seek(resolver_offset)
    while True:
        start=stream.tell();block=stream.read(1024*1024)
        if not block:break
        scanned+=len(block);data=tail+block
        index=data.find(pattern)
        if index>=0:found=start-len(tail)+index;break
        tail=data[-len(pattern):]
    if found is None:raise ValueError('native alias resolver row missing')
    stream.seek(found);encoded=b''
    while True:
        encoded+=stream.read(65536)
        if len(encoded)>8*1024*1024:raise ValueError('single-resolver diagnostic cap8MiB reached')
        try:resolver,end=decoder.raw_decode(encoded.decode('utf-8'))
        except (json.JSONDecodeError,UnicodeDecodeError):continue
        break
if resolver['id']!=wanted:raise ValueError('wrong resolver row')
kernels={
 'private_user':failure['implementation_reference']['user'],
 'private_canonical':failure['implementation_reference']['canonical'],
 'exported_user':failure['native_reference']['user'],
 'exported_canonical':failure['native_reference']['canonical']}
effects=[]
for name,key in kernels.items():
    matches=[effect for effect in resolver['kernel_effects'] if effect['input']==key]
    if len(matches)!=1:raise ValueError('exact kernel input absent or duplicated')
    effects.append({'key_role':name,**matches[0]})
result={'schema':'verifiedos-native-first-alias-diagnostic/1','scope':'read-only selected ordinary-table identities and one native resolver row; no census acceptance or native query','raw_source':str(raw),'raw_sha256_from_last_immutable_cut':expected['sha256'],'raw_blake2b_256_from_last_immutable_cut':expected['blake2b_256'],'raw_stat_before':before,'ordinary_prefix_cap_bytes':64*1024*1024,'ordinary_prefix_read_bytes':ordinary_read_bytes,'resolver_array_offset':resolver_offset,'single_resolver_cap_bytes':8*1024*1024,'resolver_row_offset':found,'resolver_scan_bytes':scanned,'resolver_decoded_bytes':len(encoded[:len(encoded.decode('utf-8')[:end].encode('utf-8'))]),'ordinary_top_keys':topkeys,'first_failure':failure,'selected_resolver':{k:resolver[k] for k in ('id','module_id','role','root','inline_keys')},'selected_resolver_population':{'module_effects':len(resolver['module_effects']),'kernel_effects':len(resolver['kernel_effects'])},'exact_kernel_effects':effects,'raw_stat_after':statkey(raw.stat())}
if result['raw_stat_after']!=before:raise ValueError('raw identity changed during diagnostic')
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'output':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'ordinary_prefix_read_bytes':ordinary_read_bytes,'resolver_scan_bytes':scanned,'declared_name':failure['exported_name'],'checks':failure['predicate_checks'],'alias_resolver':result['selected_resolver'],'effects':effects},indent=2))
