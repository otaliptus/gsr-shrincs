#!/usr/bin/env bash
# Requires the two builds and an environment permitting localhost regtest sockets.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports
unset GSR_EVAL_BINARY
build/bitcoin/bin/test_bitcoin --run_test=tapscript_v2_tests,tapscript_v2_json_tests,varops_tests,op_tx_tests,valtype_stack_tests --log_level=test_suite > reports/upstream-unit.log 2>&1
python3 build/bitcoin/test/functional/test_runner.py feature_tapscript_v2.py feature_tapscript_v2_taproot.py feature_tapscript_v2_op_tx_vaults.py tool_utils.py --jobs=2 > reports/upstream-functional.log 2>&1
python3 scripts/run_tests.py native > reports/tests.log 2>&1
python3 scripts/record_tests.py native
GSR_EVAL_BINARY="$PWD/build/profile/bin/bitcoin-util" python3 scripts/run_tests.py profiled > reports/tests-profiled.log 2>&1
python3 scripts/record_tests.py profiled
python3 -O scripts/run_tests.py optimized > reports/tests-optimized.log 2>&1
python3 scripts/record_tests.py optimized
python3 tests/regtest.py --configfile="$PWD/build/bitcoin/test/config.ini" > reports/regtest.log 2>&1
python3 scripts/measure.py > reports/measure.log 2>&1
python3 scripts/component_costs.py > reports/components.log 2>&1
python3 scripts/boundary_costs.py > reports/boundary-costs.log 2>&1
python3 scripts/parsing_probe.py --reference-binary build/profile/bin/bitcoin-util --jobs "${GSR_BUILD_JOBS:-4}" > reports/parsing-probe.log 2>&1
python3 scripts/parse_benchmark.py --jobs "${GSR_BUILD_JOBS:-4}" > reports/parser-benchmark.log 2>&1
python3 scripts/multi_compare.py --binary build/profile/bin/bitcoin-util --output reports/multi-comparison.json > reports/multi-comparison.log 2>&1
python3 scripts/export.py
python3 scripts/audit.py
python3 -O scripts/audit.py
