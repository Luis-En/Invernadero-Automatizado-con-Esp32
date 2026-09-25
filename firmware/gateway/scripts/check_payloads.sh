#!/usr/bin/env bash
# Compiles the gateway's shared payload builders for the host and validates
# their output against the backend schema. Run `pio run -e gateway` once first
# so PlatformIO has fetched ArduinoJson.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
json_src="$here/.pio/libdeps/gateway/ArduinoJson/src"

if [ ! -d "$json_src" ]; then
  echo "ArduinoJson not found at $json_src" >&2
  echo "Run 'pio run -e gateway' once to download dependencies." >&2
  exit 1
fi

python_bin="${PYTHON:-python3}"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

c++ -std=c++17 -Wall \
  -I "$json_src" -I "$here/include" -I "$here/../common/include" \
  "$here/tools/check_payloads.cpp" \
  "$here/src/json_builder.cpp" \
  "$here/../common/src/protocol.cpp" \
  -o "$work/check_payloads"

"$work/check_payloads" > "$work/payloads.jsonl"
"$python_bin" "$here/scripts/validate_payloads.py" "$work/payloads.jsonl"
