#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PIN=d13165d3d21bac73e8794eede21f0f1527f3b837
if [ ! -d build/simplicity-upstream/.git ]; then
  git clone https://github.com/BlockstreamResearch/shrincs-simplicity-verifier.git build/simplicity-upstream
fi
git -C build/simplicity-upstream checkout --detach "$PIN"
CARGO_TARGET_DIR="$ROOT/build/simplicityhl/target" cargo build --release --locked \
  --manifest-path experiments/simplicity-version-comparison/Cargo.toml
python3 experiments/simplicity-version-comparison/run.py prepare
