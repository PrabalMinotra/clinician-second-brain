#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime/swift-cache
swiftc -module-cache-path .runtime/swift-cache scripts/ocr.swift -o scripts/ocr-local
