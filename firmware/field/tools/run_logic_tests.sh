#!/usr/bin/env bash
# Compiles the field node's shared logic (automation + config parsing) for the
# host and runs the assertions. Run `pio run -e field` once first so PlatformIO
# has downloaded ArduinoJson.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
json_src="$here/.pio/libdeps/field/ArduinoJson/src"

if [ ! -d "$json_src" ]; then
  echo "ArduinoJson not found at $json_src" >&2
  echo "Run 'pio run -e field' once to download dependencies." >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

c++ -std=c++17 -Wall -Wextra \
  -I "$here/tools" -I "$here/include" -I "$here/../common/include" -I "$json_src" \
  "$here/tools/logic_tests.cpp" \
  "$here/src/automation.cpp" \
  "$here/src/config_model.cpp" \
  "$here/../common/src/protocol.cpp" \
  -o "$work/logic_tests"

"$work/logic_tests"
