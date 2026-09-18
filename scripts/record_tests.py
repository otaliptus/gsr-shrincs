#!/usr/bin/env python3
"""Bind successful test logs to the exact tested sources, fixtures and executable."""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    kind=sys.argv[1]
    if kind not in ('native','profiled'):raise SystemExit('expected native or profiled')
    log=ROOT/('reports/tests.log' if kind=='native' else 'reports/tests-profiled.log')
    assert '\nOK\n' in log.read_text() and 'Ran 16 tests' in log.read_text()
    binary=ROOT/('build/bitcoin/bin/bitcoin-util' if kind=='native' else 'build/profile/bin/bitcoin-util')
    files=[p for d in ('generator','runner','reference','tests') for p in (ROOT/d).rglob('*')
           if p.is_file() and '__pycache__' not in str(p)]
    files += [ROOT/'fixtures/vectors.json',binary,log]
    record={str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
    (ROOT/f'reports/tests-{kind}-provenance.json').write_text(json.dumps(record,indent=2)+'\n')
if __name__=='__main__':main()
