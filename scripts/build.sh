#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git submodule update --init --recursive
args=(-S vendor/bitcoin -B build/bitcoin -G Ninja -DCMAKE_BUILD_TYPE=Release
      -DENABLE_IPC=OFF -DENABLE_WALLET=OFF -DBUILD_GUI=OFF -DWITH_CCACHE=OFF)
if [[ -d build/deps/usr ]]; then args+=("-DCMAKE_PREFIX_PATH=$PWD/build/deps/usr"); fi
cmake "${args[@]}"
cmake --build build/bitcoin --target bitcoin-util bitcoind bitcoin-cli bitcoin-tx test_bitcoin -j "${GSR_BUILD_JOBS:-4}"
