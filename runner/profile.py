"""Observation adapter; an error is never a cryptographic rejection."""
import json
import subprocess
import time
from .evaluator import ROOT, HarnessError
BINARY=ROOT/'build/profile/bin/bitcoin-util'

def run_profile(command,request):
    start=time.perf_counter_ns()
    try:
        p=subprocess.run([str(BINARY),command],input=json.dumps(request),capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired) as e:raise HarnessError(str(e)) from e
    wall=time.perf_counter_ns()-start
    if p.returncode:raise HarnessError(p.stderr)
    try:
        r=json.loads(p.stdout)
        assert type(r['success']) is bool and type(r['profile']['interpreter_ns']) is int
    except (ValueError,KeyError,AssertionError,TypeError) as e:raise HarnessError(p.stdout[:1000]) from e
    r['wall_ns']=wall
    r['process_and_protocol_overhead_ns']=wall-r['profile']['interpreter_ns']
    return r
