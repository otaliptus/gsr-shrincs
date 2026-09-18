#!/usr/bin/env python3
"""Fail closed if packaged evidence is missing, stale, or inconsistent."""
from pathlib import Path
import gzip
import hashlib
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from generator.verifier import compile_verifier,CONTEXT
from generator.transaction import compile_policy
from reference.oracle import verify,decode
from runner.bitcoin import message
from test_framework.messages import tx_from_hex,CTxOut
import io


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    env=json.loads((ROOT/'reports/environment.json').read_text())
    for file,expected in env['sources_sha256'].items():assert sha(ROOT/file)==expected,('stale source',file)
    for file,expected in env['binaries'].items():assert sha(ROOT/file)==expected,('stale binary',file)
    assert sha(ROOT/'fixtures/vectors.json')==env['fixtures_sha256']
    for key,path in (('bitcoin','vendor/bitcoin'),('shrincs','vendor/shrincs-spec')):
        pin=subprocess.check_output(['git','-C',str(ROOT/path),'rev-parse','HEAD'],text=True).strip()
        assert pin==env['versions'][key]['commit']
        assert not subprocess.check_output(['git','-C',str(ROOT/path),'status','--porcelain'],text=True)
    programs=json.loads((ROOT/'generated/manifest.json').read_text())
    for profile in ('baseline','bytes','full'):
        for mode in ('unified','stateful','stateless'):
            name=f'{profile}-{mode}';p=compile_verifier(profile,mode)
            assert (ROOT/f'generated/{name}.bin').read_bytes()==p.code,name
            assert hashlib.sha256(p.code).hexdigest()==programs[name]['sha256']
            p.audit()
    vectors=json.loads((ROOT/'fixtures/vectors.json').read_text())['vectors']
    for v in vectors:
        sig,pk,msg=decode(v);assert verify(msg,sig,pk,bytes.fromhex(v['context'])),v['name']
    data=json.loads(gzip.decompress((ROOT/'reports/regtest-details.json.gz').read_bytes()))
    costs=json.loads((ROOT/'reports/costs.json').read_text())
    assert costs['recorded_transactions_sha256']==sha(ROOT/'reports/regtest-details.json.gz')
    assert len(data['spends'])==len(costs['transactions'])==10
    assert len(data['rejections'])==len(costs['rejected_transactions'])==124
    for row,measured in zip(data['spends'],costs['transactions']):
        assert row['name']==measured['name']
        tx=tx_from_hex(row['raw_transaction']);pk=bytes.fromhex(row['public_key'])
        assert tx.get_weight()==measured['weight']
        assert measured['varops_allowed']==10000*tx.get_weight()
        assert measured['varops_consumed']<=measured['varops_allowed']
        spent=[]
        for serialized in row['spent_outputs']:
            item=CTxOut();item.deserialize(io.BytesIO(bytes.fromhex(serialized)));spent.append(item)
        for i,witness in enumerate(tx.wit.vtxinwit):
            sig,script,control=witness.scriptWitness.stack
            policy=compile_policy(pk,mode=row.get('mode','unified'),profile=row.get('profile','full'),max_inputs=4 if len(tx.vin)>1 else 1)
            assert script==policy.code,(row['name'],'stale transaction program')
            digest=message(tx,spent,i,script)
            assert verify(digest,sig,pk),row['name']
            if 'message' in row:assert digest.hex()==row['message']
            assert control[0]&0xfe==0xc2
        metrics=measured['metrics']
        assert metrics['peak_total_entries']<=32768
        assert metrics['peak_total_bytes']<=8_000_000
        assert metrics['max_item_bytes']<=4_000_000
        assert metrics['executed_function_body_bytes']<=4_000_000
    for row in costs['rejected_transactions']:
        assert not row['node_result']['allowed']
        assert any(not x['success'] for x in row['failure'])
        assert not any('budget' in x.get('error','').lower() for x in row['failure'])
    components=json.loads((ROOT/'reports/components.json').read_text())
    assert components['cases']==384 and all(x['accepted'] for x in components['rows'])
    assert components['evaluator_sha256']==sha(ROOT/'build/bitcoin/bin/bitcoin-util')
    boundaries=json.loads((ROOT/'reports/boundary-costs.json').read_text())
    assert boundaries['rows']==1530 and boundaries['depths']==255
    assert boundaries['details_sha256']==sha(ROOT/'reports/boundary-costs.json.gz')
    boundary_rows=json.loads(gzip.decompress((ROOT/'reports/boundary-costs.json.gz').read_bytes()))
    assert len(boundary_rows)==1530
    for profile in ('baseline','bytes','full'):
        subset=[x for x in boundary_rows if x['profile']==profile]
        assert len(subset)==510
        assert {(x['depth'],x['index']) for x in subset}=={(d,i) for d in range(1,256) for i in (0,2**min(d,64)-1)}
        for row in subset:
            assert row['script_sha256']==programs[f'{profile}-unified']['sha256']
            assert row['metrics']['peak_total_bytes']<=8_000_000
            assert row['metrics']['peak_total_entries']<=32768
            assert row['metrics']['max_item_bytes']<=4_000_000
            assert row['metrics']['executed_function_body_bytes']<=4_000_000
    for kind in ('native','profiled'):
        provenance=json.loads((ROOT/f'reports/tests-{kind}-provenance.json').read_text())
        for file,expected in provenance.items():assert sha(ROOT/file)==expected,('stale tested artifact',kind,file)
    for filename in ('tests.log','tests-profiled.log'):
        log=(ROOT/'reports'/filename).read_text();assert '\nOK\n' in log and 'Ran 16 tests' in log,filename
    assert 'No errors detected' in (ROOT/'reports/upstream-unit.log').read_text()
    log=(ROOT/'reports/upstream-functional.log').read_text()
    for name in ('feature_tapscript_v2.py','feature_tapscript_v2_taproot.py','feature_tapscript_v2_op_tx_vaults.py','tool_utils.py'):
        assert any(name in line and 'passed' in line for line in log.splitlines()),name
    assert 'Tests successful' in (ROOT/'reports/regtest.log').read_text()
    output=dict(status='pass',source_pins_clean=True,generated_programs=9,reference_fixtures=len(vectors),
                stateful_depths_tested=255,accepted_mined_transactions=10,rejected_transactions=124,
                scope='Laboratory verifier/transaction package M0-M7; no external review, production signer, or quantum-safe output wrapper',
                evidence_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'reports').iterdir())
                                 if p.is_file() and p.name not in ('audit.json','AUDIT.md','check.log')})
    (ROOT/'reports/audit.json').write_text(json.dumps(output,indent=2)+'\n')
    print('Completion evidence audit passed')
if __name__=='__main__':main()
