#!/usr/bin/env bash
set -euo pipefail

api_level="${1:?Android API level is required}"
package_name="io.github.langxi13.secretbase"
activity_name="${package_name}/.MainActivity"
output_prefix="${RUNNER_TEMP:?RUNNER_TEMP is required}/android-api-${api_level}"

apk=$(find artifacts/android -maxdepth 1 -type f -name '*.apk' -print -quit)
if [[ -z "$apk" ]]; then
  echo "Android artifact was not found." >&2
  exit 1
fi

adb logcat -c
adb install "$apk"
adb shell am start -W -n "$activity_name" | tee "${output_prefix}-launch.txt"
sleep 8

pid=$(adb shell pidof "$package_name" | tr -d '\r')
if [[ -z "$pid" ]]; then
  echo "SecretBase process is not running after launch." >&2
  exit 1
fi

adb exec-out screencap -p >"${output_prefix}.png"
adb logcat -d --pid="$pid" >"${output_prefix}-logcat.txt"

if grep -Fq 'FATAL EXCEPTION' "${output_prefix}-logcat.txt"; then
  echo "SecretBase emitted a fatal Android exception." >&2
  exit 1
fi
