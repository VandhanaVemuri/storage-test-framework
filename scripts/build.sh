#!/usr/bin/env bash
# Builds the C++ storage test engine.
set -euo pipefail
cd "$(dirname "$0")/../cpp"
g++ -std=c++17 -Wall -O2 -Iinclude src/device.cpp src/main.cpp -o storage_test_cli
echo "Built cpp/storage_test_cli"
