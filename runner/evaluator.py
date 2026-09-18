"""Strict process boundary to the pinned C++ evaluator, never a Python VM."""
from dataclasses import dataclass
from pathlib import Path
import json
import os
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = Path(os.environ.get('GSR_EVAL_BINARY', ROOT / 'build/bitcoin/bin/bitcoin-util'))

class HarnessError(RuntimeError):
    pass

@dataclass
class Result:
    success: bool
    error: str | None
    stack: list[bytes]
    remaining: int
    consumed: int
    elapsed_seconds: float

    @property
    def classification(self):
        if self.success:
            return 'accept'
        return 'budget' if self.error == 'Varops budget exceeded' else 'reject'

def evaluate(script, stack=(), budget=1_000_000_000, *, binary=DEFAULT_BINARY, timeout=30):
    if type(budget) is not int or not 0 <= budget < 2**64:
        raise ValueError('budget must be uint64')
    request = dict(protocol=1, sigversion='tapscript_v2', script=script.hex(),
                   stack=[bytes(x).hex() for x in stack], varops_budget=budget)
    start = time.perf_counter()
    try:
        p = subprocess.run([str(binary), 'evalscript'], input=json.dumps(request),
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HarnessError(f'evaluator process failed: {e}') from e
    elapsed = time.perf_counter()-start
    if p.returncode:
        raise HarnessError(f'evaluator exit {p.returncode}: {p.stderr[:2000]}')
    try:
        data = json.loads(p.stdout)
        assert type(data['protocol']) is int and data['protocol'] == 1 and data['context'] == 'standalone'
        assert data['sigversion'] == 'tapscript_v2'
        assert type(data['success']) is bool
        assert (data['error'] is None) if data['success'] else isinstance(data['error'], str)
        remaining = data['varops-budget-remaining']
        assert type(remaining) is int and 0 <= remaining <= budget
        assert type(data['stack-after']) is list
        final = [bytes.fromhex(item) for item in data['stack-after']]
    except (ValueError, TypeError, KeyError, AssertionError) as e:
        raise HarnessError(f'malformed evaluator response: {p.stdout[:500]}') from e
    return Result(data['success'], data['error'], final, remaining, budget-remaining, elapsed)
