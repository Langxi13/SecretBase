#!/usr/bin/env bash
set -euo pipefail

api_level="${1:?Android API level is required}"
package_name="io.github.langxi13.secretbase"
activity_name="${package_name}/.MainActivity"
output_prefix="${RUNNER_TEMP:?RUNNER_TEMP is required}/android-api-${api_level}"
pid=""

capture_evidence() {
  adb exec-out screencap -p >"${output_prefix}.png" 2>/dev/null || rm -f "${output_prefix}.png"
  if [[ -n "$pid" ]]; then
    adb logcat -d --pid="$pid" >"${output_prefix}-logcat.txt" 2>/dev/null || true
  else
    adb logcat -d >"${output_prefix}-logcat.txt" 2>/dev/null || true
  fi
}

wait_for_package_manager() {
  local attempt
  local package_path
  for attempt in $(seq 1 36); do
    if package_path=$(adb shell pm path android 2>/dev/null) &&
      [[ "${package_path//$'\r'/}" == package:* ]]; then
      return 0
    fi
    echo "Waiting for Android package manager (${attempt}/36)..."
    adb wait-for-device >/dev/null 2>&1 || true
    sleep 5
  done
  echo "Android package manager did not become ready." >&2
  return 1
}

install_apk() {
  local attempt
  for attempt in 1 2 3; do
    if adb install --no-streaming -r "$apk"; then
      return 0
    fi
    echo "APK installation failed (${attempt}/3); retrying..." >&2
    sleep $((attempt * 10))
    wait_for_package_manager
  done
  return 1
}

apk=$(find artifacts/android -maxdepth 1 -type f \
  -name '*-android-x86_64*.apk' -print -quit)
if [[ -z "$apk" ]]; then
  apk=$(find artifacts/android -maxdepth 1 -type f \
    -name '*-android-universal*.apk' -print -quit)
fi
if [[ -z "$apk" ]]; then
  echo "Android artifact was not found." >&2
  exit 1
fi

trap capture_evidence EXIT
wait_for_package_manager
adb logcat -c
install_apk
package_dump="${output_prefix}-package.txt"
adb shell dumpsys package "$package_name" >"$package_dump"
if ! grep -Fq 'SecretBaseAutofillService' "$package_dump"; then
  echo "SecretBase AutofillService is not registered in the installed APK." >&2
  exit 1
fi
adb shell settings put secure autofill_service \
  "${package_name}/.autofill.SecretBaseAutofillService"
enabled_autofill=$(adb shell settings get secure autofill_service | tr -d '\r')
if [[ "$enabled_autofill" != *"SecretBaseAutofillService"* ]]; then
  echo "SecretBase AutofillService could not be enabled on the emulator." >&2
  exit 1
fi
adb shell am start -W -n "$activity_name" | tee "${output_prefix}-launch.txt"
sleep 8

pid=$(adb shell pidof "$package_name" | tr -d '\r')
if [[ -z "$pid" ]]; then
  echo "SecretBase process is not running after launch." >&2
  exit 1
fi

capture_evidence
trap - EXIT

if grep -Fq 'FATAL EXCEPTION' "${output_prefix}-logcat.txt"; then
  echo "SecretBase emitted a fatal Android exception." >&2
  exit 1
fi
