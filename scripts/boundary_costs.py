#!/usr/bin/env python3
"""Resource accounting for every supported stateful depth and index extreme."""
from pathlib import Path
import gzip
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from generator.verifier import compile_verifier
from reference.oracle import synthetic_stateful, decode
from runner.evaluator import evaluate
from runner.profile import run_profile
from scripts.measure import evaluate_request

def main():
    programs={p:compile_verifier(p) for p in ('baseline','bytes','full')}
    rows=[]
    for depth in range(1,256):
        for index in (0,2**min(depth,64)-1):
            v=synthetic_stateful(depth,index);values=decode(v)
            for profile,p in programs.items():
                r=evaluate(p.code,values)
                m=run_profile('evalscript',evaluate_request(p.code,values))
                assert r.success and m['success']
                assert r.remaining==m['varops-budget-remaining']
                assert m['profile']['sha256_calls']==244+depth
                rows.append(dict(depth=depth,index=index,profile=profile,signature_bytes=len(values[0]),
                    script_bytes=len(p.code),script_sha256=hashlib.sha256(p.code).hexdigest(),
                    input_sha256=hashlib.sha256(b''.join(values)).hexdigest(),varops_consumed=r.consumed,metrics=m['profile']))
    (ROOT/'reports/boundary-costs.json.gz').write_bytes(gzip.compress(json.dumps(rows,sort_keys=True).encode(),mtime=0))
    summary=dict(rows=len(rows),depths=255,index_classes=['zero','maximum'],
                 fixture_provenance='Synthetic authentication siblings with genuine WOTS signing and computed root binding',
                 allowance='Standalone functional allowance; transaction feasibility is measured separately in costs.json',profiles={})
    for profile in programs:
        subset=[x for x in rows if x['profile']==profile]
        summary['profiles'][profile]=dict(varops_min=min(x['varops_consumed'] for x in subset),
            varops_max=max(x['varops_consumed'] for x in subset),
            peak_total_bytes=max(x['metrics']['peak_total_bytes'] for x in subset),
            peak_total_entries=max(x['metrics']['peak_total_entries'] for x in subset),
            maximum_item=max(x['metrics']['max_item_bytes'] for x in subset),
            maximum_invoked_body_bytes=max(x['metrics']['executed_function_body_bytes'] for x in subset))
    summary['details_sha256']=hashlib.sha256((ROOT/'reports/boundary-costs.json.gz').read_bytes()).hexdigest()
    (ROOT/'reports/boundary-costs.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(f'Measured {len(rows)} boundary executions with matching instrumented/native results')
if __name__=='__main__':main()
